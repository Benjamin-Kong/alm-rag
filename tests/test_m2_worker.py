"""SRS-026/055/057/058: worker integration, lease renewal and fail-closed exits."""
import json
from pathlib import Path
import sqlite3
import threading
import time

import pytest

from almrag.queue import Queue, LeaseLost
from almrag.storage import Database
from almrag.worker import healthy, run_once


def test_configured_worker_honors_attachment_directory(tmp_path,monkeypatch):
    """SRS-005: API and worker must persist to the same configured directory."""
    from almrag.config import Settings
    from almrag.worker import _ConfiguredCollection
    import almrag.collection
    captured=[]
    class Service:
        def __init__(self,db,factory,root):captured.append(Path(root))
        def run(self,job,abort_check):return 'SUCCEEDED'
    monkeypatch.setattr(almrag.collection,'CollectionService',Service)
    settings=Settings(database_path=str(tmp_path/'db/data.sqlite'),attachment_root=str(tmp_path/'custom-assets'))
    assert _ConfiguredCollection(Database(settings.database_path),settings).run({},lambda:False)=='SUCCEEDED'
    assert captured==[tmp_path/'custom-assets']


class CountingQueue(Queue):
    def __init__(self,db):
        super().__init__(db)
        self.beats=0
        self.finishes=[]
    def heartbeat(self,*args,**kwargs):
        super().heartbeat(*args,**kwargs)
        self.beats+=1
    def finish(self,*args,**kwargs):
        super().finish(*args,**kwargs)
        self.finishes.append((args,kwargs))


@pytest.fixture
def queued(tmp_path):
    db=Database(tmp_path/'data.sqlite'); db.migrate()
    instance=db.add_instance('codebeamer','https://fixture.invalid','Fixture','env:FIXTURE')
    project=db.add_project(instance,'p','Project')
    q=CountingQueue(db)
    job=q.enqueue(project,'COLLECT')
    return db,q,job,tmp_path/'worker-health.json'


def test_collection_service_owns_terminal_transition(queued):
    db,q,job,path=queued
    class Service:
        def run(self,claimed,abort_check):
            assert claimed['state']=='RUNNING' and not abort_check()
            q.finish(claimed['job_id'],claimed['fencing_token'],'COMPLETED_WITH_ERRORS')
            return 'COMPLETED_WITH_ERRORS'
    assert run_once(q,'worker',Service(),health_path=path)
    assert q.get_job(job['job_id'])['state']=='COMPLETED_WITH_ERRORS'
    assert len(q.finishes)==1
    assert not [t for t in threading.enumerate() if t.name.startswith('almrag-heartbeat-')]


def test_heartbeat_and_health_survive_long_collection(queued):
    db,q,job,path=queued
    class Service:
        def run(self,claimed,abort_check):
            first=claimed['lease_expires_at']
            initial=json.loads(path.read_text())['timestamp']
            deadline=time.monotonic()+3
            while time.time() <= first+0.04:
                assert time.monotonic()<deadline
                assert not abort_check()
                threading.Event().wait(.01)
            # The original lease has elapsed; independent claim still cannot steal it.
            assert Queue(db).claim('other',lease_seconds=1) is None
            assert q.beats>=2 and healthy(path)
            assert json.loads(path.read_text())['timestamp']>initial
            q.finish(claimed['job_id'],claimed['fencing_token'],'SUCCEEDED')
            return 'SUCCEEDED'
    assert run_once(q,'long',Service(),health_path=path,lease_seconds=.25,heartbeat_interval=.025)
    assert q.get_job(job['job_id'])['state']=='SUCCEEDED'


def test_lease_loss_aborts_running_service_without_finish(queued):
    db,q,job,path=queued
    class Service:
        def run(self,claimed,abort_check):
            with db.transaction() as c:
                c.execute('UPDATE jobs SET fencing_token=? WHERE job_id=?',('replacement',claimed['job_id']))
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                abort_check()
                threading.Event().wait(.01)
            pytest.fail('worker did not signal lease loss')
    with pytest.raises(LeaseLost):
        run_once(q,'old',Service(),health_path=path,lease_seconds=.5,heartbeat_interval=.01)
    assert q.finishes==[] and q.get_job(job['job_id'])['fencing_token']=='replacement'
    assert not [t for t in threading.enumerate() if t.name.startswith('almrag-heartbeat-')]


def test_stop_callback_reaches_service_cancellation(queued):
    db,q,job,path=queued; stopped=threading.Event()
    class Service:
        def run(self,claimed,abort_check):
            stopped.set()
            assert abort_check()
            q.finish(claimed['job_id'],claimed['fencing_token'],'CANCELLED','ABORT_REQUESTED')
            return 'CANCELLED'
    assert run_once(q,'worker',Service(),stop_check=stopped.is_set,health_path=path)
    assert q.get_job(job['job_id'])['state']=='CANCELLED'


def test_unsupported_stage_and_missing_service_remain_blocked(queued):
    db,q,job,path=queued
    class NeverService:
        def run(self,*args,**kwargs): pytest.fail('unsupported stage invoked collector')
    assert run_once(q,'worker')
    assert q.get_job(job['job_id'])['last_error_code']=='STAGE_UNAVAILABLE'
    unsupported=q.enqueue(job['project_uid'],'SYNC')
    assert run_once(q,'worker',NeverService())
    assert q.get_job(unsupported['job_id'])['last_error_code']=='STAGE_UNAVAILABLE'


def test_unexpected_service_exception_is_sanitized_and_blocked(queued,capsys):
    db,q,job,path=queued
    class Broken:
        def run(self,*args,**kwargs): raise RuntimeError('synthetic private error body')
    assert run_once(q,'worker',Broken(),health_path=path)
    final=q.get_job(job['job_id'])
    assert final['state']=='BLOCKED' and final['last_error_code']=='WORKER_ERROR'
    assert 'private error body' not in capsys.readouterr().out


def test_background_heartbeat_failure_aborts_without_false_success(queued):
    db,q,job,path=queued
    def broken_heartbeat(*args,**kwargs): raise LeaseLost('injected stale lease')
    q.heartbeat=broken_heartbeat
    class Service:
        def run(self,claimed,abort_check):
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                abort_check()
                threading.Event().wait(.01)
            pytest.fail('background lease failure was not delivered')
    with pytest.raises(LeaseLost): run_once(q,'worker',Service(),heartbeat_interval=.01)
    assert q.finishes==[]


def test_empty_queue_does_not_invoke_service(queued):
    db,q,job,path=queued; assert run_once(q,'worker')
    class Never:
        def run(self,*args,**kwargs): pytest.fail('empty queue invoked service')
    assert run_once(q,'worker',Never()) is False


def test_invalid_renewal_parameters_do_not_claim_job(queued):
    db,q,job,path=queued
    for kwargs in [{'lease_seconds':0},{'heartbeat_interval':0},{'heartbeat_interval':float('nan')}]:
        with pytest.raises(ValueError): run_once(q,'worker',object(),**kwargs)
    assert q.get_job(job['job_id'])['state']=='QUEUED'


def migrate_collection(db):
    # Worktree M1 runner is frozen; Main's ordered runner applies002 natively.
    with db.transaction() as c:
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='collection_configs'").fetchone():
            return
        buffer=''
        for line in (Path(__file__).parents[1]/'src/almrag/migrations/002_collection.sql').read_text().splitlines(True):
            buffer+=line
            if sqlite3.complete_statement(buffer): c.execute(buffer); buffer=''


def test_actual_collection_service_long_attachment_and_outcomes(queued):
    """SRS-026/055: actual SQLite+collection completes despite a long source request."""
    from almrag.collection import CollectionService
    from test_collection import Adapter, SourceError
    db,q,unused,path=queued
    # queued fixture's arbitrary COLLECT job has no snapshot and is intentionally blocked.
    run_once(q,'foundation')
    migrate_collection(db)
    with db.connect() as c: instance=c.execute('SELECT instance_uid FROM instances').fetchone()[0]
    adapter=Adapter(); adapter.fail['1']=SourceError('ITEM_INVALID')
    service=CollectionService(db,lambda _:adapter,path.parent/'assets')
    project=service.configure_project(instance,'p','Project')
    job=service.enqueue(project)
    original=adapter.download_attachment
    def slow(*args):
        deadline=time.monotonic()+.32
        while time.monotonic()<deadline: threading.Event().wait(.01)
        assert q.beats>=2 and healthy(path)
        return original(*args)
    adapter.download_attachment=slow
    assert run_once(q,'collector',service,health_path=path,lease_seconds=.2,heartbeat_interval=.02)
    final=q.get_job(job['job_id'])
    assert final['state']=='COMPLETED_WITH_ERRORS'
    assert (final['progress_total'],final['succeeded_items'],final['failed_items'])==(2,1,1)
    # CollectionService uses its own Queue, so the spy records only initial fail-closed finish.
    assert len(q.finishes)==1
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM collection_failures').fetchone()[0]==1


def test_actual_collection_service_stop_prevents_late_result_commit(queued):
    """SRS-055: termination after remote work stops publication and writes CANCELLED."""
    from almrag.collection import CollectionService
    from test_collection import Adapter
    db,q,unused,path=queued; run_once(q,'foundation'); migrate_collection(db)
    with db.connect() as c: instance=c.execute('SELECT instance_uid FROM instances').fetchone()[0]
    adapter=Adapter(); stopped=threading.Event()
    service=CollectionService(db,lambda _:adapter,path.parent/'assets')
    project=service.configure_project(instance,'p','Project'); job=service.enqueue(project)
    original=adapter.get_item
    def stop_after_request(*args):
        stopped.set()
        return original(*args)
    adapter.get_item=stop_after_request
    assert run_once(q,'collector',service,stop_check=stopped.is_set,health_path=path)
    assert q.get_job(job['job_id'])['state']=='PAUSED'
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM collection_outcomes').fetchone()[0]==0
