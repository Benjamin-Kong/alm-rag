"""M2 acceptance: six synthetic projects, API→shared HTTP→worker→SQLite/assets.

No sockets, source writes, model or index services are used.
"""
from copy import deepcopy
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from almrag.api import create_app
from almrag.collection import CollectionService
from almrag.config import Settings
from almrag.connection import Connections
from almrag.queue import Queue
from almrag.storage import Database
from almrag.worker import run_once
from test_connectors import cb_item_client, polarion_client

MATRIX=json.loads((Path(__file__).parent/'fixtures/alm/project_matrix.json').read_text())
CASES=[(product,row) for product in ('codebeamer','polarion') for row in MATRIX[product]]

def routes_for(product,row):
    project,scope,item=row['project_id'],row['scope_id'],row['item_id']
    if product=='codebeamer':
        routes=deepcopy(cb_item_client().routes)
        for path in list(routes):
            if isinstance(path,str) and '/items/100' in path:
                routes[path.replace('/items/100','/items/'+item)]=routes.pop(path)
        raw=routes[f'/v3/items/{item}'];raw['id']=int(item);raw['tracker']['id']=int(scope)
        def projects(params):
            page=int(params.get('page',1));group=MATRIX[product][:2] if page==1 else MATRIX[product][2:]
            return {'page':page,'pageSize':2,'total':3,'projects':[{'id':int(x['project_id']),'name':'Synthetic '+x['project_id']} for x in group]}
        routes['/v3/projects']=projects
        routes[f'/v3/projects/{project}/trackers']=[{'id':int(scope),'name':'Requirements'}]
        routes[f'/v3/trackers/{scope}/fields']=[{'id':900,'name':'Custom'}]
        routes[f'/v3/trackers/{scope}/items']={'total':1,'itemRefs':[{'id':int(item),'version':4}]}
        return routes,'https://cb.example.invalid','TRACKER',b'attachment\x00data',raw
    template=deepcopy(polarion_client().routes)
    def rename(path):return path.replace('/projects/p/','/projects/'+project+'/').replace('/REQ-1','/'+item)
    routes={(tuple(rename(part) for part in key) if isinstance(key,tuple) else rename(key)):value for key,value in template.items()}
    raw=routes[f'/projects/{project}/workitems/{item}']
    resource=raw['data'];resource['id']=project+'/'+item;resource['revision']='7'
    resource['attributes']['id']=item;resource['attributes']['type']=scope
    routes[f'/projects/{project}/workitems/{item}/attachments']['data'][0]['id']=f'{project}/{item}/file.txt'
    def projects(params):
        page=int(params.get('page[number]',1));group=MATRIX[product][:2] if page==1 else MATRIX[product][2:]
        return {'data':[{'id':x['project_id'],'attributes':{'name':'Synthetic '+x['project_id']}} for x in group],
                'meta':{'totalCount':3},'links':{'next':'/projects?page[number]=2' if page==1 else None}}
    routes['/projects']=projects
    routes[f'/projects/{project}/enumerations/~/workitem-type/~']={'data':{'attributes':{'options':[{'id':scope,'name':'Type'}]}}}
    routes[f'/projects/{project}/actions/getFieldsMetadata']={'data':{'attributes':{'futureCustom':{'label':'Custom'}}}}
    routes[f'/projects/{project}/workitems']={'data':[resource]}
    return routes,'https://po.example.invalid/polarion/rest/v1','WORK_ITEM_TYPE',b'\xffbinary',raw

@pytest.mark.parametrize('product,row',CASES,ids=[p+'-'+r['project_id'] for p,r in CASES])
def test_six_project_mock_acceptance(tmp_path,product,row):
    routes,base,kind,attachment_bytes,source_raw=routes_for(product,row)
    calls=[]
    def handler(req):
        calls.append(req)
        assert req.method=='GET' and req.headers['Authorization']=='Bearer synthetic-token'
        path=req.url.path.removeprefix('/polarion/rest/v1')
        if ('GET',path) in routes:return httpx.Response(200,content=routes[('GET',path)])
        value=routes[path]
        if callable(value):value=value(dict(req.url.params))
        return httpx.Response(200,json=value)
    db=Database(tmp_path/'db.sqlite');db.migrate()
    settings=Settings(allowed_origin='https://testserver',database_path=str(db.path),attachment_root=str(tmp_path/'assets'))
    connections=Connections(db,settings,transport_factory=lambda _:httpx.MockTransport(handler),secret_resolver=lambda _:'synthetic-token')
    collection=CollectionService(db,connections.connector,settings.attachment_root)
    app=create_app(settings,db=db,connections=connections,collection=collection)
    app.state.security.bootstrap('admin','long synthetic password')
    with TestClient(app,base_url='https://testserver') as client:
        assert client.post('/api/v1/auth/login',headers={'Origin':'https://testserver'},json={'username':'admin','password':'long synthetic password'}).status_code==204
        headers={'Origin':'https://testserver','X-CSRF-Token':client.cookies['almrag_csrf']}
        registration=client.post('/api/v1/alm-instances',headers=headers,json={'source_type':product,'display_name':'Synthetic','base_url':base,'auth_ref':'env:FIXTURE','http_policy':{'requests_per_second':1000,'burst':1000,'min_interval_ms':0}})
        assert registration.status_code==201,registration.text
        uid=registration.json()['instance_uid']
        assert len(client.get(f'/api/v1/alm-instances/{uid}/projects').json())==3
        registration=client.post('/api/v1/projects',headers=headers,json={'alm_instance_uid':uid,'source_project_id':row['project_id'],'name':'Synthetic','scope_kind':kind,'selection_mode':'SELECTED','source_scope_ids':[row['scope_id']]})
        assert registration.status_code==201,registration.text
        project=registration.json()['project_uid']
        for _ in range(2):
            pre=client.post(f'/api/v1/projects/{project}/preflight',headers=headers).json()
            assert pre['collect_ready'] and not pre['sync_ready'],pre
            assert pre['estimated_requests'] is None and pre['request_estimate_kind']=='UNKNOWN'
            assert pre['request_count_lower_bound']==1
            queued=client.post(f'/api/v1/projects/{project}/jobs',headers=headers,json={'stage':'COLLECT','config_revision':pre['config_revision']})
            assert queued.status_code==202,queued.text
            assert run_once(Queue(db),'mock-worker',collection,health_path=tmp_path/'health.json')
            assert client.get('/api/v1/jobs/'+queued.json()['job_id']).json()['state']=='SUCCEEDED'
        with db.connect() as c:
            assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==1
            assert c.execute('SELECT count(*) FROM attachments').fetchone()[0]==1
            saved=json.loads(c.execute('SELECT raw_payload FROM item_revisions').fetchone()[0])
            assert saved['raw']==source_raw
            assert len(saved['description']['raw'])>50000
            assert saved['raw_resources']['relations']
            assert c.execute('SELECT active_revision_uid FROM items').fetchone()[0] is None
            path=Path(c.execute('SELECT disk_path FROM attachments').fetchone()[0])
            assert path.is_relative_to(tmp_path/'assets') and path.read_bytes()==attachment_bytes
        assert any('page=2' in str(req.url) or 'page%5Bnumber%5D=2' in str(req.url) for req in calls)
