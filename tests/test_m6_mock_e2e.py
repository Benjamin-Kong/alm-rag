"""SRS-033/034/039: actual SQLite/API/FIFO/quality with synthetic source/model/vector."""
from fastapi.testclient import TestClient
from test_pipeline import setup,collection_setup,run
from almrag.api import create_app
from almrag.config import Settings
from almrag.queue import Queue
from almrag.retrieval import SearchService
from almrag.worker import run_once
from almrag.quality import QualityService


def test_public_integrity_golden_evaluation_and_authorized_report(setup):
    db,adapter,p,runtime,pipeline,index=setup
    assert run(setup)[0]=='SUCCEEDED'
    vector=index.vector_store
    def query(collection,embedding,*,project_uid,generation_uid,limit,offset=0,item_uids=None):
        points=[{'id':x['id'],'payload':x['payload'],'score':1.0} for x in vector.collections[collection].values() if x['payload']['project_uid']==project_uid and x['payload']['generation_uid']==generation_uid and (item_uids is None or x['payload']['item_uid'] in item_uids)]
        return sorted(points,key=lambda x:x['id'])[offset:offset+limit]
    vector.query=query
    search=SearchService(db,lambda _:runtime,vector,allow_fixture=True)
    quality=QualityService(db,search,vector,attachment_root=pipeline.collection.attachment_root)
    app=create_app(Settings(database_path=str(db.path)),db=db,search=search,quality=quality)
    _,manager=app.state.security.create_key('m',[p],['project_read','project_manage'],actor='synthetic')
    _,other=app.state.security.create_key('x',['foreign'],['project_read','project_manage'],actor='synthetic')
    h={'X-API-Key':manager};fh={'X-API-Key':other};base=f'/api/v1/projects/{p}'
    with db.connect() as c:items=[r[0] for r in c.execute('SELECT item_uid FROM items WHERE project_uid=?',(p,))]
    with TestClient(app,base_url='https://testserver') as client:
        ds=client.post(base+'/evaluation-datasets',headers=h,json={'cases':[{'query':'Title','relevant_item_uids':items}]})
        assert ds.status_code==201,ds.text
        evaluation=client.post(base+'/evaluations',headers=h,json={'project_uids':[p],'dataset_ref':ds.json()['dataset_ref'],'top_k':10})
        assert evaluation.status_code==202,evaluation.text
        job=evaluation.json()['job_id'];path='/api/v1/jobs/'+job+'/quality-report'
        assert client.get(path,headers=h).status_code==409
        assert run_once(Queue(db),'quality-e2e',quality_service=quality)
        report=client.get(path,headers=h)
        assert report.status_code==200,report.text
        assert report.json()['status']=='PASS'
        metrics=report.json()['report']['methods']
        assert set(metrics)=={'dense','keyword','hybrid'}
        assert all(x['recall_at_k']==1 for x in metrics.values())
        assert client.get(path,headers=fh).status_code==404
        integrity=client.post(base+'/integrity',headers=h)
        assert integrity.status_code==202,integrity.text
        assert run_once(Queue(db),'integrity-e2e',quality_service=quality)
        ir=client.get('/api/v1/jobs/'+integrity.json()['job_id']+'/quality-report',headers=h)
        assert ir.status_code==200,ir.text
        assert ir.json()['status']=='NOT VERIFIED' # source observations are local; no actual ALM contacted
        with db.connect() as c:
            assert c.execute("SELECT count(*) FROM jobs WHERE stage IN ('INTEGRITY','EVALUATE') AND state='SUCCEEDED'").fetchone()[0]==2
