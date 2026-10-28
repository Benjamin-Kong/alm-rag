"""SRS-001/003/045/046/047/053/055: real SQLite + shared mock HTTP API boundary."""
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from almrag.api import create_app
from almrag.config import Settings
from almrag.connection import Connections
from almrag.storage import Database
from almrag.queue import Queue
from almrag.collection import CollectionService

PROFILE={'source_type':'codebeamer','display_name':'Synthetic','base_url':'https://alm.example.invalid','auth_ref':'env:SYNTHETIC_TOKEN',
         'http_policy':{'requests_per_second':1000,'burst':100,'min_interval_ms':0}}

@pytest.fixture
def env(tmp_path):
    db=Database(tmp_path/'test.sqlite');db.migrate();calls=[]
    def handler(request):
        calls.append(request)
        path=request.url.path
        if path=='/v3/projects':return httpx.Response(200,json=[{'id':1,'name':'Project'}])
        if path=='/v3/projects/1/trackers':return httpx.Response(200,json=[{'id':31,'name':'Requirements'},{'id':32,'name':'Bugs'}])
        if path in {'/v3/trackers/31/fields','/v3/trackers/32/fields'}:return httpx.Response(200,json=[{'id':3,'name':'Name'},{'id':80,'name':'Description'}])
        if path=='/v3/trackers/31/items':return httpx.Response(200,json=[{'id':100,'version':1}])
        if path=='/v3/trackers/32/items':return httpx.Response(200,json=[])
        if path=='/v3/items/100':return httpx.Response(200,json={'id':100,'tracker':{'id':31},'version':1,'name':'Synthetic','description':'Full original','descriptionFormat':'PlainText'})
        if path=='/v3/items/100/relations':return httpx.Response(200,json={})
        if path=='/v3/items/100/attachments':return httpx.Response(200,json=[])
        raise AssertionError(path)
    connections=Connections(db,Settings(),transport_factory=lambda _:httpx.MockTransport(handler),secret_resolver=lambda _:'synthetic-secret')
    service=CollectionService(db,connections.connector,tmp_path/'attachments')
    app=create_app(Settings(allowed_origin='https://testserver'),db=db,connections=connections,collection=service)
    app.state.security.bootstrap('admin','long synthetic password')
    with TestClient(app,base_url='https://testserver') as client:
        r=client.post('/api/v1/auth/login',json={'username':'admin','password':'long synthetic password'},headers={'Origin':'https://testserver'})
        assert r.status_code==204
        headers={'Origin':'https://testserver','X-CSRF-Token':client.cookies['almrag_csrf']}
        yield app,client,headers,db,calls

def register(env):
    _,client,headers,_,_=env
    r=client.post('/api/v1/alm-instances',json=PROFILE,headers=headers)
    assert r.status_code==201,r.text
    assert 'synthetic-secret' not in r.text and 'auth_ref' not in r.text
    return r.json()['instance_uid']

def project(env,uid):
    _,client,headers,_,_=env
    r=client.post('/api/v1/projects',headers=headers,json={'alm_instance_uid':uid,'source_project_id':'1','name':'Project','scope_kind':'TRACKER','selection_mode':'ALL'})
    assert r.status_code==201,r.text
    return r.json()['project_uid']

def test_discover_preflight_collect_http_to_sqlite(env):
    app,c,h,db,calls=env;uid=register(env)
    assert c.post(f'/api/v1/alm-instances/{uid}/probe',headers=h).json()['read_only'] is True
    assert c.get(f'/api/v1/alm-instances/{uid}/projects').json()[0]['id']=='1'
    scope=c.get(f'/api/v1/alm-instances/{uid}/projects/1/scopes').json()[0]
    assert scope['id']=='31' and scope['kind']=='TRACKER'
    p=project(env,uid)
    pre=c.post(f'/api/v1/projects/{p}/preflight',headers=h).json()
    assert pre['collect_ready'] and not pre['sync_ready'],pre
    assert pre['estimated_items']==1
    assert {x['id'] for x in pre['readable_fields']}=={'3','80'}
    r=c.post(f'/api/v1/projects/{p}/jobs',headers=h,json={'stage':'COLLECT','config_revision':pre['config_revision']})
    assert r.status_code==202,r.text
    job=Queue(db).claim('test',300)
    assert app.state.collection.run(job)=='SUCCEEDED'
    assert c.get('/api/v1/jobs/'+r.json()['job_id']).json()['state']=='SUCCEEDED'
    with db.connect() as sql:
        raw=json.loads(sql.execute('SELECT raw_payload FROM item_revisions').fetchone()[0])
        assert raw['title']=='Synthetic' and raw['raw']['description']=='Full original'
        assert sql.execute('SELECT active_revision_uid FROM items').fetchone()[0] is None
    assert all(x.method=='GET' for x in calls)
    for stage in ['SYNC','PROCESS','EMBED','INDEX']:
        assert c.post(f'/api/v1/projects/{p}/jobs',headers=h,json={'stage':stage}).status_code==409

def test_profile_union_secret_and_origin_guards(env):
    _,c,h,_,calls=env
    for bad in [{**PROFILE,'password':'synthetic-secret'}, {**PROFILE,'source_type':'polarion','api_profile':'cb-rest-v3'}, {**PROFILE,'base_url':'https://user:synthetic-secret@host.invalid'}, {**PROFILE,'auth_ref':'synthetic-secret'}]:
        r=c.post('/api/v1/alm-instances',headers=h,json=bad)
        assert r.status_code==422 and 'synthetic-secret' not in r.text
    assert not calls
    assert c.post('/api/v1/alm-instances',json=PROFILE).status_code==403

def test_new_routes_do_not_expand_key_acl(env):
    app,c,h,db,calls=env;uid=register(env);p=project(env,uid)
    _,reader=app.state.security.create_key('reader',[p],['project_read'],actor='admin')
    _,manager=app.state.security.create_key('manager',[p],['project_manage','project_read','system_admin'],actor='admin')
    c.cookies.clear();before=len(calls)
    for key in [reader,manager]:
        auth={'X-API-Key':key}
        for method,path,body in [('POST','/alm-instances',PROFILE),('POST',f'/alm-instances/{uid}/probe',None),('GET',f'/alm-instances/{uid}/projects',None),('GET',f'/alm-instances/{uid}/projects/1/scopes',None),('PUT',f'/alm-instances/{uid}/rate-policy',{}),('POST','/projects',{'alm_instance_uid':uid,'source_project_id':'1','name':'Project','scope_kind':'TRACKER'})]:
            r=c.request(method,'/api/v1'+path,headers=auth,json=body)
            assert r.status_code==403,(path,r.text)
    assert len(calls)==before
    auth={'X-API-Key':reader}
    assert c.post(f'/api/v1/projects/{p}/preflight',headers=auth).status_code==403
    auth={'X-API-Key':manager}
    assert c.post('/api/v1/projects/foreign/preflight',headers=auth).status_code==404
    assert c.post(f'/api/v1/projects/{p}/preflight',headers=auth).status_code==200

def test_config_stale_preflight_and_rate_policy(env):
    _,c,h,db,_=env;uid=register(env);p=project(env,uid)
    pre=c.post(f'/api/v1/projects/{p}/preflight',headers=h).json()
    changed={'selection_mode':'SELECTED','scope_kind':'TRACKER','source_scope_ids':['31'],'embedding_fields':['title']}
    r=c.put(f'/api/v1/projects/{p}/collection-config',headers=h,json=changed)
    assert r.status_code==200,r.text
    r=c.post(f'/api/v1/projects/{p}/jobs',headers=h,json={'stage':'COLLECT','config_revision':pre['config_revision']})
    assert r.status_code==409 and r.json()['code']=='STALE_PREFLIGHT'
    assert c.put(f'/api/v1/alm-instances/{uid}/rate-policy',headers=h,json={'max_inflight':1}).status_code==200
    with db.connect() as sql:assert json.loads(sql.execute('SELECT policy FROM server_policies').fetchone()[0])['max_inflight']==1

def test_upstream_error_is_sanitized_and_live_default_off(env):
    app,c,h,db,_=env;uid=register(env)
    app.state.connections.secret_resolver=lambda _: (_ for _ in ()).throw(ValueError('synthetic-secret'))
    r=c.post(f'/api/v1/alm-instances/{uid}/probe',headers=h)
    assert r.status_code==503 and 'synthetic-secret' not in r.text


def test_default_port_profile_and_server_policy_identity(env):
    _,c,h,db,_=env;uid=register(env)
    other={**PROFILE,'base_url':'https://ALM.EXAMPLE.INVALID:443','display_name':'Renamed','auth_ref':'env:NEW_REFERENCE'}
    r=c.post('/api/v1/alm-instances',headers=h,json=other)
    assert r.status_code==201,r.text
    assert r.json()['instance_uid']==uid
    assert c.put(f'/api/v1/alm-instances/{uid}/rate-policy',headers=h,json={'max_inflight':1}).status_code==200
    with db.connect() as sql:
        assert sql.execute('SELECT count(*) FROM instances').fetchone()[0]==1
        row=sql.execute('SELECT display_name,auth_ref FROM instances').fetchone()
        assert tuple(row)==('Renamed','env:NEW_REFERENCE')
        assert sql.execute('SELECT server_key FROM server_policies').fetchone()[0]=='https://alm.example.invalid'


def test_invalid_url_port_is_validation_error_without_registration(env):
    """SRS-001/045: malformed source URL must be a sanitized client error."""
    app,c,h,db,calls=env
    with TestClient(app,base_url='https://testserver',raise_server_exceptions=False) as request:
        request.cookies.update(c.cookies)
        result=request.post('/api/v1/alm-instances',headers=h,json={**PROFILE,'base_url':'https://alm.example.invalid:abc'})
    assert result.status_code==422,result.text
    assert result.json()['code']=='INVALID_REQUEST'
    assert not calls
    with db.connect() as sql:assert sql.execute('SELECT count(*) FROM instances').fetchone()[0]==0


def test_fields_discovery_requests_only_selected_trackers(tmp_path):
    """OI-067: fields for a project must not walk every tracker (gateway 504)."""
    db=Database(tmp_path/'t.sqlite');db.migrate();paths=[]
    def handler(request):
        paths.append(request.url.path)
        if request.url.path=='/v3/projects/1/trackers':return httpx.Response(200,json=[{'id':31,'name':'A'},{'id':32,'name':'B'}])
        if request.url.path in {'/v3/trackers/31/fields','/v3/trackers/32/fields'}:
            return httpx.Response(200,json=[{'id':request.url.path.split('/')[3],'name':'F'}])
        raise AssertionError(request.url.path)
    connections=Connections(db,Settings(),transport_factory=lambda _:httpx.MockTransport(handler),secret_resolver=lambda _:'synthetic-secret')
    app=create_app(Settings(allowed_origin='https://testserver'),db=db,connections=connections,collection=CollectionService(db,connections.connector,tmp_path/'a'))
    app.state.security.bootstrap('admin','long synthetic password')
    with TestClient(app,base_url='https://testserver') as c:
        assert c.post('/api/v1/auth/login',json={'username':'admin','password':'long synthetic password'},headers={'Origin':'https://testserver'}).status_code==204
        h={'Origin':'https://testserver','X-CSRF-Token':c.cookies['almrag_csrf']}
        uid=c.post('/api/v1/alm-instances',json=PROFILE,headers=h).json()['instance_uid']
        base=f'/api/v1/alm-instances/{uid}/projects/1/fields'
        r=c.get(base,params={'scope_ids':['31']})
        assert r.status_code==200 and [f['scope_id'] for f in r.json()]==['31']
        assert '/v3/trackers/32/fields' not in paths
        assert c.get(base,params={'scope_ids':['999']}).status_code==422


def test_instance_profile_list_update_delete(env):
    _,client,headers,db,_=env
    uid=register(env)
    listed=client.get('/api/v1/alm-instances',headers=headers).json()
    assert listed[0]['auth_ref']==PROFILE['auth_ref'] and listed[0]['auth_method']=='bearer'
    updated=client.put(f'/api/v1/alm-instances/{uid}',headers=headers,json={**PROFILE,'display_name':'Renamed','ca_bundle_ref':'env:SYNTHETIC_CA'})
    assert updated.status_code==200,updated.text
    assert updated.json()['display_name']=='Renamed' and updated.json()['ca_bundle_ref']=='env:SYNTHETIC_CA'
    assert client.put(f'/api/v1/alm-instances/{uid}',headers=headers,json={**PROFILE,'source_type':'polarion','api_profile':'polarion-rest-v1'}).status_code==409
    assert client.put('/api/v1/alm-instances/missing',headers=headers,json=PROFILE).status_code==404
    assert client.put(f'/api/v1/alm-instances/{uid}',json=PROFILE).status_code==403
    assert client.delete(f'/api/v1/alm-instances/{uid}').status_code==403
    assert client.put(f'/api/v1/alm-instances/{uid}',headers=headers,json=PROFILE).json()['ca_bundle_ref'] is None
    project(env,uid)
    assert client.delete(f'/api/v1/alm-instances/{uid}',headers=headers).status_code==409
    other=client.post('/api/v1/alm-instances',json={**PROFILE,'base_url':'https://other.example.invalid'},headers=headers).json()['instance_uid']
    assert client.put(f'/api/v1/alm-instances/{other}',headers=headers,json=PROFILE).status_code==409
    assert client.delete(f'/api/v1/alm-instances/{other}',headers=headers).status_code==204
    assert [i['instance_uid'] for i in client.get('/api/v1/alm-instances',headers=headers).json()]==[uid]


def selected_project(env,uid):
    _,client,headers,_,_=env
    r=client.post('/api/v1/projects',headers=headers,json={'alm_instance_uid':uid,'source_project_id':'1','name':'Project','scope_kind':'TRACKER','selection_mode':'SELECTED','source_scope_ids':['31']})
    assert r.status_code==201,r.text
    return r.json()['project_uid']

def test_add_scopes_marks_synced_and_requires_admin_session(env):
    app,c,h,db,calls=env;uid=register(env);p=selected_project(env,uid)
    pre=c.post(f'/api/v1/projects/{p}/preflight',headers=h).json()
    c.post(f'/api/v1/projects/{p}/jobs',headers=h,json={'stage':'COLLECT','config_revision':pre['config_revision']})
    assert app.state.collection.run(Queue(db).claim('test',300))=='SUCCEEDED'
    rows={x['id']:x for x in c.get(f'/api/v1/projects/{p}/scopes').json()}
    assert rows['31']['selected'] and rows['31']['item_count']==1 and rows['31']['last_synced_at'] is not None
    assert not rows['32']['selected'] and rows['32']['item_count']==0 and rows['32']['last_synced_at'] is None
    r=c.post(f'/api/v1/projects/{p}/scopes',headers=h,json={'source_scope_ids':['32']})
    assert r.status_code==200,r.text
    rows={x['id']:x for x in r.json()}
    assert rows['31']['selected'] and rows['32']['selected']
    with db.connect() as sql:
        cfg=sql.execute('SELECT scope_ids,config_revision FROM project_selections').fetchone()
        assert json.loads(cfg[0])==['31','32'] and cfg[1]==2
        assert 'scope_added' in ' '.join(x[0] for x in sql.execute('SELECT event FROM security_audit'))
    assert c.post(f'/api/v1/projects/{p}/scopes',headers=h,json={'source_scope_ids':['999']}).status_code==422
    assert c.post(f'/api/v1/projects/{p}/scopes',headers=h,json={'source_scope_ids':[]}).status_code==422
    _,manager=app.state.security.create_key('manager',[p],['project_manage','project_read','system_admin'],actor='admin')
    c.cookies.clear();before=len(calls)
    for method in ['GET','POST']:
        r=c.request(method,f'/api/v1/projects/{p}/scopes',headers={'X-API-Key':manager},json={'source_scope_ids':['32']} if method=='POST' else None)
        assert r.status_code==403
    assert len(calls)==before

def test_add_scopes_rejected_when_all_selected(env):
    _,c,h,_,_=env;uid=register(env);p=project(env,uid)
    r=c.post(f'/api/v1/projects/{p}/scopes',headers=h,json={'source_scope_ids':['32']})
    assert r.status_code==409 and r.json()['code']=='ALL_SCOPES_SELECTED'
