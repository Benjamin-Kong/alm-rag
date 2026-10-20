"""SRS-026/056 durable queue and fencing."""
from concurrent.futures import ProcessPoolExecutor
import pytest
from almrag.storage import Database
from almrag.queue import Queue,LeaseLost
from test_storage import db,project
def claim(path): return Queue(Database(path)).claim('process')
def test_recovery(db):
    q=Queue(db); a=q.enqueue(project(db),'collect'); b=q.enqueue(project(db,'2'),'collect')
    r=q.claim('one'); t=r['fencing_token']; assert r['job_id']==a['job_id']; assert q.claim('two') is None
    q.checkpoint(a['job_id'],t,{'offset':3}); q.heartbeat(a['job_id'],t)
    with db.transaction() as c: c.execute('UPDATE jobs SET lease_expires_at=0')
    with pytest.raises(LeaseLost): q.finish(a['job_id'],t)
    assert q.recover_expired()==1
    r=Queue(Database(db.path)).claim('restart'); assert r['checkpoint']=={'offset':3}
    with pytest.raises(LeaseLost): q.checkpoint(a['job_id'],t,{})
    q.finish(a['job_id'],r['fencing_token'],'BLOCKED',error_code='STAGE_UNAVAILABLE')
    assert q.get_job(a['job_id'])['last_error_code']=='STAGE_UNAVAILABLE'
    r=q.claim('next'); assert r['job_id']==b['job_id']; q.finish(b['job_id'],r['fencing_token'],'PAUSED'); assert q.claim('none') is None
def test_process_exclusion(db):
    q=Queue(db)
    for i in range(4): q.enqueue(project(db,str(i)),'collect')
    with ProcessPoolExecutor(max_workers=3) as p: results=list(p.map(claim,[str(db.path)]*3))
    assert sum(r is not None for r in results)==1
