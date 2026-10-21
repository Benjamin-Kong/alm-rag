"""SRS-033/034/039/058: project-bound quality jobs/datasets and report authorization."""
from test_m2_api import env,register,project

class Quality:
    def __init__(self):self.calls=[]
    def stage_dataset(self,p,payload):
        self.calls.append(('stage',p,payload));return dict(dataset_ref='dataset',project_uid=p,case_count=1,sha256='a'*64)
    def enqueue_integrity(self,p):
        self.calls.append(('integrity',p));return dict(job_id='job',project_uid=p,stage='INTEGRITY',state='QUEUED')
    def enqueue_evaluation(self,p,ref,**kw):
        self.calls.append(('evaluate',p,ref,kw));return dict(job_id='job',project_uid=p,stage='EVALUATE',state='QUEUED')
    def report(self,job):
        self.calls.append(('report',job));return self.result

def test_quality_api_requires_project_manage_before_any_service_call(env):
    app,c,h,db,calls=env;p=project(env,register(env));q=Quality();app.state.quality=q
    _,reader=app.state.security.create_key('r',[p],['project_read'],actor='admin')
    _,manager=app.state.security.create_key('m',[p],['project_read','project_manage'],actor='admin')
    _,foreign=app.state.security.create_key('x',['other'],['project_read','project_manage'],actor='admin');c.cookies.clear()
    body={'cases':[{'query':'brake','relevant_item_uids':['item']}]};base='/api/v1/projects/'+p
    for suffix,payload in [('/integrity',{}),('/evaluation-datasets',body),('/evaluations',{'project_uids':[p],'dataset_ref':'dataset'})]:
        assert c.post(base+suffix,json=payload,headers={'X-API-Key':reader}).status_code==403
        assert c.post(base+suffix,json=payload,headers={'X-API-Key':foreign}).status_code==404
    assert not q.calls
    mh={'X-API-Key':manager}
    assert c.post(base+'/integrity',json={},headers=mh).status_code==202
    assert c.post(base+'/evaluation-datasets',json=body,headers=mh).json()['case_count']==1
    assert c.post(base+'/evaluations',json={'project_uids':[p],'dataset_ref':'dataset'},headers=mh).status_code==202
    before=len(q.calls)
    assert c.post(base+'/evaluations',json={'project_uids':[p,'other'],'dataset_ref':'dataset'},headers=mh).status_code==422
    assert c.post(base+'/evaluation-datasets',json={'cases':[{'query':'','relevant_item_uids':[]}]},headers=mh).status_code==422
    assert c.post(base+'/evaluations',json={'project_uids':[p],'dataset_ref':'https://foreign.invalid'},headers=mh).status_code==422
    assert len(q.calls)==before

def test_quality_report_owner_checked_before_service_or_missing_job_disclosure(env):
    from almrag.queue import Queue
    app,c,h,db,calls=env;p=project(env,register(env));q=Quality();app.state.quality=q;job=Queue(db).enqueue(p,'INTEGRITY')
    q.result=dict(job_id=job['job_id'],project_uid=p,stage='INTEGRITY',status='NOT VERIFIED',report={'source':'NOT VERIFIED'})
    _,reader=app.state.security.create_key('r',[p],['project_read'],actor='admin')
    _,foreign=app.state.security.create_key('x',['other'],['project_read'],actor='admin');c.cookies.clear()
    path='/api/v1/jobs/'+job['job_id']+'/quality-report'
    assert c.get(path,headers={'X-API-Key':foreign}).status_code==404 and not q.calls
    assert c.get(path,headers={'X-API-Key':reader}).json()['status']=='NOT VERIFIED'
    q.result['project_uid']='other'
    assert c.get(path,headers={'X-API-Key':reader}).status_code==503

def test_evaluation_top_k_rejects_boolean_instead_of_coercing_to_one(env):
    app,c,h,db,calls=env;p=project(env,register(env));q=Quality();app.state.quality=q
    response=c.post(f'/api/v1/projects/{p}/evaluations',headers=h,json={'project_uids':[p],'dataset_ref':'dataset','top_k':True})
    assert response.status_code==422 and not q.calls
