"""M1 mock acceptance over actual SQLite migrations and independent processes."""
import os
from pathlib import Path
import subprocess
import time
import sys

import pytest
from fastapi.testclient import TestClient

from almrag.api import create_app
from almrag.config import Settings
from almrag.queue import Queue, LeaseLost
from almrag.security import SecretVault
from almrag.storage import Database
from almrag.worker import run_once
from cryptography.fernet import Fernet


def setup_db(tmp_path):
    db=Database(tmp_path/'nested'/'alm.sqlite');db.migrate()
    first=db.add_instance('codebeamer','https://cb.example.invalid','same','ref-cb')
    second=db.add_instance('polarion','https://po.example.invalid','same','ref-po')
    return db,db.add_project(first,'42','same'),db.add_project(second,'42','same')


def test_actual_database_auth_worker_and_events(tmp_path):
    db,p1,p2=setup_db(tmp_path)
    q=Queue(db)
    job=q.enqueue(p1,'COLLECT')
    run_once(q,'synthetic-worker')
    assert q.get_job(job['job_id'])['last_error_code']=='STAGE_UNAVAILABLE'
    app=create_app(Settings(database_path=str(db.path)))
    _,key=app.state.security.create_key('reader',[p1],['project_read'],actor='admin')
    _,other_key=app.state.security.create_key('other',[p2],['project_read'],actor='admin')
    vault=SecretVault(db,Fernet.generate_key());vault.put('fixture','synthetic-private-value')
    assert vault.get('fixture')=='synthetic-private-value'
    with TestClient(app,base_url='https://testserver') as client:
        headers={'X-API-Key':key}
        assert client.get('/api/v1/jobs/'+job['job_id'],headers=headers).json()['state']=='BLOCKED'
        events=client.get('/api/v1/jobs/'+job['job_id']+'/events',headers=headers)
        assert events.status_code==200
        assert events.json()[-1]['error_code']=='STAGE_UNAVAILABLE'
        assert client.get('/api/v1/jobs/'+job['job_id']+'/events',headers={'X-API-Key':other_key}).status_code==404
        assert 'fencing_token' not in client.get('/api/v1/jobs',headers=headers).text
        assert client.get('/api/v1/projects',headers=headers).json()[0]['project_uid']==p1


def test_process_crash_checkpoint_and_fencing(tmp_path):
    db,p1,_=setup_db(tmp_path)
    job=Queue(db).enqueue(p1,'PROCESS')
    source="""import sys,time
from almrag.storage import Database
from almrag.queue import Queue
q=Queue(Database(sys.argv[1]));j=q.claim('crashed-process');q.checkpoint(j['job_id'],j['fencing_token'],{'offset':7});print(j['fencing_token'],flush=True);time.sleep(60)
"""
    process=subprocess.Popen([sys.executable,'-c',source,str(db.path)],stdout=subprocess.PIPE,text=True)
    try:
        token=process.stdout.readline().strip()
        assert token
    finally:
        process.terminate();process.wait(timeout=10)
    with db.transaction() as c:
        c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(job['job_id'],))
    q=Queue(Database(db.path));resumed=q.claim('replacement')
    assert resumed['checkpoint']=={'offset':7}
    with pytest.raises(LeaseLost):q.finish(job['job_id'],token)
    q.finish(job['job_id'],resumed['fencing_token'])


def test_worker_lost_lease_emits_no_blocked_success(capsys):
    class StaleQueue:
        def claim(self,*args,**kwargs):return {'job_id':'synthetic','fencing_token':'old','stage':'COLLECT'}
        def finish(self,*args,**kwargs):raise LeaseLost('expired')
    with pytest.raises(LeaseLost):run_once(StaleQueue(),'worker')
    assert 'job_blocked' not in capsys.readouterr().out


def test_native_cli_and_separate_worker(tmp_path):
    db,p1,_=setup_db(tmp_path)
    job=Queue(db).enqueue(p1,'SYNC')
    env={**os.environ,'ALMRAG_DATABASE_PATH':str(db.path)}
    migrated=subprocess.run([sys.executable,'-m','almrag.cli','migrate'],env=env,capture_output=True,text=True,timeout=10)
    assert migrated.returncode==0
    worker=subprocess.run([sys.executable,'-m','almrag.worker','--once'],env=env,capture_output=True,text=True,timeout=10)
    assert worker.returncode==0
    assert Queue(db).get_job(job['job_id'])['state']=='BLOCKED'
    assert Queue(db).get_job(job['job_id'])['last_error_code']=='PIPELINE_SNAPSHOT_MISSING'


def test_pause_queued_job_is_never_claimed_and_running_job_pauses_cooperatively(tmp_path):
    db,p1,_=setup_db(tmp_path);q=Queue(db)
    queued=q.enqueue(p1,'COLLECT')
    paused=q.request_pause(queued['job_id'])
    assert (paused['state'],paused['last_error_code'])==('PAUSED','ABORT_REQUESTED') and q.claim('w') is None
    assert q.request_pause(queued['job_id']).get('rejected') and q.request_pause('missing') is None
    running=q.enqueue(p1,'COLLECT')

    class Service:
        def run(self,job,abort_check):
            q.request_pause(job['job_id'])
            for _ in range(100):
                if abort_check():return q.finish(job['job_id'],job['fencing_token'],state='PAUSED',error_code='ABORT_REQUESTED')
                time.sleep(0.05)
            q.finish(job['job_id'],job['fencing_token'])
    run_once(q,'w',Service(),heartbeat_interval=0.1)
    done=q.get_job(running['job_id'])
    assert (done['state'],done['last_error_code'])==('PAUSED','ABORT_REQUESTED') and not q.pause_requested(running['job_id'])
