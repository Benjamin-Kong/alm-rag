"""SRS-018/019/023/024/028/033: bounded, scoped Qdrant REST contract."""
import json
from uuid import UUID

import httpx
import pytest

from almrag.vector_store import VectorError, VectorStore


COLLECTION='almrag_'+'a'*32
POINT_ID=str(UUID(int=1))
PAYLOAD={key:key+'-fixture' for key in (
    'project_uid','generation_uid','item_uid','revision_uid','chunk_uid',
    'result_uid','content_hash','model_fingerprint','vector_digest')}
POINT={'id':POINT_ID,'vector':[0.25,0.75],'payload':PAYLOAD}


def store(handler,**kwargs):
    return VectorStore('http://qdrant.test:6333',transport=httpx.MockTransport(handler),**kwargs)


def ok(result):
    return httpx.Response(200,json={'status':'ok','result':result})


def test_srs018_constructor_no_io_default_network_disabled():
    client=VectorStore('http://qdrant.test:6333')
    with pytest.raises(VectorError,match='VECTOR_NETWORK_DISABLED'):
        client.ensure_collection(COLLECTION,2)


def test_srs023_collection_create_verify_and_waited_upsert():
    calls=[]
    def handler(request):
        calls.append((request.method,request.url.path,dict(request.url.params),json.loads(request.content) if request.content else None))
        if request.method=='GET':
            if len(calls)==1:return httpx.Response(404,json={'status':{'error':'not found'}})
            return ok({'config':{'params':{'vectors':{'size':2,'distance':'Cosine'}}}})
        if request.url.path.endswith('/points'):return ok({'operation_id':1,'status':'completed'})
        return ok(True)
    client=store(handler)
    client.ensure_collection(COLLECTION,2)
    client.upsert(COLLECTION,[POINT])
    assert calls[1][3]=={'vectors':{'size':2,'distance':'Cosine'}}
    assert calls[-1][2]['wait']=='true'
    assert calls[-1][3]=={'points':[POINT]}


def test_srs033_retrieve_exact_vectors_and_payload():
    def handler(request):
        body=json.loads(request.content)
        assert body=={'ids':[POINT_ID],'with_payload':True,'with_vector':True}
        return ok([POINT])
    assert store(handler).retrieve(COLLECTION,[POINT_ID])==[POINT]


def test_srs019_project_generation_prefilter_before_limit():
    def handler(request):
        assert request.url.path==f'/collections/{COLLECTION}/points/query'
        body=json.loads(request.content)
        assert body['filter']=={'must':[
            {'key':'project_uid','match':{'value':PAYLOAD['project_uid']}},
            {'key':'generation_uid','match':{'value':PAYLOAD['generation_uid']}}]}
        assert body['limit']==5 and body['offset']==3
        assert body['with_payload'] is True and body['with_vector'] is False
        return ok({'points':[dict(POINT,score=0.8)]})
    result=store(handler).query(COLLECTION,[0.25,0.75],project_uid=PAYLOAD['project_uid'],generation_uid=PAYLOAD['generation_uid'],limit=5,offset=3)
    assert result==[{'id':POINT_ID,'score':0.8,'payload':PAYLOAD}]


@pytest.mark.parametrize('name',['other','almrag_'+'A'*32,COLLECTION+'/../other','https://secret.test'])
def test_srs028_internal_names_only_before_http(name):
    client=store(lambda r:pytest.fail('invalid collection reached HTTP'))
    with pytest.raises(VectorError,match='VECTOR_COLLECTION_INVALID'):
        client.delete_collection(name)


@pytest.mark.parametrize('status,code,state',[(302,'VECTOR_REDIRECT_FORBIDDEN','BLOCKED'),(401,'VECTOR_AUTH_FAILED','BLOCKED'),(403,'VECTOR_AUTH_FAILED','BLOCKED'),(429,'VECTOR_SERVER_PAUSED','PAUSED'),(503,'VECTOR_SERVER_PAUSED','PAUSED'),(400,'VECTOR_REQUEST_REJECTED','BLOCKED')])
def test_srs028_status_errors_sanitized_before_body(status,code,state):
    client=store(lambda r:httpx.Response(status,text='secret token customer body',headers={'location':'https://secret.test'}))
    with pytest.raises(VectorError) as exc:client.retrieve(COLLECTION,[POINT_ID])
    assert str(exc.value)==code and exc.value.global_error is True and exc.value.stop_state==state


@pytest.mark.parametrize('vectors',[{'size':3,'distance':'Cosine'},{'size':2,'distance':'Dot'},{'named':{'size':2,'distance':'Cosine'}}])
def test_srs024_collection_config_mismatch_blocks(vectors):
    client=store(lambda r:ok({'config':{'params':{'vectors':vectors}}}))
    with pytest.raises(VectorError,match='VECTOR_COLLECTION_MISMATCH'):client.ensure_collection(COLLECTION,2)


@pytest.mark.parametrize('mutate',[
    lambda p:p.update(vector=[float('nan'),1]),
    lambda p:p.update(vector=[True,1]),
    lambda p:p.update(vector=[0,0]),
    lambda p:p.update(id='../../foreign'),
    lambda p:p['payload'].pop('revision_uid'),
    lambda p:p['payload'].update(raw_body='secret'),
])
def test_srs033_invalid_point_rejected_before_network(mutate):
    point=json.loads(json.dumps(POINT));mutate(point)
    with pytest.raises(VectorError):store(lambda r:pytest.fail('invalid point reached HTTP')).upsert(COLLECTION,[point])


def test_srs033_duplicate_or_foreign_retrieval_rejected():
    for points in [[POINT,POINT],[dict(POINT,id=str(UUID(int=2)))],[dict(POINT,vector={'named':[1,2]})]]:
        with pytest.raises(VectorError):store(lambda r:ok(points)).retrieve(COLLECTION,[POINT_ID])


def test_srs019_foreign_query_result_rejected():
    point=dict(POINT,score=0.8,payload=dict(PAYLOAD,project_uid='foreign'))
    with pytest.raises(VectorError,match='VECTOR_SCOPE_MISMATCH'):
        store(lambda r:ok({'points':[point]})).query(COLLECTION,[1,2],project_uid=PAYLOAD['project_uid'],generation_uid=PAYLOAD['generation_uid'],limit=5)


def test_srs033_waited_write_requires_completed():
    with pytest.raises(VectorError,match='VECTOR_WRITE_NOT_COMPLETED'):
        store(lambda r:ok({'operation_id':1,'status':'acknowledged'})).upsert(COLLECTION,[POINT])


def test_srs028_response_size_schema_transport_and_abort():
    with pytest.raises(VectorError,match='VECTOR_RESPONSE_TOO_LARGE'):
        store(lambda r:ok([POINT]),max_response_bytes=10).retrieve(COLLECTION,[POINT_ID])
    for body in ['not-json','[]','{"status":"ok","result":{}}']:
        with pytest.raises(VectorError,match='VECTOR_RESPONSE_SCHEMA_MISMATCH'):
            store(lambda r:httpx.Response(200,text=body)).retrieve(COLLECTION,[POINT_ID])
    def broken(request):raise httpx.ConnectError('secret host',request=request)
    with pytest.raises(VectorError,match='VECTOR_TRANSPORT_ERROR') as exc:store(broken).retrieve(COLLECTION,[POINT_ID])
    assert exc.value.stop_state=='PAUSED'
    with pytest.raises(VectorError,match='ABORTED'):
        store(lambda r:pytest.fail('aborted request'),abort_check=lambda:True).retrieve(COLLECTION,[POINT_ID])


def test_srs024_delete_internal_generation_only():
    calls=[]
    def handler(request):calls.append((request.method,request.url.path));return ok(True)
    store(handler).delete_collection(COLLECTION)
    assert calls==[('DELETE',f'/collections/{COLLECTION}')]


def test_srs033_unrepresentable_score_sanitized():
    point=dict(POINT,score=10**400)
    with pytest.raises(VectorError,match='VECTOR_RESPONSE_SCHEMA_MISMATCH'):
        store(lambda r:ok({'points':[point]})).query(COLLECTION,[1,2],project_uid=PAYLOAD['project_uid'],generation_uid=PAYLOAD['generation_uid'],limit=5)


def test_srs026_deadline_and_lease_loss_preserved(monkeypatch):
    from almrag import vector_store
    from almrag.queue import LeaseLost
    ticks=iter([0,31])
    monkeypatch.setattr(vector_store.time,'monotonic',lambda:next(ticks))
    with pytest.raises(VectorError,match='VECTOR_DEADLINE_EXCEEDED') as exc:
        store(lambda r:ok([POINT])).retrieve(COLLECTION,[POINT_ID])
    assert exc.value.stop_state=='PAUSED'
    monkeypatch.undo()
    def lost():raise LeaseLost('fixture')
    with pytest.raises(LeaseLost):store(lambda r:pytest.fail('lost lease reached network'),abort_check=lost).retrieve(COLLECTION,[POINT_ID])


def test_srs028_auth_checked_without_consuming_body():
    class SecretStream(httpx.SyncByteStream):
        def __iter__(self):pytest.fail('protected error body consumed')
    with pytest.raises(VectorError,match='VECTOR_AUTH_FAILED'):
        store(lambda r:httpx.Response(401,stream=SecretStream())).retrieve(COLLECTION,[POINT_ID])


def test_srs033_request_and_batch_bounds():
    client=store(lambda r:pytest.fail('oversized request reached network'),max_request_bytes=1)
    with pytest.raises(VectorError,match='VECTOR_REQUEST_TOO_LARGE'):client.upsert(COLLECTION,[POINT])
    with pytest.raises(VectorError,match='VECTOR_BATCH_INVALID'):client.retrieve(COLLECTION,[POINT_ID]*1001)
    with pytest.raises(VectorError,match='VECTOR_POINT_DUPLICATE'):client.upsert(COLLECTION,[POINT,POINT])
    assert client.retrieve(COLLECTION,[])==[]
    assert client.upsert(COLLECTION,[]) is None


def test_srs024_known_dimension_prevents_invalid_write():
    calls=[]
    def handler(request):
        calls.append(request)
        return ok({'config':{'params':{'vectors':{'size':3,'distance':'Cosine'}}}})
    client=store(handler);client.ensure_collection(COLLECTION,3)
    with pytest.raises(VectorError,match='VECTOR_DIMENSION_MISMATCH'):client.upsert(COLLECTION,[POINT])
    assert len(calls)==1


def test_srs024_delete_retry_accepts_false_only_after_confirming_absence():
    calls=[]
    def missing(request):
        calls.append(request.method)
        return ok(False) if request.method=='DELETE' else httpx.Response(404)
    store(missing).delete_collection(COLLECTION)
    assert calls==['DELETE','GET']
    def still_present(request):return ok(False) if request.method=='DELETE' else ok({'config':{}})
    with pytest.raises(VectorError,match='VECTOR_COLLECTION_DELETE_FAILED'):
        store(still_present).delete_collection(COLLECTION)


def test_query_item_filter_is_sent_before_limit_and_empty_skips_network():
    import httpx,json
    from uuid import uuid4
    from almrag.vector_store import VectorStore
    calls=[];item=str(uuid4());project=str(uuid4());generation=str(uuid4())
    def handler(request):
        calls.append(json.loads(request.content));return httpx.Response(200,json={'status':'ok','result':{'points':[]}})
    store=VectorStore('https://vector.invalid',transport=httpx.MockTransport(handler))
    name='almrag_'+uuid4().hex
    assert store.query(name,[1.,0.],project_uid=project,generation_uid=generation,limit=1,item_uids=[item])==[]
    assert calls[0]['filter']['must'][-1]=={'key':'item_uid','match':{'any':[item]}}
    assert store.query(name,[1.,0.],project_uid=project,generation_uid=generation,limit=1,item_uids=[])==[]
    assert len(calls)==1
