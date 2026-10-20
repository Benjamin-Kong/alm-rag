"""Operator-supplied local artifact profiles, with explicit inference opt-in."""
import copy
import hashlib
from pathlib import Path
import ssl
import threading

from pydantic import BaseModel,ConfigDict,Field,ValidationError

from almrag.connection import Connections
from almrag.embedding import LocalTokenizer,ModelConfig,ModelError,OllamaEmbedder


class LocalModelProfile(BaseModel):
    model_config=ConfigDict(extra='forbid')
    model:ModelConfig
    tokenizer_path:str=Field(min_length=1)
    tokenizer_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')


class ModelRuntimeRegistry:
    def __init__(self,settings,db=None,secret_resolver=None):
        self.settings,self.db=settings,db
        self.secret_resolver=secret_resolver
        self._cache={}
        self._lock=threading.RLock()

    def get(self,project_uid):
        if not self.settings.model_profile_path:raise ModelError('MODEL_PROFILE_UNCONFIGURED')
        path=Path(self.settings.model_profile_path).resolve()
        try:
            data=path.read_bytes()
            profile=LocalModelProfile.model_validate_json(data)
        except ValidationError:raise ModelError('MODEL_PROFILE_INVALID') from None
        except OSError:raise ModelError('MODEL_PROFILE_UNAVAILABLE') from None
        key=(str(path),hashlib.sha256(data).hexdigest())
        with self._lock:
            if key not in self._cache:
                tokenizer_path=Path(profile.tokenizer_path)
                if not tokenizer_path.is_absolute():tokenizer_path=path.parent/tokenizer_path
                tokenizer=LocalTokenizer(tokenizer_path,profile.tokenizer_sha256)
                try:
                    verify=ssl.create_default_context(cafile=self.settings.ca_bundle) if self.settings.tls_verify else False
                except (OSError,ValueError):raise ModelError('MODEL_TLS_CONFIG_INVALID') from None
                self._cache={key:OllamaEmbedder(self.settings.ollama_url,profile.model,tokenizer,
                    allow_live=self.settings.live_model_enabled,verify=verify)}
            runtime=self._cache[key]
            headers={}
            if self.settings.ollama_auth_ref:
                resolver=self.secret_resolver or (Connections(self.db,self.settings).secret if self.db is not None else None)
                if resolver is None:raise ModelError('MODEL_CREDENTIAL_UNAVAILABLE')
                try:secret=resolver(self.settings.ollama_auth_ref)
                except (ValueError,OSError):raise ModelError('MODEL_CREDENTIAL_UNAVAILABLE') from None
                if not isinstance(secret,str) or not secret:raise ModelError('MODEL_CREDENTIAL_UNAVAILABLE')
                headers['Authorization']='Bearer '+secret
            runtime.headers=headers
            if self.settings.live_model_enabled:
                if runtime.profile is None:runtime.verify_runtime()
                else:runtime.check_identity()
            # Immutable verified evidence may be reused, while mutable abort
            # callbacks and request credentials remain local to each job clone.
            result=copy.copy(runtime)
            result.headers=dict(headers)
            return result
