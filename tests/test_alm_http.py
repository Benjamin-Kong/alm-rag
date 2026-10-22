"""SRS-053/054: all-source protection, no live sockets."""
import httpx
import pytest
from almrag.storage import Database
from almrag.alm_http import ALMHttpClient, HttpPolicy, AlmError


class Clock:
    def __init__(self):self.now=1000.0
    def __call__(self):return self.now
    def sleep(self,seconds):self.now+=seconds


def test_lease_abort_callback_never_runs_under_transport_write_lock(setup):
    """SRS-053/055: worker lease guard may write SQLite during abort checks."""
    db,_,_=setup
    checks=[]
    def lease_guard():
        with db.connect() as connection:
            connection.execute('PRAGMA busy_timeout=0')
            connection.execute('BEGIN IMMEDIATE')
            checks.append(True)
            connection.rollback()
        return False
    c=client(setup,lambda _:httpx.Response(200,json={}),abort_check=lease_guard)
    assert c.get_json('/v3/projects')=={}
    assert checks


@pytest.mark.parametrize('scheme,port',[('https',443),('http',80)])
def test_equivalent_default_port_shares_server_pause_and_locks(setup,scheme,port):
    """SRS-053/054: aliases normalized by HTTPX share one server budget."""
    db,uid,clock=setup
    common=dict(clock=clock,sleep=clock.sleep,jitter=lambda:0,policy=HttpPolicy(max_attempts=1))
    a=ALMHttpClient(db,uid,f'{scheme}://alm.example.invalid',transport=httpx.MockTransport(lambda _:httpx.Response(429,headers={'Retry-After':'15'})),**common)
    sent=[]
    b=ALMHttpClient(db,uid,f'{scheme}://ALM.EXAMPLE.INVALID:{port}',transport=httpx.MockTransport(lambda _:sent.append(clock()) or httpx.Response(200,json={})),**common)
    with pytest.raises(AlmError):a.get_json('/v3/projects')
    assert b.get_json('/v3/projects')=={}
    assert sent[0]>=1015
    assert a.server_key==b.server_key and a._lock_root==b._lock_root


def test_old_noncanonical_budget_fails_closed_instead_of_losing_pause(setup):
    db,uid,clock=setup
    with db.transaction() as c:
        c.execute('INSERT INTO server_policies VALUES(?,?)',('https://alm.example.invalid:443',HttpPolicy().model_dump_json()))
        c.execute('INSERT INTO server_budgets(server_key,tokens,updated_at,pause_until) VALUES(?,?,?,?)',('https://alm.example.invalid:443',1,clock(),1015))
    with pytest.raises(AlmError,match='SERVER_ORIGIN_MIGRATION_REQUIRED'):
        client(setup,lambda _:httpx.Response(200,json={}))


@pytest.fixture
def setup(tmp_path):
    db=Database(tmp_path/'alm.sqlite');db.migrate()
    instance=db.add_instance('codebeamer','https://alm.example.invalid','synthetic','ref')
    return db,instance,Clock()


def client(setup,handler,**kwargs):
    db,instance,clock=setup
    return ALMHttpClient(db,instance,'https://alm.example.invalid',transport=httpx.MockTransport(handler),clock=clock,sleep=clock.sleep,jitter=lambda:0,**kwargs)


def test_shared_rate_all_request_types_and_credentials(setup):
    times=[]
    def handler(request):times.append(setup[2]());return httpx.Response(200,json={'ok':True})
    a=client(setup,handler);b=client(setup,handler,auth_headers={'Authorization':'Bearer synthetic'})
    a.get_json('/v3/projects');b.get_json('/v3/items/1');a.request('GET','/v3/items/1/attachments/2/content')
    assert times[1]-times[0]>=0.2
    assert times[2]-times[0]>=0.5


def test_retry_after_global_persisted_and_budget_does_not_send_early(setup):
    calls=[]
    def limited(request):calls.append(setup[2]());return httpx.Response(429,headers={'Retry-After':'15'})
    a=client(setup,limited,policy=HttpPolicy(total_budget_seconds=2))
    with pytest.raises(AlmError) as caught:a.get_json('/v3/projects')
    assert caught.value.stop_state=='PAUSED'
    assert len(calls)==1
    times=[]
    b=client(setup,lambda _:times.append(setup[2]()) or httpx.Response(200,json={}),policy=HttpPolicy(total_budget_seconds=30),auth_headers={'Authorization':'Bearer other'})
    b.get_json('/v3/projects')
    assert times[0]>=1015


def test_retry_date_5xx_and_nonretryable_auth(setup):
    responses=[httpx.Response(503,headers={'Retry-After':'Thu, 01 Jan 1970 00:16:45 GMT'}),httpx.Response(200,json={})]
    c=client(setup,lambda _:responses.pop(0))
    c.get_json('/v3/projects')
    assert setup[2]()>=1005
    for status,code,global_error in [(401,'AUTH_FAILED',True),(403,'PERMISSION_DENIED',False),(404,'NOT_FOUND',False)]:
        calls=[]
        c=client(setup,lambda _:calls.append(1) or httpx.Response(status,text='sensitive-body'),auth_headers={'Authorization':f'Bearer synthetic-{status}'})
        with pytest.raises(AlmError) as error:c.get_json('/v3/items/1')
        assert (error.value.code,error.value.global_error)==(code,global_error)
        assert len(calls)==1 and 'sensitive-body' not in str(error.value)


def test_failed_credential_is_blocked_without_repeating_request(setup):
    calls=[]
    c=client(setup,lambda _:calls.append(1) or httpx.Response(401))
    for _ in range(2):
        with pytest.raises(AlmError,match='AUTH_FAILED'):c.get_json('/v3/projects')
    assert len(calls)==1


def test_read_only_origin_bytes_redirect_and_abort(setup):
    calls=[]
    c=client(setup,lambda _:calls.append(1) or httpx.Response(200,content=b'x'*100))
    for method,path in [('DELETE','/v3/items/1'),('POST','/v3/projects/1/wiki2html'),('GET','https://evil.example.invalid/x'),('GET','/v3/../secrets')]:
        with pytest.raises(AlmError):c.request(method,path)
    assert calls==[]
    with pytest.raises(AlmError,match='RESPONSE_TOO_LARGE'):c.request('GET','/v3/items/1',max_bytes=20)
    c=client(setup,lambda _:httpx.Response(302,headers={'Location':'https://evil.example.invalid'}))
    with pytest.raises(AlmError,match='UNSAFE_REDIRECT'):c.get_json('/v3/projects')
    c=client(setup,lambda _:httpx.Response(200),abort_check=lambda:True)
    with pytest.raises(AlmError,match='ABORTED'):c.get_json('/v3/projects')


def test_no_network_without_explicit_live_allowlist(setup):
    db,instance,clock=setup
    c=ALMHttpClient(db,instance,'https://alm.example.invalid')
    with pytest.raises(AlmError,match='LIVE_ALM_DISABLED'):c.get_json('/v3/projects')


def test_permits_released_and_shared_inflight_bound(setup):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Lock
    import time
    db,instance,_=setup
    active=0;peak=0;lock=Lock()
    def handler(request):
        nonlocal active,peak
        with lock:active+=1;peak=max(peak,active)
        time.sleep(0.02)
        with lock:active-=1
        return httpx.Response(200,json={})
    policy=HttpPolicy(requests_per_second=1000,burst=10,max_inflight=1,min_interval_ms=0)
    c=ALMHttpClient(db,instance,'https://concurrency.example.invalid',policy=policy,transport=httpx.MockTransport(handler))
    with ThreadPoolExecutor(max_workers=3) as executor:list(executor.map(lambda _:c.get_json('/v3/projects'),range(3)))
    assert peak==1
    with db.connect() as connection:assert connection.execute('SELECT count(*) FROM request_leases').fetchone()[0]==0


def test_circuit_and_renderer_contract(setup):
    calls=[]
    c=client(setup,lambda _:calls.append(1) or httpx.Response(503),policy=HttpPolicy(max_attempts=3,circuit_breaker_window=2,backoff_base_seconds=0))
    with pytest.raises(AlmError,match='CIRCUIT_OPEN'):c.get_json('/v3/projects')
    assert len(calls)==2


def test_verified_renderer_and_connection_timeout(setup):
    methods=[]
    c=client(setup,lambda request:methods.append(request.method) or httpx.Response(200,text='<p>rendered</p>'),renderer_verified=True)
    assert c.request('POST','/v3/projects/1/wiki2html',json={'markup':'fixture'}).text=='<p>rendered</p>'
    assert methods==['POST']
    calls=[]
    def timeout(request):calls.append(1);raise httpx.ReadTimeout('sensitive-transport-detail')
    c=client(setup,timeout,policy=HttpPolicy(max_attempts=2,backoff_base_seconds=0))
    with pytest.raises(AlmError,match='RETRY_EXHAUSTED'):c.get_json('/v3/projects')
    assert len(calls)==2


def test_protection_headers_precede_body_limits_and_permit_release(setup):
    """SRS-053/054 OI-035: error bodies cannot bypass persisted protection."""
    db,_,clock=setup
    for status,expected in [(429,'RETRY_BUDGET_EXHAUSTED'),(401,'AUTH_FAILED')]:
        c=client(setup,lambda _:httpx.Response(status,headers={'Retry-After':'15'},content=b'x'*100),
                 policy=HttpPolicy(max_response_bytes=10,total_budget_seconds=1),
                 auth_headers={'Authorization':f'Bearer oversized-{status}'})
        release=c._release
        def inspect_release(permit):
            with db.connect() as connection:
                if status==429:
                    assert connection.execute('SELECT pause_until FROM server_budgets').fetchone()[0]>=1015
                else:
                    assert connection.execute('SELECT count(*) FROM credential_blocks').fetchone()[0]==1
            release(permit)
        c._release=inspect_release
        with pytest.raises(AlmError,match=expected):c.get_json('/v3/projects')
        if status==429:clock.now=1016
    calls=[]
    c=client(setup,lambda _:calls.append(clock()) or httpx.Response(200,json={}),auth_headers={'Authorization':'Bearer oversized-401'})
    with pytest.raises(AlmError,match='AUTH_FAILED'):c.get_json('/v3/projects')
    assert calls==[]


def test_empty_response_and_exhausted_acquisition_enforce_deadline(setup):
    """SRS-053/054 OI-037: no successful completion or send after budget."""
    def late(_):setup[2].now+=2;return httpx.Response(200)
    c=client(setup,late,policy=HttpPolicy(total_budget_seconds=1))
    with pytest.raises(AlmError,match='RETRY_BUDGET_EXHAUSTED'):c.request('GET','/v3/projects')
    with pytest.raises(AlmError,match='RETRY_BUDGET_EXHAUSTED'):c._acquire(setup[2]())


def test_active_stream_keeps_permit_past_old_lease_expiry(setup):
    """SRS-053/054 OI-036: competing client cannot reclaim active permit."""
    db,instance,clock=setup
    calls=[]
    policy=HttpPolicy(requests_per_second=1000,burst=10,min_interval_ms=0,max_inflight=1,timeout_seconds=1,total_budget_seconds=100)
    competitor=client(setup,lambda _:calls.append('sent') or httpx.Response(200),policy=policy)
    competitor.policy=policy.model_copy(update={'total_budget_seconds':1})
    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            clock.now+=7
            with pytest.raises(AlmError,match='RETRY_BUDGET_EXHAUSTED'):competitor.request('GET','/v3/projects')
            assert calls==[]
            yield b'ok'
    c=client(setup,lambda _:httpx.Response(200,stream=Stream()),policy=policy)
    assert c.request('GET','/v3/projects').content==b'ok'
    with db.connect() as connection:assert connection.execute('SELECT count(*) FROM request_leases').fetchone()[0]==0


def test_nonfinite_retry_after_cannot_remove_pause(setup):
    """SRS-054: malformed nonfinite headers use bounded configured backoff."""
    c=client(setup,lambda _:httpx.Response(429,headers={'Retry-After':'NaN'}),policy=HttpPolicy(max_attempts=1,backoff_base_seconds=3))
    with pytest.raises(AlmError,match='RETRY_EXHAUSTED'):c.get_json('/v3/projects')
    with setup[0].connect() as connection:assert connection.execute('SELECT pause_until FROM server_budgets').fetchone()[0]>=1003


def _hold_stream_in_process(database_path,instance,ready,release,result):
    """Spawn target: separate process, synthetic stream, no sockets."""
    db=Database(database_path)
    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            ready.set()
            if not release.wait(10):raise RuntimeError('test-release-timeout')
            yield b'ok'
    policy=HttpPolicy(requests_per_second=1000,burst=10,min_interval_ms=0,max_inflight=1,timeout_seconds=1,total_budget_seconds=1)
    c=ALMHttpClient(db,instance,'https://alm.example.invalid',policy=policy,clock=lambda:1000.,
                    transport=httpx.MockTransport(lambda _:httpx.Response(200,stream=Stream())))
    try:result.put(c.request('GET','/v3/projects').content)
    except BaseException as error:result.put(type(error).__name__+':'+str(error))


def test_expired_active_slot_is_not_reclaimed_across_processes(setup):
    """SRS-053/054 OI-036: OS ownership survives SQLite deadline expiry."""
    import multiprocessing
    db,instance,clock=setup
    context=multiprocessing.get_context('spawn')
    ready=context.Event();release=context.Event();result=context.Queue()
    process=context.Process(target=_hold_stream_in_process,args=(str(db.path),instance,ready,release,result))
    process.start()
    try:
        assert ready.wait(5)
        clock.now=1007
        calls=[]
        c=client(setup,lambda _:calls.append(1) or httpx.Response(200),policy=HttpPolicy(total_budget_seconds=1))
        with pytest.raises(AlmError,match='RETRY_BUDGET_EXHAUSTED'):c.request('GET','/v3/projects')
        assert calls==[]
    finally:
        release.set();process.join(5)
        if process.is_alive():process.terminate();process.join(5)
    assert process.exitcode==0
    assert result.get(timeout=2)==b'ok'
    with db.connect() as connection:assert connection.execute('SELECT count(*) FROM request_leases').fetchone()[0]==0


def _crash_after_acquire(database_path,instance):
    import os
    db=Database(database_path)
    c=ALMHttpClient(db,instance,'https://alm.example.invalid',clock=lambda:1000.)
    c._acquire(1001.)
    os._exit(0)


def test_crashed_process_permit_recovers_after_expiry(setup):
    """SRS-053/054: process death releases OS ownership, stale DB lease expires."""
    import multiprocessing
    db,instance,clock=setup
    context=multiprocessing.get_context('spawn')
    process=context.Process(target=_crash_after_acquire,args=(str(db.path),instance))
    process.start();process.join(5)
    if process.is_alive():process.terminate();process.join(5)
    assert process.exitcode==0
    with db.connect() as connection:assert connection.execute('SELECT count(*) FROM request_leases').fetchone()[0]==1
    clock.now=1002
    c=client(setup,lambda _:httpx.Response(200,json={}))
    assert c.get_json('/v3/projects')=={}
    with db.connect() as connection:assert connection.execute('SELECT count(*) FROM request_leases').fetchone()[0]==0


def test_abort_during_stream_closes_and_releases(setup):
    aborted=False;closed=[]
    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            nonlocal aborted
            yield b'first'
            aborted=True
            yield b'second'
        def close(self):closed.append(True)
    c=client(setup,lambda _:httpx.Response(200,stream=Stream()),abort_check=lambda:aborted)
    with pytest.raises(AlmError,match='ABORTED'):c.request('GET','/v3/projects')
    assert closed
    with setup[0].connect() as connection:assert connection.execute('SELECT count(*) FROM request_leases').fetchone()[0]==0


def test_persisted_policy_change_applies_to_existing_clients(setup):
    db,_,clock=setup
    fast=HttpPolicy(requests_per_second=1000,burst=10,min_interval_ms=0,max_inflight=2)
    a=client(setup,lambda _:httpx.Response(200),policy=fast)
    b=client(setup,lambda _:httpx.Response(200),policy=fast)
    a.update_policy(fast.model_copy(update={'max_inflight':1}))
    permit=a._acquire(clock()+100)
    try:
        b.policy=fast.model_copy(update={'total_budget_seconds':1})
        with pytest.raises(AlmError,match='RETRY_BUDGET_EXHAUSTED'):b.request('GET','/v3/projects')
    finally:a._release(permit)


def test_database_symlink_alias_cannot_split_slot_ownership(setup,tmp_path):
    """SRS-053/054: two paths to one SQLite file share active OS slots."""
    db,instance,clock=setup
    alias=tmp_path/'alias.sqlite'
    try:alias.symlink_to(db.path)
    except OSError:pytest.skip('symlink creation not available on this platform')
    # Exercise expired SQLite lease: ownership must come from the same OS slot.
    policy=HttpPolicy(max_inflight=1,total_budget_seconds=1,min_interval_ms=0)
    a=client(setup,lambda _:httpx.Response(200),policy=policy)
    permit=a._acquire(1001)
    clock.now=1002
    b=ALMHttpClient(Database(alias),instance,'https://alm.example.invalid',policy=policy,
                    clock=clock,sleep=clock.sleep,transport=httpx.MockTransport(lambda _:httpx.Response(200)))
    try:
        with pytest.raises(AlmError,match='RETRY_BUDGET_EXHAUSTED'):b.request('GET','/v3/projects')
    finally:a._release(permit)


def test_permit_lock_is_released_when_sqlite_commit_fails(setup,monkeypatch):
    """SRS-053/054: failed reservation must not leak an untracked OS lock."""
    from contextlib import contextmanager
    db,_,clock=setup
    c=client(setup,lambda _:httpx.Response(200))
    original=db.transaction
    @contextmanager
    def failing_commit():
        with original() as connection:
            yield connection
            raise RuntimeError('synthetic commit failure')
    monkeypatch.setattr(db,'transaction',failing_commit)
    with pytest.raises(RuntimeError,match='synthetic commit failure'):c._acquire(clock()+10)
    assert c._permits=={}


def test_gzip_response_is_decoded_once(setup):
    """SRS-053: a Content-Encoding: gzip reply must not be decoded a second time."""
    import gzip
    payload=gzip.compress(b'[{"id":1}]')
    c=client(setup,lambda _:httpx.Response(200,headers={'Content-Encoding':'gzip'},content=payload))
    assert c.get_json('/v3/projects')==[{'id':1}]
