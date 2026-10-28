"""Admin API key management: list/create/revoke contracts, secrecy, authorization and legacy compatibility."""
import json
import sqlite3
from fastapi.testclient import TestClient
from test_m2_api import env, register, project
from almrag.security import Security
from almrag.storage import Database


def make(env, name='user01', perms=('search',)):
    app, c, h, db, _ = env
    p = project(env, register(env)) if not hasattr(make, 'p') or make.db is not db else make.p
    make.p, make.db = p, db
    r = c.post('/api/v1/api-keys', headers=h, json={'name': name, 'project_uids': [p], 'permissions': list(perms)})
    assert r.status_code == 201, r.text
    return p, r.json()


def test_admin_lifecycle_list_hides_secrets_and_revocation_blocks_auth(env):
    app, c, h, db, _ = env
    p, created = make(env)
    assert c.get('/api/v1/api-keys', headers=h).status_code == 200
    body = c.get('/api/v1/api-keys', headers=h).json()
    assert body['total'] == 1 and body['items'][0]['key_id'] == created['key_id']
    item = body['items'][0]
    assert item['status'] == 'active' and item['project_uids'] == [p] and item['permissions'] == ['search'] and item['created_at'].endswith('Z')
    assert created['key'] not in json.dumps(body) and 'key_hash' not in json.dumps(body)
    key = {'X-API-Key': created['key']}
    cookies = dict(c.cookies); c.cookies.clear()
    assert c.get('/api/v1/auth/me', headers=key).status_code == 200
    assert c.get('/api/v1/api-keys', headers=key).status_code == 403
    assert c.get('/api/v1/api-keys').status_code == 401
    c.cookies.update(cookies)
    assert c.delete(f"/api/v1/api-keys/{created['key_id']}", headers=h).status_code == 204
    assert c.delete(f"/api/v1/api-keys/{created['key_id']}", headers=h).status_code == 204
    assert c.delete('/api/v1/api-keys/missing', headers=h).status_code == 404
    assert c.get('/api/v1/api-keys', headers=h).json()['items'][0]['status'] == 'revoked'
    c.cookies.clear()
    assert c.get('/api/v1/auth/me', headers=key).status_code == 401
    with db.connect() as sql:
        events = [json.loads(r[0]) for r in sql.execute('SELECT event FROM security_audit')]
        assert sql.execute('SELECT COUNT(*) FROM api_keys').fetchone()[0] == 1
    assert [e['action'] for e in events].count('key_created') == 1 and [e['action'] for e in events].count('key_revoked') == 1
    assert created['key'] not in json.dumps(events)


def test_filters_pagination_validation_and_session_only(env):
    app, c, h, db, _ = env
    p, first = make(env, 'alpha')
    _, second = make(env, 'Beta_%')
    c.delete(f"/api/v1/api-keys/{first['key_id']}", headers=h)
    assert [i['name'] for i in c.get('/api/v1/api-keys', headers=h).json()['items']] == ['Beta_%', 'alpha']
    assert [i['name'] for i in c.get('/api/v1/api-keys?status=active', headers=h).json()['items']] == ['Beta_%']
    assert c.get('/api/v1/api-keys?name=ALP', headers=h).json()['total'] == 1
    assert c.get('/api/v1/api-keys?name=a%25', headers=h).json()['total'] == 0
    assert c.get(f'/api/v1/api-keys?project_uid={p}&limit=1', headers=h).json()['total'] == 2
    assert c.get('/api/v1/api-keys?project_uid=other', headers=h).json()['total'] == 0
    assert c.get('/api/v1/api-keys?limit=0', headers=h).status_code == 422
    assert c.post('/api/v1/api-keys', headers=h, json={'name': 'x', 'project_uids': ['missing'], 'permissions': ['search']}).status_code == 404
    assert c.post('/api/v1/api-keys', headers=h, json={'name': 'x', 'project_uids': [p], 'permissions': ['bogus']}).status_code == 422
    # system_admin keys keep legacy create/revoke compatibility but cannot list (session-only).
    _, admin = make(env, 'legacy-admin', ('system_admin',))
    cookies = dict(c.cookies); c.cookies.clear()
    assert c.get('/api/v1/api-keys', headers={'X-API-Key': admin['key']}).status_code == 403
    c.cookies.update(cookies)


def test_legacy_key_without_created_at_survives_migration(tmp_path):
    path = tmp_path / 'legacy.sqlite'
    db = Database(path); db.migrate()
    legacy = sqlite3.connect(path)
    legacy.execute('CREATE TABLE api_keys(key_id TEXT PRIMARY KEY, name TEXT NOT NULL, key_hash TEXT UNIQUE NOT NULL, project_uids TEXT NOT NULL, permissions TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0)')
    from almrag.security import digest
    legacy.execute('INSERT INTO api_keys VALUES(?,?,?,?,?,0)', ('old', 'legacy', digest('raw-legacy'), '["p"]', '["search"]'))
    legacy.commit(); legacy.close()
    auth = Security(db)
    assert auth.api_key('raw-legacy') == {'key_id': 'old', 'project_uids': ['p'], 'permissions': ['search']}
    items, total = auth.list_keys()
    assert total == 1 and items[0]['created_at'] is None and items[0]['status'] == 'active'
    new_id, _ = auth.create_key('new', ['p'], ['search'], actor='admin')
    assert [i['key_id'] for i in auth.list_keys()[0]] == [new_id, 'old']
    Security(db)


def test_search_only_key_lists_projects_and_no_admin_access(env):
    app, c, h, db, _ = env
    p, created = make(env)
    c.cookies.clear(); key = {'X-API-Key': created['key']}
    assert [x['project_uid'] for x in c.get('/api/v1/projects', headers=key).json()] == [p]
    assert c.get('/api/v1/jobs', headers=key).status_code == 403
    assert c.get('/api/v1/alm-instances', headers=key).status_code == 403
