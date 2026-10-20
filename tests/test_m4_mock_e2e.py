"""SRS-018/019/021/024/049/055/056: real API/FIFO/SQLite with synthetic adapters."""
from fastapi.testclient import TestClient
from test_pipeline import setup, collection_setup
from almrag.api import create_app
from almrag.config import Settings
from almrag.processing import ProcessingError
from almrag.retrieval import SearchService
from almrag.queue import Queue
from almrag.worker import run_once


def test_public_sync_100_three_failures_read_acl_replay_and_full_restoration(setup):
    db,adapter,project,runtime,pipeline,index=setup
    adapter.refs=[{'id':str(i),'scope_id':'t1','revision':'1'} for i in range(100)]
    original=runtime.embed
    def embed(text,**kw):
        if any(('Title '+str(i)+'\n') in text for i in (2,44,78)):
            raise ProcessingError('INPUT_REJECTED',False)
        return original(text,**kw)
    runtime.embed=embed
    vector=index.vector_store
    def query(collection,vector,*,project_uid,generation_uid,limit,offset=0,item_uids=None):
        points=[{'id':p['id'],'payload':p['payload'],'score':1.0} for p in index.vector_store.collections[collection].values()
                if p['payload']['project_uid']==project_uid and p['payload']['generation_uid']==generation_uid
                and (item_uids is None or p['payload']['item_uid'] in item_uids)]
        return sorted(points,key=lambda p:p['id'])[offset:offset+limit]
    vector.query=query
    search=SearchService(db,lambda _:runtime,vector,allow_fixture=True)
    app=create_app(Settings(database_path=str(db.path)),db=db,collection=pipeline.collection,
                   processing=pipeline.processing,indexing=index,search=search,pipeline=pipeline)
    _,manager=app.state.security.create_key('manager',[project],['project_manage','project_read','search'],actor='synthetic-admin')
    _,reader=app.state.security.create_key('reader',[project],['project_read'],actor='synthetic-admin')
    _,foreign=app.state.security.create_key('other',['foreign'],['project_read','project_manage','search'],actor='synthetic-admin')
    h={'X-API-Key':manager};rh={'X-API-Key':reader};fh={'X-API-Key':foreign}
    with TestClient(app,base_url='https://testserver') as client:
        pre=client.post(f'/api/v1/projects/{project}/pipeline-preflight',headers=h)
        assert pre.status_code==200 and pre.json()['sync_ready']
        queued=client.post(f'/api/v1/projects/{project}/jobs',headers=h,json={'stage':'SYNC','config_revision':pre.json()['config_revision']})
        assert queued.status_code==202,queued.text
        job_id=queued.json()['job_id']
        assert run_once(Queue(db),'mock-e2e',pipeline_service=pipeline)
        assert Queue(db).get_job(job_id)['state']=='COMPLETED_WITH_ERRORS'
        result=client.post('/api/v1/search',headers=h,json={'query':'Title','project_uids':[project],'top_k':100,'response':{'include_full_item':True}})
        assert result.status_code==200,result.text
        assert len(result.json()['results'])==97
        hit=result.json()['results'][0]
        detail=client.get('/api/v1/items/'+hit['item_uid'],headers=rh)
        assert detail.status_code==200 and detail.json()['item']==hit['item']
        assert hit['item']['fields'][0]['raw_value']=={'nested':['all','values']}
        assert client.get('/api/v1/items/'+hit['item_uid'],headers=fh).status_code==404
        base=f'/api/v1/jobs/{job_id}/failed-items'
        failures=client.get(base,headers=rh)
        assert failures.status_code==200 and len(failures.json())==3
        assert client.get(base,headers=fh).status_code==404
        assert client.post(base+'/retry',headers=rh).status_code==403
        runtime.embed=original
        adapter.get_item=lambda *args:(_ for _ in ()).throw(AssertionError('replay unexpectedly called ALM'))
        retries=client.post(base+'/retry',headers=h)
        assert retries.status_code==202,retries.text
        for replay in retries.json():
            assert run_once(Queue(db),'mock-replay',pipeline_service=pipeline)
            assert Queue(db).get_job(replay['job_id'])['state']=='SUCCEEDED'
        result=client.post('/api/v1/search',headers=h,json={'query':'Title','project_uids':[project],'top_k':100})
        assert result.status_code==200 and len(result.json()['results'])==100
        assert len({hit['item_uid'] for hit in result.json()['results']})==100
        with db.connect() as sql:
            assert sql.execute("SELECT count(*) FROM failed_items WHERE replay_state='RESOLVED'").fetchone()[0]==3
            assert sql.execute('SELECT count(*) FROM items WHERE active_revision_uid IS NOT NULL').fetchone()[0]==100
