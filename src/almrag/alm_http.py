"""Read-only ALM transport with cross-process, server-wide persistent permits."""
import hashlib
import json as jsonlib
import math
import os
import random
import re
import time
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, unquote
from uuid import uuid4
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict, Field
from almrag.config import canonical_endpoint, server_origin


class _SlotLock:
    """Stable per-database slot; OS releases it on process death.

    Keep the inode permanently: unlinking a lock file could create two locks for
    the same slot. SQLite expiry alone cannot identify a blocked active stream.
    """
    def __init__(self,path):
        self.fd=os.open(path,os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
        if os.fstat(self.fd).st_size==0:os.write(self.fd,b'0')
        os.lseek(self.fd,0,os.SEEK_SET)

    def acquire(self):
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.fd,msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            return True
        except BlockingIOError:return False
        except OSError as error:
            if error.errno in {11,13,35}:return False
            raise

    def close(self):
        os.close(self.fd)


class AlmError(ValueError):
    def __init__(self,code,global_error=False,stop_state='BLOCKED',retryable=False,status=None):
        super().__init__(code)
        self.code,self.global_error,self.stop_state,self.retryable,self.status=code,global_error,stop_state,retryable,status


class HttpPolicy(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    requests_per_second:float=Field(default=2,gt=0,le=1000)
    burst:int=Field(default=2,ge=1,le=1000)
    max_inflight:int=Field(default=2,ge=1,le=32)
    min_interval_ms:int=Field(default=200,ge=0,le=60000)
    timeout_seconds:float=Field(default=30,gt=0,le=300)
    max_attempts:int=Field(default=5,ge=1,le=10)
    backoff_base_seconds:float=Field(default=2,ge=0,le=120)
    backoff_max_seconds:float=Field(default=120,ge=0,le=600)
    total_budget_seconds:float=Field(default=180,gt=0,le=3600)
    circuit_breaker_window:int=Field(default=20,ge=1,le=100)
    max_response_bytes:int=Field(default=16777216,ge=1,le=1073741824)


class ALMHttpClient:
    def __init__(self,db,instance_uid,base_url,*,policy=None,auth_headers=None,transport=None,
                 clock=time.time,sleep=time.sleep,jitter=random.random,abort_check=lambda:False,
                 allow_live=False,allowed_origins=(),renderer_verified=False,verify=True):
        self.db,self.instance_uid,self.base_url=db,instance_uid,canonical_endpoint(base_url)
        self.server_key=server_origin(self.base_url)
        self.policy=policy or HttpPolicy()
        self.headers=auth_headers or {}
        self.credential_scope=hashlib.sha256(jsonlib.dumps(self.headers,sort_keys=True).encode()).hexdigest()
        self.transport,self.clock,self.sleep,self.jitter=transport,clock,sleep,jitter
        self.abort_check,self.allow_live=abort_check,allow_live
        self.allowed_origins={server_origin(value) for value in allowed_origins}
        self.renderer_verified,self.verify=renderer_verified,verify
        self._permits={}
        database_path=Path(db.path).resolve()
        lock_base=database_path.parent / ('.'+database_path.name+'.alm-locks')
        lock_base.mkdir(mode=0o700,exist_ok=True)
        self._lock_root=lock_base / hashlib.sha256(self.server_key.encode()).hexdigest()
        self._lock_root.mkdir(mode=0o700,exist_ok=True)
        with db.transaction() as c:
            self.require_canonical_state(c,self.server_key)
            c.execute('INSERT OR IGNORE INTO server_policies VALUES(?,?)',(self.server_key,self.policy.model_dump_json()))
            c.execute('INSERT OR IGNORE INTO server_budgets(server_key,tokens,updated_at) VALUES(?,?,?)',(self.server_key,self.policy.burst,clock()))

    @staticmethod
    def require_canonical_state(connection,key):
        # Never silently discard an old alias's persisted pause/credential blocks
        # or move active OS locks. Prototype upgrades require a stopped-worker
        # state migration reviewed separately; new databases use canonical keys.
        for row in connection.execute('SELECT server_key FROM server_policies'):
            if row['server_key']!=key and server_origin(row['server_key'])==key:
                raise AlmError('SERVER_ORIGIN_MIGRATION_REQUIRED',True)

    def update_policy(self,policy):
        with self.db.transaction() as c:
            c.execute('UPDATE server_policies SET policy=? WHERE server_key=?',(policy.model_dump_json(),self.server_key))
            c.execute('UPDATE server_budgets SET tokens=min(tokens,?) WHERE server_key=?',(policy.burst,self.server_key))
        self.policy=policy

    def _abort(self):
        if self.abort_check():raise AlmError('ABORTED',True,stop_state='PAUSED')

    def _check_deadline(self,deadline,*,check_abort=True):
        if check_abort:self._abort()
        if self.clock()>=deadline:
            raise AlmError('RETRY_BUDGET_EXHAUSTED',True,stop_state='PAUSED',retryable=True)

    def _wait(self,delay,deadline):
        if self.clock()+delay>deadline:
            raise AlmError('RETRY_BUDGET_EXHAUSTED',True,stop_state='PAUSED',retryable=True)
        remaining=delay
        while remaining>0:
            self._abort();step=min(remaining,0.2);self.sleep(step);remaining-=step
        self._check_deadline(deadline)

    def _acquire(self,deadline):
        while True:
            self._check_deadline(deadline);now=self.clock()
            acquired=None
            try:
                with self.db.transaction() as c:
                    if c.execute('SELECT 1 FROM credential_blocks WHERE server_key=? AND credential_scope=?',(self.server_key,self.credential_scope)).fetchone():
                        raise AlmError('AUTH_FAILED',True,status=401)
                    row=c.execute('SELECT * FROM server_budgets WHERE server_key=?',(self.server_key,)).fetchone()
                    policy=HttpPolicy.model_validate_json(c.execute('SELECT policy FROM server_policies WHERE server_key=?',(self.server_key,)).fetchone()[0])
                    if row['circuit_state']=='OPEN':raise AlmError('CIRCUIT_OPEN',True,stop_state='PAUSED',retryable=True)
                    for expired in c.execute('SELECT permit_uid FROM request_leases WHERE server_key=? AND expires<=?',(self.server_key,now)).fetchall():
                        permit_uid=expired['permit_uid']
                        # Pre-M2 prototype UUID leases have no owning OS slot. All
                        # workers must be stopped before upgrading that prototype.
                        if ':' not in permit_uid:
                            c.execute('DELETE FROM request_leases WHERE permit_uid=?',(permit_uid,))
                            continue
                        slot=permit_uid.split(':',1)[0]
                        if not slot.isdigit() or not 0<=int(slot)<32:raise AlmError('INVALID_PERMIT',True)
                        guard=_SlotLock(self._lock_root / slot)
                        try:
                            if guard.acquire():c.execute('DELETE FROM request_leases WHERE permit_uid=?',(permit_uid,))
                        finally:guard.close()
                    inflight=c.execute('SELECT count(*) FROM request_leases WHERE server_key=?',(self.server_key,)).fetchone()[0]
                    tokens=min(policy.burst,row['tokens']+max(0,now-row['updated_at'])*policy.requests_per_second)
                    delay=max(0,row['pause_until']-now,row['next_allowed']-now,(1-tokens)/policy.requests_per_second)
                    if inflight>=policy.max_inflight:delay=max(delay,0.1)
                    c.execute('UPDATE server_budgets SET tokens=?,updated_at=? WHERE server_key=?',(tokens,now,self.server_key))
                    if delay<=0:
                        # The worker abort callback may itself fence a SQLite
                        # lease. Never invoke it while holding this write lock.
                        self._check_deadline(deadline,check_abort=False)
                        for slot in range(32):
                            guard=_SlotLock(self._lock_root / str(slot))
                            if not guard.acquire():guard.close();continue
                            permit=f'{slot}:{uuid4()}'
                            acquired=(permit,guard)
                            try:
                                c.execute('INSERT INTO request_leases VALUES(?,?,?)',(permit,self.server_key,deadline))
                                c.execute('UPDATE server_budgets SET tokens=?,next_allowed=? WHERE server_key=?',(tokens-1,now+policy.min_interval_ms/1000,self.server_key))
                                self._permits[permit]=guard
                                return permit
                            except BaseException:raise
                        delay=0.1
            except BaseException:
                if acquired is not None:
                    permit,guard=acquired
                    self._permits.pop(permit,None)
                    guard.close()
                raise
            self._wait(delay,deadline)

    def _release(self,permit):
        try:
            with self.db.transaction() as c:c.execute('DELETE FROM request_leases WHERE permit_uid=?',(permit,))
        finally:
            guard=self._permits.pop(permit,None)
            if guard is not None:guard.close()

    def _pause(self,seconds):
        with self.db.transaction() as c:
            policy=HttpPolicy.model_validate_json(c.execute('SELECT policy FROM server_policies WHERE server_key=?',(self.server_key,)).fetchone()[0])
            c.execute('UPDATE server_budgets SET pause_until=max(pause_until,?),failures=failures+1 WHERE server_key=?',(self.clock()+seconds,self.server_key))
            c.execute("UPDATE server_budgets SET circuit_state='OPEN' WHERE server_key=? AND failures>=?",(self.server_key,policy.circuit_breaker_window))

    def _safe_path(self,path,method):
        decoded=unquote(path)
        if not path.startswith('/') or path.startswith('//') or '\\' in decoded or any(p in {'.','..'} for p in decoded.split('/')) or any(ord(p)<32 for p in decoded):
            raise AlmError('UNSAFE_URL',True)
        if urlsplit(path).scheme or urlsplit(path).netloc or '#' in path:
            raise AlmError('UNSAFE_URL',True)
        if method!='GET' and not (method=='POST' and self.renderer_verified and re.fullmatch(r'/v3/projects/[^/?]+/wiki2html',path)):
            raise AlmError('READ_ONLY_VIOLATION',True)

    def _retry_after(self,value):
        try:
            seconds=float(value)
            return max(0,seconds) if math.isfinite(seconds) else None
        except (ValueError,TypeError):
            try:return max(0,parsedate_to_datetime(value).timestamp()-self.clock())
            except (ValueError,TypeError,OverflowError):return None

    def request(self,method,path,*,params=None,json=None,max_bytes=None):
        method=method.upper();self._safe_path(path,method);self._abort()
        if self.transport is None and (not self.allow_live or self.server_key not in self.allowed_origins):
            raise AlmError('LIVE_ALM_DISABLED',True)
        deadline=self.clock()+self.policy.total_budget_seconds
        limit=self.policy.max_response_bytes if max_bytes is None else min(max_bytes,self.policy.max_response_bytes)
        for attempt in range(self.policy.max_attempts):
            permit=self._acquire(deadline)
            response=None;delay=None;paused=False
            try:
                self._check_deadline(deadline)
                with httpx.Client(transport=self.transport,verify=self.verify,timeout=min(self.policy.timeout_seconds,max(0.001,deadline-self.clock())),follow_redirects=False,trust_env=False) as client:
                    with client.stream(method,self.base_url+path,params=params,json=json,headers=self.headers) as source:
                        # Persist protection immediately, while this request's
                        # permit is held. Error bodies are neither needed nor read.
                        status=source.status_code
                        if status==401:
                            with self.db.transaction() as c:
                                c.execute('INSERT OR REPLACE INTO credential_blocks VALUES(?,?,?)',(self.server_key,self.credential_scope,'AUTH_FAILED'))
                            raise AlmError('AUTH_FAILED',True,status=status)
                        if status in {429,500,502,503,504}:
                            delay=self._retry_after(source.headers.get('Retry-After'))
                            if delay is None:delay=self._backoff(attempt)
                            self._pause(delay);paused=True
                        elif 300<=status<400:raise AlmError('UNSAFE_REDIRECT',True,status=status)
                        elif status in {403,404}:raise AlmError('PERMISSION_DENIED' if status==403 else 'NOT_FOUND',False,status=status)
                        elif not 200<=status<300:raise AlmError('SCHEMA_MISMATCH',False,status=status)
                        self._check_deadline(deadline)
                        if not paused:
                            body=bytearray()
                            for chunk in source.iter_bytes():
                                self._check_deadline(deadline)
                                if len(body)+len(chunk)>limit:raise AlmError('RESPONSE_TOO_LARGE',False)
                                body.extend(chunk)
                            self._check_deadline(deadline)
                            response=httpx.Response(status,headers=source.headers,content=bytes(body),request=source.request)
                # Empty bodies and slow response close paths also have a bound.
                self._check_deadline(deadline)
            except httpx.HTTPError:
                if not paused:
                    delay=self._backoff(attempt);self._pause(delay);paused=True
            finally:self._release(permit)
            self._check_deadline(deadline)
            if response is not None:
                with self.db.transaction() as c:c.execute('UPDATE server_budgets SET failures=0 WHERE server_key=?',(self.server_key,))
                return response
            if attempt+1>=self.policy.max_attempts:break
            self._wait(delay,deadline)
        raise AlmError('RETRY_EXHAUSTED',True,stop_state='PAUSED',retryable=True)

    def _backoff(self,attempt):
        return min(self.policy.backoff_max_seconds,self.policy.backoff_base_seconds*(2**attempt))+self.jitter()

    def get_json(self,path,params=None):
        response=self.request('GET',path,params=params)
        try:return response.json()
        except (ValueError,UnicodeError):raise AlmError('SCHEMA_MISMATCH',False) from None
