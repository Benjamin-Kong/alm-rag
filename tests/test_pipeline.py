"""SRS-023/025/026/049/055/056: fenced SYNC and bounded internal replay."""
import json

import pytest

from test_collection import setup as collection_setup, SourceError
from test_processing import Runtime, reprofile
from test_indexing import MemoryVector
from almrag.processing import ProcessingService, ProcessingError
from almrag.pipeline import PipelineService, PipelineError
from almrag.indexing import IndexService
from almrag.queue import Queue, LeaseLost


@pytest.fixture
def setup(collection_setup):
    db,adapter,collection,project=collection_setup
    runtime=Runtime();processing=ProcessingService(db,lambda p:runtime,allow_fixture=True)
    vector=MemoryVector();index=IndexService(db,processing,vector)
    pipeline=PipelineService(db,collection,processing,index)
    return db,adapter,project,runtime,pipeline,index


def run(data,queued=None):
    db,_,project,_,pipeline,_=data
    queued=queued or pipeline.enqueue(project)
    job=Queue(db).claim('pipeline-fixture',300)
    assert job['job_id']==queued['job_id']
    return pipeline.run(job),Queue(db).get_job(job['job_id'])


def counts(db):
    with db.connect() as c:
        return c.execute('SELECT count(*) FROM items WHERE active_revision_uid IS NOT NULL').fetchone()[0]


def test_sync_real_services_one_parent_and_unchanged_zero_embedding(setup):
    db,a,p,r,s,index=setup
    pre=s.preflight(p);assert pre['sync_ready'] and pre['estimated_items']==2
    state,job=run(setup,s.enqueue(p,config_revision=pre['config_revision']))
    assert state=='SUCCEEDED' and counts(db)==2
    assert (job['progress_total'],job['succeeded_items'],job['failed_items'])==(2,2,0)
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM jobs').fetchone()[0]==1
        assert c.execute("SELECT count(*) FROM job_events WHERE state='SUCCEEDED'").fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM pipeline_steps').fetchone()[0]==4
        assert c.execute('SELECT count(*) FROM index_outcomes').fetchone()[0]==2
    calls=len(r.calls);assert run(setup)[0]=='SUCCEEDED' and len(r.calls)==calls


def test_sync_100_refs_three_local_failures_replay_without_source(setup):
    db,a,p,r,s,index=setup
    a.refs=[{'id':str(i),'scope_id':'t1','revision':'1'} for i in range(100)]
    original=r.embed
    def embed(text,**kw):
        if any(('Title '+str(i)+'\n') in text for i in (2,44,78)):raise ProcessingError('INPUT_REJECTED',False)
        return original(text,**kw)
    r.embed=embed
    state,job=run(setup)
    assert state=='COMPLETED_WITH_ERRORS' and counts(db)==97
    assert (job['progress_total'],job['succeeded_items'],job['failed_items'])==(100,97,3)
    failures=s.list_failures(job['job_id']);assert len(failures)==3 and {f['failed_stage'] for f in failures}=={'EMBED'}
    r.embed=original
    a.get_item=lambda *args:pytest.fail('EMBED replay fetched source')
    replays=s.retry_all(job['job_id'])
    for replay in replays:assert run(setup,replay)[0]=='SUCCEEDED'
    assert counts(db)==100
    with db.connect() as c:
        assert c.execute("SELECT count(*) FROM failed_items WHERE replay_state='RESOLVED'").fetchone()[0]==3
        assert c.execute('SELECT count(*) FROM index_points').fetchone()[0]==c.execute('SELECT count(DISTINCT point_uuid) FROM index_points').fetchone()[0]


def test_sync_collection_failure_has_no_invented_revision(setup):
    db,a,p,r,s,index=setup;a.fail['0']=SourceError('ITEM_INVALID')
    state,job=run(setup)
    assert state=='COMPLETED_WITH_ERRORS' and counts(db)==1
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM failed_items').fetchone()[0]==0
    failure=s.list_failures(job['job_id'])[0]
    assert failure['revision_uid'] is None and failure['source_item_id']=='0'


def test_replay_idempotency_scope_and_revision_guards(setup):
    db,a,p,r,s,index=setup;r.error=ProcessingError('INPUT_REJECTED',False)
    _,job=run(setup);failure=s.list_failures(job['job_id'])[0];r.error=None
    retry=s.retry(job['job_id'],failure['item_uid'],expected_revision_uid=failure['revision_uid'])
    assert s.retry(job['job_id'],failure['item_uid'])['job_id']==retry['job_id']
    with pytest.raises(PipelineError,match='STALE_REVISION'):s.retry(job['job_id'],failure['item_uid'],expected_revision_uid='wrong')
    with db.transaction() as c:c.execute("UPDATE collection_memberships SET state='OUT_OF_SCOPE' WHERE source_item_id=?",(failure['source_item_id'],))
    assert run(setup,retry)[0]=='BLOCKED' and counts(db)==0
    with pytest.raises(PipelineError,match='REPLAY_SCOPE_CHANGED'):s.retry(job['job_id'],failure['item_uid'])


def test_new_model_partial_sync_cannot_switch_generation(setup):
    db,a,p,r,s,index=setup;assert run(setup)[0]=='SUCCEEDED'
    with db.connect() as c:old=c.execute('SELECT active_generation_uid FROM projects WHERE project_uid=?',(p,)).fetchone()[0]
    reprofile(r,expected_digest='sha256:'+'b'*64);r.error=ProcessingError('INPUT_REJECTED',False)
    assert run(setup)[0]=='BLOCKED'
    with db.connect() as c:assert c.execute('SELECT active_generation_uid FROM projects WHERE project_uid=?',(p,)).fetchone()[0]==old


def test_global_auth_stops_before_embedding(setup):
    db,a,p,r,s,index=setup;a.fail['0']=SourceError('UNAUTHORIZED',True)
    state,job=run(setup)
    assert state=='BLOCKED' and not r.calls and job['last_error_code']=='UNAUTHORIZED'


def test_crash_reclaim_retains_checkpoints_and_lost_fence(setup):
    db,a,p,r,s,index=setup
    class Crash(BaseException):pass
    def crash(event):
        if event=='after_PROCESS':raise Crash()
    s.fault_hook=crash;s.enqueue(p);job=Queue(db).claim('old',300)
    with pytest.raises(Crash):s.run(job)
    with db.transaction() as c:c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(job['job_id'],))
    with pytest.raises(LeaseLost):s.run(job)
    s.fault_hook=lambda e:None
    assert s.run(Queue(db).claim('new',300))=='SUCCEEDED' and counts(db)==2


def test_pause_resume_and_config_drift_guard(setup):
    db,a,p,r,s,index=setup;r.error=ProcessingError('MODEL_SERVER_PAUSED',stop_state='PAUSED')
    state,job=run(setup);assert state=='PAUSED'
    r.error=None;assert run(setup,s.resume(job['job_id']))[0]=='SUCCEEDED'
    with pytest.raises(PipelineError,match='RESUME_STATE_INVALID'):s.resume(job['job_id'])
    reprofile(r,expected_digest='sha256:'+'b'*64)
    r.error=ProcessingError('MODEL_SERVER_PAUSED',stop_state='PAUSED');_,job=run(setup)
    reprofile(r,expected_digest='sha256:'+'c'*64)
    with pytest.raises(PipelineError,match='MODEL_RUNTIME_DRIFT'):s.resume(job['job_id'])


def test_model_response_schema_mismatch_block_is_resumable(setup):
    db,a,p,r,s,index=setup;r.error=ProcessingError('MODEL_RESPONSE_SCHEMA_MISMATCH')
    state,job=run(setup);assert state=='BLOCKED' and job['last_error_code']=='MODEL_RESPONSE_SCHEMA_MISMATCH'
    r.error=None;assert run(setup,s.resume(job['job_id']))[0]=='SUCCEEDED'


def test_queued_model_drift_blocks_before_collection(setup):
    db,a,p,r,s,index=setup;queued=s.enqueue(p);reprofile(r,expected_digest='sha256:'+'b'*64)
    a.get_item=lambda *args:pytest.fail('drift fetched source')
    assert run(setup,queued)[0]=='BLOCKED'


def test_collect_replay_without_revision_preserves_sibling_membership(setup):
    db,a,p,r,s,index=setup;a.fail['0']=SourceError('ITEM_INVALID')
    _,job=run(setup);a.fail={}
    queued=s.retry(job['job_id'],'0')
    assert run(setup,queued)[0]=='SUCCEEDED' and counts(db)==2
    with db.connect() as c:
        assert {x[0] for x in c.execute('SELECT state FROM collection_memberships')}=={'IN_SCOPE'}
        assert c.execute('SELECT replay_state FROM collection_failures WHERE job_id=?',(job['job_id'],)).fetchone()[0]=='RESOLVED'


def test_recollect_new_revision_crash_resumes_its_own_pinned_revision(setup):
    db,a,p,r,s,index=setup;r.error=ProcessingError('INPUT_REJECTED',False)
    _,job=run(setup);failure=s.list_failures(job['job_id'])[0];r.error=None
    original=a.get_item
    def changed(project,item):
        value=original(project,item);value['revision']='2';return value
    a.get_item=changed
    queued=s.retry(job['job_id'],failure['item_uid'],force_recollect=True)
    class Crash(BaseException):pass
    def fault(event):
        if event=='after_PROCESS':raise Crash()
    s.fault_hook=fault;claimed=Queue(db).claim('old',300)
    with pytest.raises(Crash):s.run(claimed)
    with db.transaction() as c:c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(queued['job_id'],))
    s.fault_hook=lambda e:None
    assert s.run(Queue(db).claim('new',300))=='SUCCEEDED'


def test_runtime_callback_restored_after_global_failure(setup):
    db,a,p,r,s,index=setup;previous=r.abort_check
    r.error=ProcessingError('MODEL_SERVER_PAUSED',stop_state='PAUSED')
    assert run(setup)[0]=='PAUSED' and r.abort_check is previous


def test_resume_rejects_scope_change_in_checkpointed_sync(setup):
    db,a,p,r,s,index=setup;r.error=ProcessingError('MODEL_SERVER_PAUSED',stop_state='PAUSED')
    _,job=run(setup);r.error=None
    with db.transaction() as c:c.execute("UPDATE collection_memberships SET state='UNAUTHORIZED'")
    with pytest.raises(PipelineError,match='PINNED_INPUT_CHANGED'):s.resume(job['job_id'])


def test_replay_rejects_newly_excluded_scope_before_next_collection(setup):
    db,a,p,r,s,index=setup;r.error=ProcessingError('INPUT_REJECTED',False)
    _,job=run(setup);failure=s.list_failures(job['job_id'])[0]
    with db.connect() as c:instance=c.execute('SELECT instance_uid FROM projects WHERE project_uid=?',(p,)).fetchone()[0]
    s.collection.configure_project(instance,'p','Project',selection_mode='SELECTED',scope_ids=['t2'])
    with pytest.raises(PipelineError,match='REPLAY_SCOPE_CHANGED'):s.retry(job['job_id'],failure['item_uid'])


def test_retry_can_find_failure_beyond_first_page(setup,monkeypatch):
    db,a,p,r,s,index=setup;r.error=ProcessingError('INPUT_REJECTED',False)
    _,job=run(setup);failure=s.list_failures(job['job_id'])[0]
    filler=dict(failure,item_uid='different',source_item_id='different')
    monkeypatch.setattr(s,'list_failures',lambda job_id,limit=100,offset=0:[filler]*1000 if offset==0 else [failure])
    assert s.retry(job['job_id'],failure['item_uid'])['stage']=='REPLAY'


def test_sync_reuses_fresh_preflight_catalog_instead_of_relisting_source(setup):
    db,a,p,r,s,index=setup
    seen=[]
    original=s.collection._preflight
    s.collection._preflight=lambda uid:(seen.append(uid),original(uid))[1]
    pre=s.preflight(p);s.enqueue(p,config_revision=pre['config_revision'])
    assert seen==[p]
    s.enqueue(p)
    assert seen==[p,p]
