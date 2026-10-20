"""SRS-027/028/057, TEST-027/028/057: credential and diagnostic boundaries."""
import json
import sqlite3
from contextlib import contextmanager

import pytest
from cryptography.fernet import Fernet

from almrag.security import Security, SecretVault, safe_event, digest


class TestDB:
    __test__ = False

    def __init__(self, path):
        self.path = path

    @contextmanager
    def transaction(self):
        with sqlite3.connect(self.path) as c:
            c.row_factory = sqlite3.Row
            c.execute('BEGIN IMMEDIATE')
            yield c

    connect = transaction


def test_password_session_and_key_expiry_revocation(tmp_path):
    db = TestDB(tmp_path / 'test.sqlite')
    auth = Security(db, session_seconds=10)
    auth.bootstrap('admin', 'a long synthetic password')
    with pytest.raises(ValueError):
        auth.bootstrap('admin', 'replacement password')
    assert auth.login('admin', 'wrong', now=100) is None
    session, csrf = auth.login('admin', 'a long synthetic password', now=100)
    assert auth.session(session, now=101)['username'] == 'admin'
    assert auth.session(session, now=111) is None
    key_id, key = auth.create_key('synthetic', ['p1'], ['project_read'], actor='admin')
    assert auth.api_key(key)['project_uids'] == ['p1']
    auth.revoke_key(key_id, actor='admin')
    assert auth.api_key(key) is None
    auth.logout(session)
    assert auth.session(session, now=101) is None
    raw = db.path.read_bytes()
    for secret in ('a long synthetic password', session, csrf, key):
        assert secret.encode() not in raw


def test_encrypted_vault_wrong_key_and_safe_logs(tmp_path):
    db = TestDB(tmp_path / 'test.sqlite')
    vault = SecretVault(db, Fernet.generate_key())
    vault.put('synthetic-ref', 'synthetic-password')
    assert vault.get('synthetic-ref') == 'synthetic-password'
    assert b'synthetic-password' not in db.path.read_bytes()
    other = SecretVault(db, Fernet.generate_key())
    with pytest.raises(ValueError, match='secret_unavailable'):
        other.get('synthetic-ref')
    event = safe_event(action='login', outcome='denied', password='synthetic-password', query='raw query', error_code='INVALID_AUTH', trace_id='abc')
    assert 'synthetic-password' not in json.dumps(event)
    assert 'raw query' not in json.dumps(event)
    assert event['error_code'] == 'INVALID_AUTH'
    assert 'synthetic-password' not in json.dumps(safe_event(error_code='secret=synthetic-password'))


def test_empty_and_unknown_permissions_rejected(tmp_path):
    auth = Security(TestDB(tmp_path / 'test.sqlite'))
    for projects, permissions in [([], ['project_read']), (['p'], []), (['p'], ['root'])]:
        with pytest.raises(ValueError):
            auth.create_key('name', projects, permissions, actor='admin')


def test_key_audit_attribution_and_atomicity(tmp_path):
    db=TestDB(tmp_path/'audit.sqlite');auth=Security(db)
    key_id,_=auth.create_key('synthetic',['p'],['project_read'],actor='caller-one',trace_id='00000000-0000-4000-8000-000000000001')
    auth.revoke_key(key_id,actor='caller-two')
    with db.connect() as c:
        events=[json.loads(r['event']) for r in c.execute('SELECT event FROM security_audit ORDER BY audit_id')]
    assert events[0]['actor_ref']==digest('caller-one')
    assert events[1]['actor_ref']==digest('caller-two')
    assert events[0]['target_uid']==events[1]['target_uid']==key_id
    assert events[0]['trace_id']=='00000000-0000-4000-8000-000000000001'
    assert 'caller-one' not in json.dumps(events)
    with db.transaction() as c:
        c.execute("CREATE TRIGGER reject_audit BEFORE INSERT ON security_audit BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        auth.create_key('not-issued',['p'],['project_read'],actor='caller')
    with db.connect() as c:
        assert c.execute("SELECT count(*) FROM api_keys WHERE name='not-issued'").fetchone()[0]==0
