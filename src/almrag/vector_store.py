"""Bounded Qdrant REST adapter for internal, isolated index generations.

No construction I/O, redirects, ambient proxy credentials or model/source calls.
Publication and SQLite/point digest comparisons belong to the index coordinator.
"""
import json
import math
import re
import time
from uuid import UUID

import httpx

from almrag.config import canonical_endpoint
from almrag.queue import LeaseLost


PAYLOAD_KEYS=frozenset(('project_uid','generation_uid','item_uid','revision_uid',
    'chunk_uid','result_uid','content_hash','model_fingerprint','vector_digest'))


class VectorError(ValueError):
    def __init__(self,code,global_error=True,stop_state='BLOCKED'):
        super().__init__(code)
        self.code,self.global_error,self.stop_state=code,global_error,stop_state


def _integer(value,minimum,maximum):
    return isinstance(value,int) and not isinstance(value,bool) and minimum<=value<=maximum


def _identifier(value):
    if not isinstance(value,str):raise VectorError('VECTOR_POINT_ID_INVALID')
    try:
        if str(UUID(value))!=value:raise ValueError
    except (ValueError,AttributeError):raise VectorError('VECTOR_POINT_ID_INVALID') from None
    return value


def _scope(value):
    if not isinstance(value,str) or not value or len(value)>4096:
        raise VectorError('VECTOR_PAYLOAD_INVALID')
    return value


def _payload(value):
    if not isinstance(value,dict) or value.keys()!=PAYLOAD_KEYS:
        raise VectorError('VECTOR_PAYLOAD_INVALID')
    return {key:_scope(item) for key,item in value.items()}


def _vector(value,dimension=None):
    if not isinstance(value,list) or not 1<=len(value)<=32768:
        raise VectorError('VECTOR_INTEGRITY_ERROR')
    if dimension is not None and len(value)!=dimension:raise VectorError('VECTOR_DIMENSION_MISMATCH')
    try:
        valid=all(not isinstance(n,bool) and isinstance(n,(int,float)) and math.isfinite(n) for n in value)
    except (ValueError,OverflowError):valid=False
    if not valid or not any(n!=0 for n in value):raise VectorError('VECTOR_INTEGRITY_ERROR')
    return list(value)


class VectorStore:
    def __init__(self,base_url,*,auth_headers=None,verify=True,transport=None,allow_live=False,
                 abort_check=lambda:False,timeout_seconds=30,max_response_bytes=16*1024*1024,
                 max_request_bytes=16*1024*1024):
        self.base_url=canonical_endpoint(base_url)
        self.headers=dict(auth_headers or {})
        self.verify,self.transport,self.allow_live=verify,transport,allow_live
        self.abort_check=abort_check
        if (isinstance(timeout_seconds,bool) or not isinstance(timeout_seconds,(int,float))
                or not math.isfinite(timeout_seconds) or timeout_seconds<=0
                or not _integer(max_response_bytes,1,64*1024*1024)
                or not _integer(max_request_bytes,1,64*1024*1024)):
            raise VectorError('VECTOR_LIMIT_INVALID')
        self.timeout_seconds,self.max_response_bytes,self.max_request_bytes=timeout_seconds,max_response_bytes,max_request_bytes
        self._dimensions={}

    def _abort(self):
        # A lease fence can raise LeaseLost directly; do not convert it.
        if self.abort_check():raise VectorError('ABORTED',stop_state='PAUSED')

    def _collection(self,name):
        if not isinstance(name,str) or re.fullmatch(r'almrag_[a-f0-9]{32}',name) is None:
            raise VectorError('VECTOR_COLLECTION_INVALID')
        return '/collections/'+name

    def _request(self,method,path,payload=None,*,missing_ok=False,wait=False):
        self._abort()
        if self.transport is None and not self.allow_live:raise VectorError('VECTOR_NETWORK_DISABLED')
        body=None
        if payload is not None:
            try:body=json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
            except (TypeError,ValueError,OverflowError):raise VectorError('VECTOR_REQUEST_INVALID') from None
            if len(body)>self.max_request_bytes:raise VectorError('VECTOR_REQUEST_TOO_LARGE')
        started=time.monotonic()
        def check():
            self._abort()
            if time.monotonic()-started>self.timeout_seconds:
                raise VectorError('VECTOR_DEADLINE_EXCEEDED',stop_state='PAUSED')
        try:
            headers=dict(self.headers)
            if body is not None:headers['Content-Type']='application/json'
            with httpx.Client(transport=self.transport,timeout=self.timeout_seconds,verify=self.verify,
                              follow_redirects=False,trust_env=False) as client:
                with client.stream(method,self.base_url+path,content=body,headers=headers,
                                   params={'wait':'true'} if wait else None) as response:
                    check()
                    status=response.status_code
                    if 300<=status<400:raise VectorError('VECTOR_REDIRECT_FORBIDDEN')
                    if status in {401,403}:raise VectorError('VECTOR_AUTH_FAILED')
                    if status==429 or status>=500:raise VectorError('VECTOR_SERVER_PAUSED',stop_state='PAUSED')
                    if status==404 and missing_ok:return None
                    if status in {400,404,409,413,422}:raise VectorError('VECTOR_REQUEST_REJECTED')
                    if status!=200:raise VectorError('VECTOR_UNAVAILABLE')
                    data=bytearray()
                    for part in response.iter_bytes():
                        check()
                        if len(data)+len(part)>self.max_response_bytes:raise VectorError('VECTOR_RESPONSE_TOO_LARGE')
                        data.extend(part)
            check()
            def invalid_constant(value):raise ValueError('nonfinite JSON')
            value=json.loads(data,parse_constant=invalid_constant)
            if not isinstance(value,dict) or value.get('status')!='ok' or 'result' not in value:
                raise VectorError('VECTOR_RESPONSE_SCHEMA_MISMATCH')
            return value['result']
        except (VectorError,LeaseLost):raise
        except httpx.HTTPError:raise VectorError('VECTOR_TRANSPORT_ERROR',stop_state='PAUSED') from None
        except (ValueError,UnicodeError,OSError,RecursionError):
            raise VectorError('VECTOR_RESPONSE_SCHEMA_MISMATCH') from None

    def ensure_collection(self,name,dimension):
        path=self._collection(name)
        if not _integer(dimension,1,32768):raise VectorError('VECTOR_DIMENSION_INVALID')
        result=self._request('GET',path,missing_ok=True)
        if result is None:
            created=self._request('PUT',path,{'vectors':{'size':dimension,'distance':'Cosine'}})
            if created is not True:raise VectorError('VECTOR_COLLECTION_CREATE_FAILED')
            result=self._request('GET',path)
        try:vectors=result['config']['params']['vectors']
        except (KeyError,TypeError):raise VectorError('VECTOR_RESPONSE_SCHEMA_MISMATCH') from None
        if (not isinstance(vectors,dict) or not _integer(vectors.get('size'),1,32768)
                or vectors['size']!=dimension or vectors.get('distance')!='Cosine'):
            raise VectorError('VECTOR_COLLECTION_MISMATCH')
        self._dimensions[name]=dimension

    def upsert(self,name,points):
        path=self._collection(name)
        if not isinstance(points,list) or len(points)>1000:raise VectorError('VECTOR_BATCH_INVALID')
        cleaned=[];seen=set();dimension=self._dimensions.get(name)
        for point in points:
            if not isinstance(point,dict) or point.keys()!={'id','vector','payload'}:
                raise VectorError('VECTOR_POINT_INVALID')
            point_id=_identifier(point['id'])
            if point_id in seen:raise VectorError('VECTOR_POINT_DUPLICATE')
            seen.add(point_id)
            vector=_vector(point['vector'],dimension)
            dimension=len(vector)
            cleaned.append({'id':point_id,'vector':vector,'payload':_payload(point['payload'])})
        if not cleaned:return
        result=self._request('PUT',path+'/points',{'points':cleaned},wait=True)
        if not isinstance(result,dict) or result.get('status')!='completed':
            raise VectorError('VECTOR_WRITE_NOT_COMPLETED')

    def retrieve(self,name,ids):
        path=self._collection(name)
        if not isinstance(ids,list) or len(ids)>1000:raise VectorError('VECTOR_BATCH_INVALID')
        expected={_identifier(point_id) for point_id in ids}
        if len(expected)!=len(ids):raise VectorError('VECTOR_POINT_DUPLICATE')
        if not ids:return []
        result=self._request('POST',path+'/points',{'ids':ids,'with_payload':True,'with_vector':True})
        if not isinstance(result,list):raise VectorError('VECTOR_RESPONSE_SCHEMA_MISMATCH')
        if len(result)>len(ids):raise VectorError('VECTOR_RESPONSE_SCHEMA_MISMATCH')
        cleaned=[];seen=set()
        for point in result:
            if not isinstance(point,dict):raise VectorError('VECTOR_RESPONSE_SCHEMA_MISMATCH')
            point_id=_identifier(point.get('id'))
            if point_id in seen or point_id not in expected:raise VectorError('VECTOR_POINT_SET_MISMATCH')
            seen.add(point_id)
            cleaned.append({'id':point_id,'vector':_vector(point.get('vector'),self._dimensions.get(name)),
                            'payload':_payload(point.get('payload'))})
        # Missing IDs are retained as absence; the publication caller compares exact coverage.
        return cleaned

    def query(self,name,vector,*,project_uid,generation_uid,limit,offset=0,item_uids=None):
        path=self._collection(name)
        project_uid,generation_uid=_scope(project_uid),_scope(generation_uid)
        if not _integer(limit,1,10000) or not _integer(offset,0,1000000):raise VectorError('VECTOR_QUERY_LIMIT_INVALID')
        must=[{'key':'project_uid','match':{'value':project_uid}},
              {'key':'generation_uid','match':{'value':generation_uid}}]
        if item_uids is not None:
            if not isinstance(item_uids,list) or len(item_uids)>10000 or any(not isinstance(x,str) or not x or len(x)>1024 for x in item_uids):raise VectorError('VECTOR_ITEM_FILTER_INVALID')
            if not item_uids:return []
            must.append({'key':'item_uid','match':{'any':item_uids}})
        result=self._request('POST',path+'/points/query',{
            'query':_vector(vector,self._dimensions.get(name)),
            'filter':{'must':must},
            'limit':limit,'offset':offset,'with_payload':True,'with_vector':False})
        if not isinstance(result,dict) or not isinstance(result.get('points'),list) or len(result['points'])>limit:
            raise VectorError('VECTOR_RESPONSE_SCHEMA_MISMATCH')
        cleaned=[];seen=set()
        for point in result['points']:
            if not isinstance(point,dict):raise VectorError('VECTOR_RESPONSE_SCHEMA_MISMATCH')
            point_id=_identifier(point.get('id'));payload=_payload(point.get('payload'))
            if point_id in seen:raise VectorError('VECTOR_POINT_DUPLICATE')
            seen.add(point_id)
            if payload['project_uid']!=project_uid or payload['generation_uid']!=generation_uid or (item_uids is not None and payload['item_uid'] not in item_uids):
                raise VectorError('VECTOR_SCOPE_MISMATCH')
            score=point.get('score')
            try:valid_score=not isinstance(score,bool) and isinstance(score,(int,float)) and math.isfinite(score)
            except (ValueError,OverflowError):valid_score=False
            if not valid_score:
                raise VectorError('VECTOR_RESPONSE_SCHEMA_MISMATCH')
            cleaned.append({'id':point_id,'score':score,'payload':payload})
        return cleaned

    def delete_collection(self,name):
        result=self._request('DELETE',self._collection(name),missing_ok=True)
        if result is False:
            # Qdrant may return 200/false for a repeated delete. Prove absence
            # before accepting the idempotent cleanup; false alone is not proof.
            if self._request('GET',self._collection(name),missing_ok=True) is not None:
                raise VectorError('VECTOR_COLLECTION_DELETE_FAILED')
        elif result is not None and result is not True:raise VectorError('VECTOR_COLLECTION_DELETE_FAILED')
        self._dimensions.pop(name,None)
