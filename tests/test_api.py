"""SRS-019/027/028/040/057: synthetic negative ACL and cookie contracts."""
import json
import sqlite3
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from almrag.api import create_app
from almrag.config import Settings


class ApiDB:
    """Minimal adapter for isolated API contract tests, no production state."""
    def __init__(self, path):
        self.path = path
        with self.transaction() as c:
            c.execute('CREATE TABLE projects(project_uid TEXT, instance_uid TEXT, source_project_id TEXT, name TEXT)')
            c.execute('CREATE TABLE jobs(job_id TEXT, project_uid TEXT, stage TEXT, state TEXT, checkpoint TEXT)')
            c.executemany('INSERT INTO projects VALUES(?,?,?,?)', [('p1','i1','1','one'), ('p2','i2','2','two')])
            c.execute("INSERT INTO jobs VALUES('j2','p2','SYNC','QUEUED','{}')")

    @contextmanager
    def transaction(self):
        with sqlite3.connect(self.path) as c:
            c.row_factory = sqlite3.Row
            yield c
    connect = transaction


@pytest.fixture
def env(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path/'test.sqlite'), allowed_origin='https://testserver'), db=ApiDB(tmp_path/'test.sqlite'))
    app.state.security.bootstrap('admin','long synthetic password')
    with TestClient(app, base_url='https://testserver') as client:
        yield app, client


def login(client):
    r = client.post('/api/v1/auth/login', json={'username':'admin','password':'long synthetic password'}, headers={'Origin':'https://testserver'})
    assert r.status_code == 204
    assert r.content == b''
    assert 'httponly' in r.headers['set-cookie'].lower()
    assert 'secure' in r.headers['set-cookie'].lower()
    return {'Origin':'https://testserver', 'X-CSRF-Token':client.cookies['almrag_csrf']}


def test_cookie_csrf_logout_and_validation_secrecy(env):
    app, client = env
    assert client.get('/api/v1/healthz').json() == {'status':'ok'}
    assert client.get('/api/v1/readyz').status_code == 401
    assert client.post('/api/v1/auth/login',json={'password':['synthetic-secret']}).status_code == 403
    headers = login(client)
    assert client.post('/api/v1/auth/logout').status_code == 403
    assert client.get('/api/v1/readyz').status_code == 200
    r = client.post('/api/v1/api-keys', json={'name':['synthetic-secret']}, headers=headers)
    assert r.status_code == 422 and 'synthetic-secret' not in r.text
    assert client.post('/api/v1/auth/logout',headers=headers).status_code == 204
    assert client.get('/api/v1/readyz').status_code == 401


def test_key_scope_revocation_and_unavailable_stages(env):
    app, client = env
    headers = login(client)
    response = client.post('/api/v1/api-keys',json={'name':'reader','project_uids':['p1'],'permissions':['project_read']},headers=headers)
    assert response.status_code == 201
    key = response.json()
    client.cookies.clear()
    auth = {'X-API-Key':key['key']}
    assert [p['project_uid'] for p in client.get('/api/v1/projects',headers=auth).json()] == ['p1']
    assert client.get('/api/v1/jobs/j2',headers=auth).status_code == 404
    assert client.get('/api/v1/jobs/unknown',headers=auth).status_code == 404
    assert client.get('/api/v1/jobs',headers=auth).json() == []
    assert client.post('/api/v1/projects/p1/jobs',json={'stage':'SYNC'},headers=auth).status_code == 403
    assert client.get('/api/v1/readyz',headers=auth).status_code == 403
    admin_headers = login(client)
    result=client.post('/api/v1/projects/p1/jobs',json={'stage':'SYNC'},headers=admin_headers)
    assert result.status_code == 503 and result.json()['code']=='DATABASE_UNAVAILABLE'  # Minimal fixture has no collection tables; never bypass preflight.
    assert client.delete('/api/v1/api-keys/'+key['key_id'],headers=admin_headers).status_code == 204
    client.cookies.clear()
    assert client.get('/api/v1/projects',headers=auth).status_code == 401


def test_admin_key_cannot_expand_grants(env):
    app, client = env
    _, raw = app.state.security.create_key('limited',['p1'],['system_admin','project_read'],actor='admin')
    headers={'X-API-Key':raw}
    r=client.post('/api/v1/api-keys',headers=headers,json={'name':'escalate','project_uids':['p2'],'permissions':['system_admin']})
    assert r.status_code == 403
    r=client.post('/api/v1/api-keys',headers=headers,json={'name':'escalate','project_uids':['p1'],'permissions':['project_manage']})
    assert r.status_code == 403
    assert client.get('/api/v1/audit-events',headers=headers).status_code == 403


def test_auth_failures_are_audited_without_input(env):
    app, client=env
    r=client.get('/api/v1/projects',headers={'X-API-Key':'synthetic-invalid-token'})
    assert r.status_code == 401
    headers=login(client)
    events=client.get('/api/v1/audit-events',headers=headers).json()
    assert any(e.get('error_code')=='INVALID_AUTH' for e in events)
    assert 'synthetic-invalid-token' not in json.dumps(events)


@pytest.mark.parametrize('method',['api_key','audit'])
def test_database_auth_failure_is_sanitized(env,monkeypatch,method):
    app,client=env
    def fail(*args,**kwargs):
        raise sqlite3.OperationalError('synthetic-sensitive-db-detail')
    monkeypatch.setattr(app.state.security,method,fail)
    response=client.get('/api/v1/projects',headers={'X-API-Key':'invalid'})
    assert response.status_code==503
    assert response.json()['code']=='DATABASE_UNAVAILABLE'
    assert 'synthetic-sensitive-db-detail' not in response.text


def test_csrf_origin_and_mixed_credentials(env):
    app,client=env
    headers=login(client)
    assert client.post('/api/v1/auth/logout',headers={**headers,'X-CSRF-Token':'wrong'}).status_code==403
    assert client.post('/api/v1/auth/logout',headers={**headers,'Origin':'https://evil.example.invalid'}).status_code==403
    _,other_csrf=app.state.security.login('admin','long synthetic password')
    assert client.post('/api/v1/auth/logout',headers={**headers,'X-CSRF-Token':other_csrf}).status_code==403
    assert client.get('/api/v1/projects',headers={'X-API-Key':'wrong'}).status_code==401
    events=client.get('/api/v1/audit-events').json()
    assert sum(e.get('error_code')=='FORBIDDEN' for e in events)>=3


def test_scoped_admin_key_revoke_boundary(env):
    app,client=env
    auth=app.state.security
    _,limited=auth.create_key('limited',['p1'],['system_admin','project_read'],actor='admin')
    foreign_id,_=auth.create_key('foreign',['p2'],['project_read'],actor='admin')
    wider_id,_=auth.create_key('wider',['p1'],['project_manage'],actor='admin')
    headers={'X-API-Key':limited}
    for key_id in [foreign_id,wider_id]:
        assert client.delete('/api/v1/api-keys/'+key_id,headers=headers).status_code==404
    created=client.post('/api/v1/api-keys',headers=headers,json={'name':'safe','project_uids':['p1'],'permissions':['project_read']})
    assert created.status_code==201
    assert client.delete('/api/v1/api-keys/'+created.json()['key_id'],headers=headers).status_code==204
    from almrag.security import digest
    principal=auth.api_key(limited)
    with app.state.db.connect() as c:
        event=json.loads(c.execute('SELECT event FROM security_audit ORDER BY audit_id DESC LIMIT 1').fetchone()[0])
    assert event['actor_ref']==digest('api_key:'+principal['key_id'])
    assert event['target_uid']==created.json()['key_id']


def test_openapi_has_security_and_sanitized_errors(env):
    app,_=env
    spec=app.openapi()
    assert spec['components']['securitySchemes']['ApiKeyAuth']['name']=='X-API-Key'
    operation=spec['paths']['/api/v1/jobs/{job_id}']['get']
    assert operation['security']==[{'ApiKeyAuth':[]},{'AdminSession':[]}]
    assert operation['responses']['401']['content']['application/json']['schema']['$ref'].endswith('/ApiError')
    assert spec['paths']['/api/v1/healthz']['get']['security']==[]


def test_exported_contract_matches_executed_api(env):
    from pathlib import Path
    import yaml
    app,_=env
    root=Path(__file__).resolve().parents[1]
    exported=json.loads((root/'docs/api/m4-openapi.json').read_text())
    assert exported==app.openapi()
    draft=yaml.safe_load((root/'docs/api/openapi.yaml').read_text())
    for path,methods in exported['paths'].items():
        for verb,operation in methods.items():
            recorded=draft['paths'][path.removeprefix('/api/v1')][verb]
            assert recorded['operationId']==operation['operationId']
            assert recorded['x-required-scope']==operation['x-required-scope']
            assert set(recorded['responses'])==set(operation['responses'])
