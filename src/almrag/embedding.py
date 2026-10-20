"""Pinned local tokenizer and explicit, calibrated Ollama embedding runtime.

Constructing these objects never downloads a model/tokenizer or contacts a server.
Fixture verification cannot be promoted to production VERIFIED evidence.
"""
import hashlib
import json
import math
from pathlib import Path

import httpx
from pydantic import BaseModel,ConfigDict,Field

from almrag.config import canonical_endpoint
from almrag.queue import LeaseLost


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


class ModelError(ValueError):
    def __init__(self,code,global_error=True,stop_state='BLOCKED'):
        super().__init__(code)
        self.code,self.global_error,self.stop_state=code,global_error,stop_state


class ModelConfig(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    model_name:str=Field(default='embeddinggemma-2',pattern=r'^embeddinggemma-2(?::[A-Za-z0-9_.-]+)?$')
    expected_digest:str=Field(pattern=r'^sha256:[0-9a-f]{64}$')
    vector_dimension:int=Field(default=768,ge=1,le=32768)
    effective_max_input_tokens:int=Field(default=1024,ge=1,le=262144)


class LocalTokenizer:
    """Load a hash-pinned local tokenizer.json; never from_pretrained/network."""
    def __init__(self,path,expected_sha256):
        from tokenizers import Tokenizer
        try:
            data=Path(path).read_bytes()
            if hashlib.sha256(data).hexdigest()!=expected_sha256:
                raise ModelError('TOKENIZER_ARTIFACT_MISMATCH')
            self._tokenizer=Tokenizer.from_str(data.decode('utf-8'))
            self._tokenizer.no_truncation()
            self._tokenizer.no_padding()
        except ModelError:raise
        except Exception:
            # Tokenizers' Rust binding may raise its own generic Exception.
            raise ModelError('TOKENIZER_ARTIFACT_UNAVAILABLE') from None
        self._identity='hf-json:'+expected_sha256+':untruncated-unpadded-v1:special-tokens-on'

    @property
    def identity(self):return self._identity

    def count(self,text):
        if not isinstance(text,str):raise ModelError('TOKENIZER_INPUT_INVALID')
        return len(self._tokenizer.encode(text,add_special_tokens=True).ids)


class OllamaEmbedder:
    def __init__(self,base_url,config,tokenizer,*,transport=None,allow_live=False,
                 allow_fixture=False,auth_headers=None,verify=True,abort_check=lambda:False,
                 timeout_seconds=30,max_response_bytes=16*1024*1024):
        self.base_url=canonical_endpoint(base_url)
        self.config,self.tokenizer=config,tokenizer
        self.transport,self.allow_live,self.allow_fixture=transport,allow_live,allow_fixture
        self.headers,self.verify=auth_headers or {},verify
        self.abort_check,self.timeout_seconds,self.max_response_bytes=abort_check,timeout_seconds,max_response_bytes
        self._profile=None

    @property
    def profile(self):
        return None if self._profile is None else json.loads(json.dumps(self._profile))

    def _abort(self):
        if self.abort_check():raise ModelError('ABORTED',stop_state='PAUSED')

    def _request(self,method,path,payload=None):
        self._abort()
        if self.transport is None and not self.allow_live:raise ModelError('MODEL_NETWORK_DISABLED')
        if (method,path) not in {('GET','/api/tags'),('POST','/api/show'),('POST','/api/embed')}:
            raise ModelError('MODEL_ENDPOINT_FORBIDDEN')
        try:
            with httpx.Client(transport=self.transport,timeout=self.timeout_seconds,verify=self.verify,follow_redirects=False,trust_env=False) as client:
                with client.stream(method,self.base_url+path,json=payload,headers=self.headers) as response:
                    status=response.status_code
                    if 300<=status<400:raise ModelError('MODEL_REDIRECT_FORBIDDEN')
                    if status in {401,403}:raise ModelError('MODEL_AUTH_FAILED')
                    if status==429 or status>=500:raise ModelError('MODEL_SERVER_PAUSED',stop_state='PAUSED')
                    if path=='/api/embed' and status in {400,413,422}:raise ModelError('INPUT_REJECTED',False)
                    if status!=200:raise ModelError('MODEL_UNAVAILABLE')
                    body=bytearray()
                    for part in response.iter_bytes():
                        self._abort()
                        if len(body)+len(part)>self.max_response_bytes:raise ModelError('MODEL_RESPONSE_TOO_LARGE')
                        body.extend(part)
            self._abort()
            value=json.loads(body)
            if not isinstance(value,dict):raise ModelError('MODEL_RESPONSE_SCHEMA_MISMATCH')
            return value
        except (ModelError,LeaseLost):raise
        except httpx.HTTPError:raise ModelError('MODEL_TRANSPORT_ERROR',stop_state='PAUSED') from None
        except (ValueError,UnicodeError,OSError):raise ModelError('MODEL_RESPONSE_SCHEMA_MISMATCH') from None

    def _digest(self):
        payload=self._request('GET','/api/tags')
        name=self.config.model_name if ':' in self.config.model_name else self.config.model_name+':latest'
        models=payload.get('models')
        if not isinstance(models,list):raise ModelError('MODEL_RESPONSE_SCHEMA_MISMATCH')
        found=[model for model in models if isinstance(model,dict) and model.get('name',model.get('model'))==name]
        if len(found)!=1:raise ModelError('MODEL_UNAVAILABLE')
        if found[0].get('digest')!=self.config.expected_digest:raise ModelError('MODEL_DIGEST_MISMATCH')
        return found[0]['digest']

    def _count(self,text):
        count=self.tokenizer.count(text)
        if not isinstance(count,int) or isinstance(count,bool) or count<0:raise ModelError('TOKENIZER_COUNT_INVALID')
        return count

    def _vector(self,text,expected_tokens):
        body=self._request('POST','/api/embed',{'model':self.config.model_name,'input':text,'truncate':False,
            'dimensions':self.config.vector_dimension,'options':{'num_ctx':self.config.effective_max_input_tokens}})
        vectors=body.get('embeddings')
        if body.get('model') not in {self.config.model_name,self.config.model_name+':latest'}:
            raise ModelError('MODEL_RESPONSE_IDENTITY_MISMATCH')
        if not isinstance(vectors,list) or len(vectors)!=1 or not isinstance(vectors[0],list):
            raise ModelError('VECTOR_INTEGRITY_ERROR')
        vector=vectors[0]
        if len(vector)!=self.config.vector_dimension or any(isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) for n in vector):
            raise ModelError('VECTOR_INTEGRITY_ERROR')
        if not any(n!=0 for n in vector):raise ModelError('VECTOR_INTEGRITY_ERROR')
        count=body.get('prompt_eval_count')
        if not isinstance(count,int) or isinstance(count,bool) or count!=expected_tokens:
            raise ModelError('TOKENIZER_MISMATCH')
        return [float(n) for n in vector]

    def verify_runtime(self):
        self._profile=None
        if self.transport is None and not self.allow_live:raise ModelError('MODEL_NETWORK_DISABLED')
        if not isinstance(self.tokenizer,LocalTokenizer) and not self.allow_fixture:raise ModelError('TOKENIZER_UNVERIFIED')
        if self.transport is not None and not self.allow_fixture:raise ModelError('MODEL_VERIFICATION_TEST_TRANSPORT')
        digest=self._digest()
        show=self._request('POST','/api/show',{'model':self.config.model_name})
        if 'embedding' not in show.get('capabilities',[]):raise ModelError('MODEL_CAPABILITY_MISMATCH')
        info=show.get('model_info')
        if not isinstance(info,dict):raise ModelError('MODEL_CONTEXT_UNVERIFIED')
        limits=[value for key,value in info.items() if key.endswith('.context_length') and isinstance(value,int) and not isinstance(value,bool) and value>0]
        if not limits or self.config.effective_max_input_tokens>min(limits):raise ModelError('MODEL_CONTEXT_UNVERIFIED')
        evidence=[]
        for text in ['Calibration text.','한글 Unicode ☃ = header/value']:
            count=self._count(text)
            if count>self.config.effective_max_input_tokens:raise ModelError('CALIBRATION_CONTEXT_TOO_SMALL')
            self._vector(text,count)
            evidence.append({'input_digest':hashlib.sha256(text.encode()).hexdigest(),'tokens':count})
        self._digest()
        profile={'state':'FIXTURE_ONLY' if self.allow_fixture or self.transport is not None else 'VERIFIED',
                 'model_digest':digest,'tokenizer_id':self.tokenizer.identity,
                 'config':self.config.model_dump(),'calibration_evidence':evidence}
        profile['fingerprint']=fingerprint(profile)
        self._profile=profile
        return self.profile

    def embed(self,text,*,expected_tokens):
        if self._profile is None:raise ModelError('MODEL_RUNTIME_UNVERIFIED')
        if self.tokenizer.identity!=self._profile['tokenizer_id']:raise ModelError('TOKENIZER_MISMATCH')
        count=self._count(text)
        if count!=expected_tokens:raise ModelError('TOKENIZER_MISMATCH')
        if count>self.config.effective_max_input_tokens:raise ModelError('INPUT_TOO_LARGE',False)
        self._digest()
        vector=self._vector(text,count)
        self._digest()
        return vector

    def check_identity(self):
        if self._profile is None:raise ModelError('MODEL_RUNTIME_UNVERIFIED')
        self._digest()
        if self.tokenizer.identity!=self._profile['tokenizer_id']:raise ModelError('TOKENIZER_MISMATCH')
        return self.profile
