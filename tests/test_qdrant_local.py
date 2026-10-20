"""SRS-018/019/024: opt-in synthetic local Qdrant contract/integration only.

Set ALMRAG_TEST_QDRANT_URL=http://127.0.0.1:16333 to target the dedicated
throwaway test container. Never defaults to configured/production Qdrant.
"""
import json,os
from urllib.parse import urlsplit
from uuid import uuid4
import pytest
from almrag.vector_store import VectorStore,VectorError
from almrag.indexing import IndexService,collection_name_for
from almrag.retrieval import SearchService,SearchRequest
from almrag.processing import ProcessingPolicy
from almrag.chunking import ChunkConfig
from almrag.queue import Queue
from test_processing import setup,add_item,execute

URL=os.getenv('ALMRAG_TEST_QDRANT_URL')
pytestmark=pytest.mark.skipif(not URL,reason='dedicated synthetic local Qdrant not explicitly enabled')


@pytest.fixture
def vector():
    parsed=urlsplit(URL)
    assert parsed.scheme=='http' and parsed.hostname in {'localhost','127.0.0.1'} and parsed.port==16333 and not parsed.path and not parsed.query
    store=VectorStore(URL,auth_headers={'api-key':'synthetic-m4-only'},allow_live=True)
    created=[]
    original=store.ensure_collection
    def create(name,dimension):
        if name not in created:created.append(name)
        return original(name,dimension)
    store.ensure_collection=create
    try:yield store
    finally:
        for name in created:store.delete_collection(name)


def index_once(data,index,stage='INDEX'):
    db,_,p,_,_=data;queued=index.enqueue(p,stage);job=Queue(db).claim('local-qdrant',300)
    assert queued['job_id']==job['job_id']
    return index.run(job)


def test_real_qdrant_auth_point_roundtrip_and_scoped_query(vector):
    name=collection_name_for(str(uuid4()));vector.ensure_collection(name,2)
    def point(project,generation):
        payload={k:str(uuid4()) for k in ['project_uid','generation_uid','item_uid','revision_uid','chunk_uid','result_uid','content_hash','model_fingerprint','vector_digest']}
        payload.update(project_uid=project,generation_uid=generation)
        return {'id':str(uuid4()),'vector':[.6,.8],'payload':payload}
    p1,p2=point('project-a','generation-a'),point('project-b','generation-b')
    vector.upsert(name,[p1,p2]);vector.upsert(name,[p1])
    found=vector.retrieve(name,[p1['id'],p2['id']])
    assert {p['id'] for p in found}=={p1['id'],p2['id']}
    hits=vector.query(name,[.6,.8],project_uid='project-a',generation_uid='generation-a',limit=100)
    assert [h['id'] for h in hits]==[p1['id']]
    wrong=VectorStore(URL,auth_headers={'api-key':'invalid-synthetic'},allow_live=True)
    with pytest.raises(VectorError) as error:wrong.query(name,[.6,.8],project_uid='project-a',generation_uid='generation-a',limit=1)
    assert error.value.code=='VECTOR_AUTH_FAILED'


def test_real_qdrant_index_search_rebuild_and_live_reader_cleanup(setup,vector):
    db,i,p,r,processing=setup
    first=add_item(setup,description='한글 요구사항 SOME/IP-SD 30490 0x123 word '*50)
    execute(setup);execute(setup,'EMBED')
    index=IndexService(db,processing,vector);assert index_once(setup,index)=='SUCCEEDED'
    with db.connect() as c:old=c.execute('SELECT active_generation_uid FROM projects WHERE project_uid=?',(p,)).fetchone()[0]
    search=SearchService(db,lambda _:r,vector,allow_fixture=True)
    hit=search.search(SearchRequest(query='SOME/IP-SD',project_uids=[p],response={'include_full_item':True}),allowed_projects=[p])['results']
    assert len(hit)==1 and hit[0]['revision_uid']==first and hit[0]['item']['raw']=={'complete':'unselected'}
    before=len(r.calls)
    assert index_once(setup,index)=='SUCCEEDED' and len(r.calls)==before  # No content embeddings by INDEX.
    processing.configure(p,ProcessingPolicy(chunking=ChunkConfig(prefix='new generation')))
    execute(setup);execute(setup,'EMBED')
    with search.readers.snapshot([p]) as (_,pairs):
        assert pairs[p]==old
        assert index_once(setup,index,'REBUILD')=='SUCCEEDED'
        assert old not in index.cleanup()
        assert vector.query(collection_name_for(old),[1,2],project_uid=p,generation_uid=old,limit=100)
    assert old in index.cleanup()
    with db.connect() as c:
        assert c.execute('SELECT cleanup_state FROM generation_configs WHERE generation_uid=?',(old,)).fetchone()[0]=='DELETED'
        assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==1
    assert len(search.search(SearchRequest(query='word',project_uids=[p]),allowed_projects=[p])['results'])==1


def test_real_qdrant_stage_crash_recovery_has_no_duplicate_points(setup,vector):
    db,_,p,r,processing=setup;add_item(setup);execute(setup);execute(setup,'EMBED')
    class Crash(BaseException):pass
    def crash(event):
        if event=='after_dense':raise Crash()
    index=IndexService(db,processing,vector,fault_hook=crash);queued=index.enqueue(p);job=Queue(db).claim('old',300)
    with pytest.raises(Crash):index.run(job)
    with db.transaction() as c:
        assert c.execute('SELECT active_generation_uid FROM projects WHERE project_uid=?',(p,)).fetchone()[0] is None
        c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(job['job_id'],))
    index=IndexService(db,processing,vector);assert index.run(Queue(db).claim('new',300))=='SUCCEEDED'
    with db.connect() as c:
        generation=c.execute('SELECT active_generation_uid FROM projects WHERE project_uid=?',(p,)).fetchone()[0]
        ids=[row[0] for row in c.execute('SELECT point_uuid FROM index_points WHERE generation_uid=?',(generation,))]
    assert len(vector.query(collection_name_for(generation),[1,2],project_uid=p,generation_uid=generation,limit=100))==len(ids)
    assert {point['id'] for point in vector.retrieve(collection_name_for(generation),ids)}==set(ids)


def _crash_after_real_dense_write(path,project,url):
    from almrag.storage import Database
    from almrag.processing import ProcessingService
    from test_processing import Runtime
    db=Database(path);runtime=Runtime();processing=ProcessingService(db,lambda _:runtime,allow_fixture=True)
    store=VectorStore(url,auth_headers={'api-key':'synthetic-m4-only'},allow_live=True)
    def crash(event):
        if event=='after_dense':os._exit(91)
    service=IndexService(db,processing,store,fault_hook=crash)
    service.run(Queue(db).claim('crash-process',300))


def test_real_process_crash_after_qdrant_write_reclaims_same_points(setup,vector):
    import multiprocessing
    db,_,p,r,processing=setup;add_item(setup);execute(setup);execute(setup,'EMBED')
    index=IndexService(db,processing,vector);queued=index.enqueue(p)
    child=multiprocessing.get_context('spawn').Process(target=_crash_after_real_dense_write,args=(str(db.path),p,URL));child.start()
    try:
        child.join(15)
        assert child.exitcode==91
        with db.transaction() as c:
            assert c.execute('SELECT active_generation_uid FROM projects WHERE project_uid=?',(p,)).fetchone()[0] is None
            c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(queued['job_id'],))
        assert index.run(Queue(db).claim('recovered-process',300))=='SUCCEEDED'
        with db.connect() as c:
            generation=c.execute('SELECT active_generation_uid FROM projects WHERE project_uid=?',(p,)).fetchone()[0]
            expected=c.execute('SELECT count(*) FROM index_points WHERE generation_uid=?',(generation,)).fetchone()[0]
        assert len(vector.query(collection_name_for(generation),[1,2],project_uid=p,generation_uid=generation,limit=100))==expected
        assert Queue(db).get_job(queued['job_id'])['retry_count']==1
    finally:
        if child.is_alive():child.kill();child.join(10)


def test_real_qdrant_metadata_allowlist_is_applied_before_limit(vector):
    name=collection_name_for(str(uuid4()));vector.ensure_collection(name,2)
    project,generation=str(uuid4()),str(uuid4());points=[]
    for n in range(51):
        payload={k:str(uuid4()) for k in ['project_uid','generation_uid','item_uid','revision_uid','chunk_uid','result_uid','content_hash','model_fingerprint','vector_digest']}
        payload.update(project_uid=project,generation_uid=generation)
        points.append({'id':str(uuid4()),'vector':[.6,.8],'payload':payload})
    vector.upsert(name,points);target=points[-1]
    hits=vector.query(name,[.6,.8],project_uid=project,generation_uid=generation,limit=1,item_uids=[target['payload']['item_uid']])
    assert [hit['id'] for hit in hits]==[target['id']]
    assert vector.query(name,[.6,.8],project_uid=project,generation_uid=generation,limit=1,item_uids=[])==[]
