"""SRS-009/014/040/041/053: processing API keeps existing ACL and offline boundary."""
from test_m2_api import env,register,project

class Processing:
    def __init__(self):self.calls=[]
    def get_config(self,p):return {'project_uid':p,'policy':{'fields':None,'scope_fields':{},'chunking':None},'effective_policy':{'fields':[],'chunking':{}},'config_revision':'pinned','instance_uid':'i','instance_policy':{}}
    def configure(self,p,policy):self.calls.append(('configure',p,policy));return self.get_config(p)
    def configure_instance(self,i,policy):self.calls.append(('instance',i,policy));return policy
    def preflight(self,p):return {'status':'BLOCKED','process_ready':False,'embed_ready':False,'sync_ready':False,'config_revision':None,'estimated_items':0,'diagnostics':['MODEL_PROFILE_UNCONFIGURED']}
    def enqueue(self,p,stage,config_revision=None):
        self.calls.append((stage,p,config_revision));return {'job_id':'processing','project_uid':p,'stage':stage,'state':'QUEUED'}


def test_processing_routes_offline_acl_and_typed_fields(env):
    app,c,h,db,calls=env;uid=register(env);p=project(env,uid)
    fake=Processing();app.state.processing=fake;before=len(calls)
    path=f'/api/v1/projects/{p}/processing-config'
    assert c.get(path).status_code==200
    assert c.put(path,headers=h,json={'fields':[{'kind':'SOURCE','key':'title'}]}).status_code==200
    assert c.put(path,headers=h,json={'fields':[{'kind':'NORMALIZED','key':'unknown'}]}).status_code==422
    assert c.post(f'/api/v1/projects/{p}/processing-preflight',headers=h).json()['diagnostics']==['MODEL_PROFILE_UNCONFIGURED']
    assert c.put(path,json={}).status_code==403
    _,reader=app.state.security.create_key('r',[p],['project_read'],actor='admin')
    _,manager=app.state.security.create_key('m',[p],['project_read','project_manage','system_admin'],actor='admin')
    c.cookies.clear()
    assert c.get(path,headers={'X-API-Key':reader}).status_code==200
    for suffix in ['processing-config','processing-preflight']:
        method='PUT' if suffix.endswith('config') else 'POST'
        assert c.request(method,f'/api/v1/projects/{p}/{suffix}',headers={'X-API-Key':reader},json={}).status_code==403
        assert c.request(method,f'/api/v1/projects/foreign/{suffix}',headers={'X-API-Key':manager},json={}).status_code==404
    assert c.put(f'/api/v1/alm-instances/{uid}/processing-defaults',headers={'X-API-Key':manager},json={}).status_code==403
    assert len(calls)==before


def test_processing_stage_dispatch_keeps_index_and_sync_blocked(env):
    app,c,h,db,calls=env;p=project(env,register(env));fake=Processing();app.state.processing=fake
    for stage in ['PROCESS','EMBED']:
        response=c.post(f'/api/v1/projects/{p}/jobs',headers=h,json={'stage':stage,'config_revision':'pinned'})
        assert response.status_code==202,response.text
        assert fake.calls[-1]==(stage,p,'pinned')
    for stage in ['SYNC','INDEX','REBUILD_INDEX']:
        assert c.post(f'/api/v1/projects/{p}/jobs',headers=h,json={'stage':stage}).status_code==409


def test_default_processing_runtime_blocks_without_alm_calls(env):
    app,c,h,db,calls=env;p=project(env,register(env));before=len(calls)
    response=c.post(f'/api/v1/projects/{p}/processing-preflight',headers=h)
    assert response.status_code==200,response.text
    assert response.json()['status']=='BLOCKED'
    assert 'MODEL_PROFILE_UNCONFIGURED' in response.json()['diagnostics']
    response=c.post(f'/api/v1/projects/{p}/jobs',headers=h,json={'stage':'PROCESS'})
    assert response.status_code==409 and response.json()['code']=='MODEL_PROFILE_UNCONFIGURED'
    assert len(calls)==before


def test_processing_contract_typed_results(env):
    app,*_=env
    spec=app.openapi()
    operation=spec['paths']['/api/v1/projects/{project_uid}/processing-preflight']['post']
    assert operation['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/ProcessingPreflightInfo')
    assert operation['x-implementation-status']=='M3_IMPLEMENTED'
