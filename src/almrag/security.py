"""Session and key credentials, encrypted secret references and bounded audit events."""
import hashlib
import json
import re
import secrets
import time
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from cryptography.fernet import Fernet, InvalidToken

PERMISSIONS = {'search', 'project_read', 'project_manage', 'system_admin'}
ERRORS = {'CLEANUP_RETRY_PENDING', 'INVALID_AUTH', 'FORBIDDEN', 'INVALID_REQUEST', 'NOT_FOUND', 'STAGE_UNAVAILABLE', 'DATABASE_UNAVAILABLE', 'INTERNAL_ERROR', 'LEASE_LOST'}
ACTIONS = {'index_cleanup', 'item_replay', 'failed_items_replay', 'job_resume', 'login', 'logout', 'key_created', 'key_revoked', 'bootstrap', 'job_claim', 'job_blocked', 'request', 'worker_start', 'worker_stop'}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def safe_event(**values):
    result = {'timestamp': time.time()}
    for key, value in values.items():
        if key == 'action' and value in ACTIONS:
            result[key] = value
        elif key == 'outcome' and value in {'ok', 'denied', 'blocked', 'deferred'}:
            result[key] = value
        elif key == 'error_code' and value in ERRORS:
            result[key] = value
        elif key == 'stage' and value in {'SYNC', 'COLLECT', 'PROCESS', 'EMBED', 'INDEX', 'REBUILD_INDEX'}:
            result[key] = value
        elif key in {'attempt', 'http_status', 'elapsed_ms'} and isinstance(value, int) and 0 <= value <= 10**9:
            result[key] = value
        elif key == 'actor_ref' and isinstance(value,str) and re.fullmatch(r'[0-9a-f]{64}',value):
            result[key] = value
        elif key in {'alm_instance_uid', 'project_uid', 'job_uid', 'item_uid', 'step_uid', 'trace_id', 'target_uid'} and isinstance(value, str) and re.fullmatch(r'[0-9a-f-]{36}', value):
            result[key] = value
    return result


class Security:
    def __init__(self, db, session_seconds=3600):
        self.db, self.session_seconds = db, session_seconds
        self.hasher = PasswordHasher()
        self.dummy_hash = self.hasher.hash(secrets.token_urlsafe(32))
        with db.transaction() as c:
            for sql in [
                'CREATE TABLE IF NOT EXISTS administrators(username TEXT PRIMARY KEY, password_hash TEXT NOT NULL)',
                'CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, username TEXT NOT NULL, csrf_hash TEXT NOT NULL, expires REAL NOT NULL)',
                'CREATE TABLE IF NOT EXISTS api_keys(key_id TEXT PRIMARY KEY, name TEXT NOT NULL, key_hash TEXT UNIQUE NOT NULL, project_uids TEXT NOT NULL, permissions TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0)',
                'CREATE TABLE IF NOT EXISTS security_audit(audit_id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL)',
            ]:
                c.execute(sql)

    def audit(self, **values):
        with self.db.transaction() as c:
            self._audit(c,**values)

    @staticmethod
    def _audit(connection,**values):
        connection.execute('INSERT INTO security_audit(event) VALUES(?)',(json.dumps(safe_event(**values)),))

    def bootstrap(self, username, password):
        if not username or len(username) > 128 or not 16 <= len(password) <= 1024:
            raise ValueError('invalid_admin_credentials')
        hashed = self.hasher.hash(password)
        with self.db.transaction() as c:
            if c.execute('SELECT 1 FROM administrators LIMIT 1').fetchone():
                raise ValueError('admin_already_exists')
            c.execute('INSERT INTO administrators VALUES(?,?)', (username, hashed))
            self._audit(c,action='bootstrap',outcome='ok',actor_ref=digest('admin:'+username))

    def login(self, username, password, now=None, trace_id=None):
        now = time.time() if now is None else now
        with self.db.connect() as c:
            row = c.execute('SELECT password_hash FROM administrators WHERE username=?', (username,)).fetchone()
        try:
            valid = self.hasher.verify(row['password_hash'] if row else self.dummy_hash, password)
        except VerificationError:
            valid = False
        if not row or not valid:
            self.audit(action='login', outcome='denied', error_code='INVALID_AUTH',actor_ref=digest('admin:'+username),trace_id=trace_id)
            return None
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.db.transaction() as c:
            c.execute('INSERT INTO sessions VALUES(?,?,?,?)', (digest(token), username, digest(csrf), now + self.session_seconds))
            self._audit(c,action='login',outcome='ok',actor_ref=digest('admin:'+username),trace_id=trace_id)
        return token, csrf

    def session(self, token, now=None):
        now = time.time() if now is None else now
        with self.db.connect() as c:
            row = c.execute('SELECT username,csrf_hash FROM sessions WHERE token_hash=? AND expires>?', (digest(token), now)).fetchone()
        return dict(row) if row else None

    def logout(self, token, trace_id=None):
        with self.db.transaction() as c:
            row=c.execute('SELECT username FROM sessions WHERE token_hash=?',(digest(token),)).fetchone()
            c.execute('DELETE FROM sessions WHERE token_hash=?', (digest(token),))
            self._audit(c,action='logout',outcome='ok',actor_ref=digest('admin:'+row['username']) if row else None,trace_id=trace_id)

    def create_key(self, name, project_uids, permissions, actor,trace_id=None):
        if not project_uids or not permissions or not set(permissions) <= PERMISSIONS:
            raise ValueError('invalid_key_scope')
        key_id, raw = str(uuid4()), secrets.token_urlsafe(32)
        with self.db.transaction() as c:
            c.execute('INSERT INTO api_keys(key_id,name,key_hash,project_uids,permissions) VALUES(?,?,?,?,?)',
                      (key_id, name, digest(raw), json.dumps(sorted(set(project_uids))), json.dumps(sorted(set(permissions)))))
            self._audit(c,action='key_created',outcome='ok',actor_ref=digest(actor),target_uid=key_id,trace_id=trace_id)
        return key_id, raw

    def api_key(self, raw):
        with self.db.connect() as c:
            row = c.execute('SELECT key_id,project_uids,permissions FROM api_keys WHERE key_hash=? AND revoked=0', (digest(raw),)).fetchone()
        if not row:
            return None
        return {'key_id': row['key_id'], 'project_uids': json.loads(row['project_uids']), 'permissions': json.loads(row['permissions'])}

    def revoke_key(self, key_id, actor,trace_id=None):
        with self.db.transaction() as c:
            c.execute('UPDATE api_keys SET revoked=1 WHERE key_id=?', (key_id,))
            self._audit(c,action='key_revoked',outcome='ok',actor_ref=digest(actor),target_uid=key_id,trace_id=trace_id)


class SecretVault:
    def __init__(self, db, master_key):
        self.db = db
        self.cipher = Fernet(master_key)
        with db.transaction() as c:
            c.execute('CREATE TABLE IF NOT EXISTS encrypted_secrets(ref TEXT PRIMARY KEY, ciphertext BLOB NOT NULL)')

    def put(self, ref, value):
        with self.db.transaction() as c:
            c.execute('INSERT INTO encrypted_secrets VALUES(?,?) ON CONFLICT(ref) DO UPDATE SET ciphertext=excluded.ciphertext',
                      (ref, self.cipher.encrypt(value.encode())))

    def get(self, ref):
        with self.db.connect() as c:
            row = c.execute('SELECT ciphertext FROM encrypted_secrets WHERE ref=?', (ref,)).fetchone()
        if not row:
            raise ValueError('secret_unavailable')
        try:
            return self.cipher.decrypt(row['ciphertext']).decode()
        except InvalidToken:
            raise ValueError('secret_unavailable') from None
