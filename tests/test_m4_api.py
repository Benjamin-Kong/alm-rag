"""SRS-018/019/021/049: search scopes checked before service and detail restoration."""
from test_m2_api import env,register,project

class Search:
    def __init__(self):self.calls=[]
    def search(self,payload,*,allowed_projects):
        self.calls.append((payload,allowed_projects));return {'total':0,'results':[],'exhausted':True,'backfill_limited':False,'rounds':1,'unindexed_project_uids':payload.project_uids}
    def item_detail(self,p,item,*,allowed_projects):
        self.calls.append((p,item,allowed_projects));return {'project_uid':p,'item_uid':item,'revision_uid':'revision','source_revision':'1','item':{'title':'Synthetic'},'content_blocks':[]}


def test_search_key_acl_checks_precede_service_and_type_validation(env):
    app,c,h,db,calls=env;p=project(env,register(env));fake=Search();app.state.search=fake
    _,reader=app.state.security.create_key('reader',[p],['project_read'],actor='admin')
    _,searcher=app.state.security.create_key('search',[p],['search'],actor='admin')
    c.cookies.clear()
    assert c.post('/api/v1/search',headers={'X-API-Key':reader},json={'query':'x','project_uids':[p]}).status_code==403
    assert c.post('/api/v1/search',headers={'X-API-Key':searcher},json={'query':'x','project_uids':['foreign']}).status_code==403
    assert fake.calls==[]
    for body in [{'query':'x'},{'query':'x','project_uids':[]},{'query':'x','project_uids':[p,p]},{'query':'x','project_uids':[p],'top_k':101}]:
        assert c.post('/api/v1/search',headers={'X-API-Key':searcher},json=body).status_code==422
    result=c.post('/api/v1/search',headers={'X-API-Key':searcher},json={'query':'한글 SOME/IP-SD','project_uids':[p]})
    assert result.status_code==200,result.text
    assert fake.calls[-1][1]==[p] and result.json()['results']==[]


def test_active_item_detail_preserves_project_read_without_expanding_grants(env):
    app,c,h,db,calls=env;p=project(env,register(env));fake=Search();app.state.search=fake
    from almrag.storage import canonical_uid
    item=canonical_uid('item',p,'100')
    with db.transaction() as sql:sql.execute('INSERT INTO items(item_uid,project_uid,source_item_id) VALUES(?,?,?)',(item,p,'100'))
    _,reader=app.state.security.create_key('reader',[p],['project_read'],actor='admin')
    _,foreign=app.state.security.create_key('foreign',['unrelated'],['project_read'],actor='admin')
    c.cookies.clear()
    assert c.get('/api/v1/items/'+item,headers={'X-API-Key':foreign}).status_code==404
    assert not fake.calls
    result=c.get('/api/v1/items/'+item,headers={'X-API-Key':reader})
    assert result.status_code==200 and result.json()['item']['title']=='Synthetic'
    assert c.get('/api/v1/items/unknown',headers={'X-API-Key':reader}).status_code==404


def test_default_unindexed_search_performs_no_source_or_model_network(env):
    app,c,h,db,calls=env;p=project(env,register(env));before=len(calls)
    response=c.post('/api/v1/search',headers=h,json={'query':'word','project_uids':[p]})
    assert response.status_code==200,response.text
    assert response.json()['unindexed_project_uids']==[p] and response.json()['results']==[]
    assert len(calls)==before


class Index:
    def __init__(self):self.calls=[]
    def preflight(self,p,stage='INDEX'):
        self.calls.append(('preflight',p,stage));return {'status':'READY','index_ready':True,'rebuild_ready':True,'config_revision':'pinned','estimated_items':1,'diagnostics':[]}
    def enqueue(self,p,stage='INDEX',config_revision=None):
        self.calls.append((stage,p,config_revision));return {'job_id':'index','project_uid':p,'stage':stage,'state':'QUEUED'}


def test_index_and_rebuild_routes_keep_existing_project_manage_scope(env):
    app,c,h,db,calls=env;p=project(env,register(env));fake=Index();app.state.indexing=fake
    pre=c.post(f'/api/v1/projects/{p}/index-preflight?stage=REBUILD_INDEX',headers=h)
    assert pre.status_code==200 and pre.json()['config_revision']=='pinned'
    assert fake.calls[-1]==('preflight',p,'REBUILD')
    for stage,internal in [('INDEX','INDEX'),('REBUILD_INDEX','REBUILD')]:
        result=c.post(f'/api/v1/projects/{p}/jobs',headers=h,json={'stage':stage,'config_revision':'pinned'})
        assert result.status_code==202,result.text
        assert fake.calls[-1]==(internal,p,'pinned')
    _,reader=app.state.security.create_key('reader',[p],['project_read'],actor='admin')
    c.cookies.clear();before=len(fake.calls)
    assert c.post(f'/api/v1/projects/{p}/index-preflight',headers={'X-API-Key':reader}).status_code==403
    assert len(fake.calls)==before


class Pipeline:
    def __init__(self,p):self.p=p;self.calls=[]
    def preflight(self,p):
        self.calls.append(('preflight',p));return dict(status='READY',sync_ready=True,config_revision='pinned',estimated_items=1,diagnostics=[])
    def enqueue(self,p,stage='SYNC',config_revision=None):
        self.calls.append(('enqueue',p,stage,config_revision));return dict(job_id='sync',project_uid=p,stage=stage,state='QUEUED')
    def list_failures(self,j,limit=100,offset=0):
        self.calls.append(('list',j,limit,offset));return [dict(failed_item_uid=None,job_id=j,project_uid=self.p,item_uid=None,source_item_id='synthetic',revision_uid=None,failed_stage='COLLECT',error_code='HTTP_503',retryable=1,replay_state='PENDING')]
    def retry(self,j,item,**kw):
        self.calls.append(('retry',j,item,kw));return dict(job_id='replay',project_uid=self.p,stage='REPLAY',state='QUEUED')
    def retry_all(self,j,**kw):return [self.retry(j,'synthetic',**kw)]
    def resume(self,j):
        self.calls.append(('resume',j));return dict(job_id=j,project_uid=self.p,stage='SYNC',state='QUEUED')


def pipeline_env(env):
    from almrag.queue import Queue
    app,c,h,db,calls=env;p=project(env,register(env));fake=Pipeline(p);app.state.pipeline=fake
    job=Queue(db).enqueue(p,'SYNC')['job_id']
    return app,c,h,db,p,fake,job


def test_pipeline_preflight_sync_dispatch_and_alias(env):
    app,c,h,db,p,fake,j=pipeline_env(env)
    pre=c.post(f'/api/v1/projects/{p}/pipeline-preflight',headers=h)
    assert pre.status_code==200,pre.text
    assert pre.json()['sync_ready'] is True
    response=c.post(f'/api/v1/projects/{p}/jobs',headers=h,json={'stage':'SYNC','config_revision':'pinned'})
    assert response.status_code==202,response.text
    assert fake.calls[-1]==('enqueue',p,'SYNC','pinned')
    assert c.post(f'/api/v1/projects/{p}/sync',headers=h).status_code==202


def test_failure_read_allowed_but_replay_and_resume_require_manage_before_service(env):
    app,c,h,db,p,fake,j=pipeline_env(env)
    _,reader=app.state.security.create_key('reader',[p],['project_read'],actor='admin')
    _,manager=app.state.security.create_key('manager',[p],['project_manage'],actor='admin')
    _,foreign=app.state.security.create_key('foreign',['foreign'],['project_read','project_manage'],actor='admin')
    c.cookies.clear();read={'X-API-Key':reader};manage={'X-API-Key':manager};other={'X-API-Key':foreign}
    base=f'/api/v1/jobs/{j}'
    response=c.get(base+'/failed-items?limit=1&offset=0',headers=read)
    assert response.status_code==200,response.text
    assert response.json()[0]['retryable'] is True
    before=len(fake.calls)
    for suffix in ['/failed-items/synthetic/retry','/failed-items/retry','/resume']:
        assert c.post(base+suffix,headers=read,json={}).status_code==403
        assert c.post(base+suffix,headers=other,json={}).status_code==404
    assert c.get(base+'/failed-items',headers=other).status_code==404
    assert c.get('/api/v1/jobs/unknown/failed-items',headers=read).status_code==404
    assert len(fake.calls)==before
    request={'from_stage':'COLLECT','force_recollect':True,'expected_revision_uid':'rev'}
    result=c.post(base+'/failed-items/synthetic/retry',headers=manage,json=request)
    assert result.status_code==202,result.text
    assert fake.calls[-1]==('retry',j,'synthetic',request)
    assert c.post(base+'/failed-items/retry',headers=manage).status_code==202
    assert c.post(base+'/resume',headers=manage).status_code==202
    with db.connect() as sql:events=[__import__('json').loads(r[0]) for r in sql.execute('SELECT event FROM security_audit')]
    accepted=[e for e in events if e.get('action') in {'item_replay','failed_items_replay','job_resume'}]
    assert len(accepted)==3
    assert all(len(e['actor_ref'])==64 and e['project_uid']==p and e['job_uid']==j for e in accepted)
    assert manager not in str(events) and 'synthetic' not in str(accepted)


def test_failure_requests_validate_and_pipeline_errors_are_sanitized(env):
    from almrag.pipeline import PipelineError
    app,c,h,db,p,fake,j=pipeline_env(env);base=f'/api/v1/jobs/{j}'
    for query in ['limit=0','limit=1001','offset=-1']:
        assert c.get(base+'/failed-items?'+query,headers=h).status_code==422
    assert c.post(base+'/failed-items/id/retry',headers=h,json={'from_stage':'BOGUS'}).status_code==422
    assert not fake.calls
    def conflict(*a,**kw):raise PipelineError('STALE_REVISION')
    fake.retry=conflict
    response=c.post(base+'/failed-items/id/retry',headers=h,json={})
    assert response.status_code==409 and response.json()['code']=='STALE_REVISION'


def test_id_filters_are_typed_and_still_require_authorized_project_scope(env):
    app,c,h,db,calls=env;p=project(env,register(env));fake=Search();app.state.search=fake
    _,key=app.state.security.create_key('scoped',[p],['search'],actor='admin');c.cookies.clear();headers={'X-API-Key':key}
    body={'query':'opaque','project_uids':[p],'filters':{'source_item_ids':['opaque'],'fields':[{'kind':'SOURCE','key':'private','value':{'nested':[True,None,3]}}]}}
    result=c.post('/api/v1/search',headers=headers,json=body)
    assert result.status_code==200,result.text
    assert fake.calls[-1][0].filters.source_item_ids==['opaque']
    before=len(fake.calls);body['project_uids']=['foreign']
    assert c.post('/api/v1/search',headers=headers,json=body).status_code==403
    assert len(fake.calls)==before
    for filters in [{'item_uids':[]},{'item_uids':['x','x']},{'fields':[{'kind':'UNKNOWN','key':'x','value':1}]},{'fields':[{'kind':'SOURCE','key':'x','value':'x'*65537}]}]:
        assert c.post('/api/v1/search',headers=headers,json={'query':'x','project_uids':[p],'filters':filters}).status_code==422
    assert len(fake.calls)==before
