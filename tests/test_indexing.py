"""SRS-020/021/024/049/055: fenced publication, rebuild and live readers."""
import copy
import json
import pytest
from test_processing import setup, add_item, execute, reprofile
from almrag.indexing import IndexService, IndexError
from almrag.queue import Queue, LeaseLost
from almrag.readers import ReaderRegistry
from almrag.embedding import fingerprint

class MemoryVector:
    def __init__(self): self.collections={};self.corrupt=False;self.hook=None;self.calls=[];self.abort_check=lambda:False
    def ensure_collection(self,name,dimension): self.collections.setdefault(name,{})
    def upsert(self,name,points):
        assert not self.abort_check()
        self.calls.append(('upsert',name))
        for p in points:self.collections[name][p['id']]=copy.deepcopy(p)
        if self.hook:self.hook()
    def retrieve(self,name,ids):
        result=[copy.deepcopy(self.collections[name][i]) for i in ids if i in self.collections[name]]
        if self.corrupt and result:result[0]['payload']['revision_uid']='corrupt'
        return result
    def delete_collection(self,name): self.collections.pop(name,None);self.calls.append(('delete',name))

def ready(data):
    assert execute(data)[0]=='SUCCEEDED'
    assert execute(data,'EMBED')[0]=='SUCCEEDED'

def run(data,index,stage='INDEX'):
    db,_,p,_,_=data
    queued=index.enqueue(p,stage)
    job=Queue(db).claim('index',300)
    assert job['job_id']==queued['job_id']
    return index.run(job),job

def active(data):
    db,_,p,_,_=data
    with db.connect() as c:
        return c.execute('SELECT active_generation_uid FROM projects WHERE project_uid=?',(p,)).fetchone()[0],{r[0]:r[1] for r in c.execute('SELECT item_uid,active_revision_uid FROM items WHERE project_uid=?',(p,))}

def test_index_idempotent_exact_coverage_and_normalized_vectors(setup):
    db,_,p,r,s=setup;revision=add_item(setup);ready(setup);store=MemoryVector();index=IndexService(db,s,store)
    assert run(setup,index)[0]=='SUCCEEDED'
    generation,items=active(setup);assert set(items.values())=={revision}
    calls=len(r.calls)
    assert run(setup,index)[0]=='SUCCEEDED'
    assert active(setup)[0]==generation and len(r.calls)==calls
    with db.connect() as c:
        count=c.execute('SELECT count(*) FROM chunks').fetchone()[0]
        assert c.execute('SELECT count(*) FROM index_points').fetchone()[0]==count
        assert c.execute('SELECT count(*) FROM keyword_documents').fetchone()[0]==count
    vectors=list(store.collections.values())[0]
    assert all(abs(sum(v*v for v in x['vector'])-1)<1e-6 for x in vectors.values())

def test_item_with_more_chunks_than_store_batch_limit_is_indexed_in_batches(setup,monkeypatch):
    import almrag.indexing as indexing
    monkeypatch.setattr(indexing,'VECTOR_BATCH_SIZE',1)
    db,_,p,r,s=setup;revision=add_item(setup);ready(setup)
    class Capped(MemoryVector):
        def upsert(self,name,points):
            assert len(points)<=1;super().upsert(name,points)
        def retrieve(self,name,ids):
            assert len(ids)<=1;return super().retrieve(name,ids)
    store=Capped();index=IndexService(db,s,store)
    assert run(setup,index)[0]=='SUCCEEDED'
    with db.connect() as c:count=c.execute('SELECT count(*) FROM chunks').fetchone()[0]
    assert count>1 and sum(1 for call in store.calls if call[0]=='upsert')==count
    assert set(active(setup)[1].values())=={revision}

def test_unready_item_failure_keeps_old_and_continues_sibling(setup):
    db,_,p,r,s=setup;old=add_item(setup);ready(setup);index=IndexService(db,s,MemoryVector());assert run(setup,index)[0]=='SUCCEEDED'
    new=add_item(setup,revision='2');other=add_item(setup,'2');ready(setup)
    with db.transaction() as c:c.execute("UPDATE processing_results SET state='PROCESS_READY' WHERE revision_uid=?",(new,))
    assert run(setup,index)[0]=='COMPLETED_WITH_ERRORS'
    assert set(active(setup)[1].values())=={old,other}
    with db.connect() as c:assert c.execute("SELECT revision_uid FROM failed_items WHERE failed_stage='INDEX'").fetchone()[0]==new

def test_corrupt_remote_never_publishes(setup):
    db,_,p,r,s=setup;add_item(setup);ready(setup);store=MemoryVector();store.corrupt=True;index=IndexService(db,s,store)
    state,job=run(setup,index)
    assert state=='BLOCKED' and active(setup)[0] is None
    assert Queue(db).get_job(job['job_id'])['last_error_code']=='DENSE_COVERAGE_MISMATCH'

def test_config_change_requires_complete_rebuild_and_reader_defers_cleanup(setup):
    db,_,p,r,s=setup;add_item(setup);ready(setup);store=MemoryVector();readers=ReaderRegistry(db);index=IndexService(db,s,store,readers=readers)
    assert run(setup,index)[0]=='SUCCEEDED';old=active(setup)[0]
    reprofile(r,expected_digest='sha256:'+'b'*64)
    with pytest.raises(IndexError,match='REBUILD_REQUIRED'):index.enqueue(p)
    assert run(setup,index,'REBUILD')[0]=='BLOCKED' and active(setup)[0]==old
    ready(setup)
    with readers.snapshot([p]):
        assert run(setup,index,'REBUILD')[0]=='SUCCEEDED'
        assert active(setup)[0]!=old
        index.cleanup()
        assert len(store.collections)==2
    index.cleanup()
    assert len(store.collections)==1
    with db.connect() as c:assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==1

def test_staging_crash_reclaim_and_scope_change_do_not_activate(setup):
    db,_,p,r,s=setup;revision=add_item(setup);ready(setup);store=MemoryVector()
    class Crash(BaseException):pass
    def fault(event):
        if event=='after_dense':raise Crash()
    index=IndexService(db,s,store,fault_hook=fault);q=index.enqueue(p);job=Queue(db).claim('old',300)
    with pytest.raises(Crash):index.run(job)
    assert active(setup)[0] is None
    with db.transaction() as c:c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(job['job_id'],))
    restarted=IndexService(db,s,store)
    assert restarted.run(Queue(db).claim('new',300))=='SUCCEEDED'
    old=active(setup)
    add_item(setup,revision='2');ready(setup)
    def scope_change(event):
        if event=='before_publish':
            with db.transaction() as c:c.execute("UPDATE collection_memberships SET state='OUT_OF_SCOPE'")
    assert run(setup,IndexService(db,s,store,fault_hook=scope_change))[0]=='COMPLETED_WITH_ERRORS'
    assert active(setup)==old

def test_lost_lease_during_upload_prevents_publication(setup):
    db,_,p,r,s=setup;add_item(setup);ready(setup);store=MemoryVector();index=IndexService(db,s,store);index.enqueue(p);job=Queue(db).claim('old',300)
    def expire():
        with db.transaction() as c:c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(job['job_id'],))
    store.hook=expire
    with pytest.raises(LeaseLost):index.run(job)
    assert active(setup)[0] is None

def test_queued_model_drift_blocks_before_remote(setup):
    db,_,p,r,s=setup;add_item(setup);ready(setup);store=MemoryVector();index=IndexService(db,s,store);index.enqueue(p);job=Queue(db).claim('owner',300)
    reprofile(r,expected_digest='sha256:'+'b'*64)
    assert index.run(job)=='BLOCKED' and store.collections=={}

def test_rebuild_crash_after_atomic_publication_recovers_without_duplicate(setup):
    db,_,p,r,s=setup;add_item(setup);ready(setup);store=MemoryVector();index=IndexService(db,s,store);assert run(setup,index)[0]=='SUCCEEDED'
    class Crash(BaseException):pass
    def crash(event):
        if event=='after_publish':raise Crash()
    rebuilding=IndexService(db,s,store,fault_hook=crash);rebuilding.enqueue(p,'REBUILD');job=Queue(db).claim('old',300)
    with pytest.raises(Crash):rebuilding.run(job)
    published=active(setup)
    with db.transaction() as c:c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(job['job_id'],))
    assert index.run(Queue(db).claim('new',300))=='SUCCEEDED'
    assert active(setup)==published

def test_missing_old_active_is_required_rebuild_coverage(setup):
    db,_,p,r,s=setup;add_item(setup);ready(setup);store=MemoryVector();index=IndexService(db,s,store);assert run(setup,index)[0]=='SUCCEEDED';old=active(setup)
    with db.transaction() as c:c.execute("UPDATE collection_memberships SET state='MISSING'")
    reprofile(r,expected_digest='sha256:'+'b'*64)
    assert run(setup,index,'REBUILD')[0]=='BLOCKED'
    assert active(setup)==old
    with db.connect() as c:assert c.execute('SELECT state FROM collection_memberships').fetchone()[0]=='MISSING'

def test_rebuild_new_in_scope_item_mid_stage_blocks_whole_switch(setup):
    db,_,p,r,s=setup;add_item(setup);ready(setup);store=MemoryVector();index=IndexService(db,s,store);assert run(setup,index)[0]=='SUCCEEDED';old=active(setup)
    changed=False
    def add(event):
        nonlocal changed
        if event=='before_publish' and not changed:changed=True;add_item(setup,'new')
    assert run(setup,IndexService(db,s,store,fault_hook=add),'REBUILD')[0]=='BLOCKED'
    assert active(setup)[0]==old[0]

def test_lexical_corruption_before_publish_fails_coverage(setup):
    db,_,p,r,s=setup;add_item(setup);ready(setup);store=MemoryVector()
    def corrupt(event):
        if event=='after_lexical':
            with db.transaction() as c:c.execute('DELETE FROM keyword_fts')
    assert run(setup,IndexService(db,s,store,fault_hook=corrupt))[0]=='BLOCKED'
    assert active(setup)[0] is None

def test_runtime_change_between_staging_and_publication_blocks(setup):
    db,_,p,r,s=setup;add_item(setup);ready(setup);store=MemoryVector()
    def drift(event):
        if event=='before_publish':reprofile(r,expected_digest='sha256:'+'b'*64)
    assert run(setup,IndexService(db,s,store,fault_hook=drift))[0]=='BLOCKED'
    assert active(setup)[0] is None

def test_dense_change_between_staging_and_publication_blocks(setup):
    db,_,p,r,s=setup;add_item(setup);ready(setup);store=MemoryVector()
    def corrupt(event):
        if event=='before_publish':store.corrupt=True
    assert run(setup,IndexService(db,s,store,fault_hook=corrupt))[0]=='BLOCKED'
    assert active(setup)[0] is None

def test_paused_inactive_job_can_resume_same_generation_before_cleanup(setup):
    db,_,p,r,s=setup;add_item(setup);ready(setup);store=MemoryVector();store.corrupt=True;index=IndexService(db,s,store)
    state,job=run(setup,index);assert state=='BLOCKED'
    with db.connect() as c:generation=json.loads(c.execute('SELECT snapshot FROM index_snapshots WHERE job_id=?',(job['job_id'],)).fetchone()[0])['generation_uid']
    store.corrupt=False
    with db.transaction() as c:c.execute("UPDATE jobs SET state='QUEUED' WHERE job_id=?",(job['job_id'],))
    assert index.run(Queue(db).claim('resumed',300))=='SUCCEEDED'
    assert active(setup)[0]==generation

def test_gc_with_expired_job_fence_has_no_external_side_effect(setup):
    db,_,p,r,s=setup;add_item(setup);ready(setup);store=MemoryVector();index=IndexService(db,s,store)
    assert run(setup,index)[0]=='SUCCEEDED';assert run(setup,index,'REBUILD')[0]=='SUCCEEDED'
    index.enqueue(p);job=Queue(db).claim('expired',300)
    with db.transaction() as c:c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(job['job_id'],))
    count=len(store.calls)
    with pytest.raises(LeaseLost):index.cleanup(job)
    assert len(store.calls)==count

def test_empty_initial_generation_and_no_resurrection_after_gc(setup):
    db,_,p,r,s=setup;store=MemoryVector();index=IndexService(db,s,store)
    assert run(setup,index)[0]=='SUCCEEDED' and active(setup)[0]
    add_item(setup);ready(setup);store.corrupt=True
    state,job=run(setup,index,'REBUILD');assert state=='BLOCKED'
    index.cleanup();store.corrupt=False
    with db.transaction() as c:c.execute("UPDATE jobs SET state='QUEUED' WHERE job_id=?",(job['job_id'],))
    assert index.run(Queue(db).claim('resumed',300))=='BLOCKED'
    assert Queue(db).get_job(job['job_id'])['last_error_code']=='GENERATION_CLEANED'

def test_repeated_resume_never_reopens_gc_deleted_generation(setup):
    db,_,p,r,s=setup;add_item(setup);ready(setup);store=MemoryVector();store.corrupt=True;index=IndexService(db,s,store)
    state,job=run(setup,index);assert state=='BLOCKED';index.cleanup();store.corrupt=False
    for attempt in range(2):
        with db.transaction() as c:c.execute("UPDATE jobs SET state='QUEUED' WHERE job_id=?",(job['job_id'],))
        assert index.run(Queue(db).claim('resume'+str(attempt),300))=='BLOCKED'
        assert Queue(db).get_job(job['job_id'])['last_error_code']=='GENERATION_CLEANED'
    assert active(setup)[0] is None

def test_cleanup_binds_and_restores_inflight_fencing_callback(setup):
    db,_,p,r,s=setup;add_item(setup);ready(setup);store=MemoryVector();index=IndexService(db,s,store)
    assert run(setup,index)[0]=='SUCCEEDED';assert run(setup,index,'REBUILD')[0]=='SUCCEEDED'
    index.enqueue(p);job=Queue(db).claim('gc',300);previous=store.abort_check
    def delete(name):
        with db.transaction() as c:c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(job['job_id'],))
        with pytest.raises(LeaseLost):store.abort_check()
    store.delete_collection=delete
    with pytest.raises(LeaseLost):index.cleanup(job)
    assert store.abort_check is previous


def test_index_stage_can_leave_terminal_transition_to_parent_pipeline(setup):
    db,_,p,r,s=setup;add_item(setup);ready(setup);index=IndexService(db,s,MemoryVector())
    queued=index.enqueue(p);job=Queue(db).claim('parent',300)
    result=index.run(job,finish=False)
    assert result=={'state':'SUCCEEDED','error_code':None}
    assert Queue(db).get_job(job['job_id'])['state']=='RUNNING'
    Queue(db).finish(job['job_id'],job['fencing_token'],'SUCCEEDED')


def test_rebuild_preflight_can_report_new_generation_prerequisites(setup):
    db,_,p,r,s=setup;add_item(setup);ready(setup);index=IndexService(db,s,MemoryVector())
    assert run(setup,index)[0]=='SUCCEEDED'
    reprofile(r,expected_digest='sha256:'+'b'*64)
    assert index.preflight(p,stage='REBUILD')['diagnostics']==['EMBED_REQUIRED']


def test_current_selection_excludes_stale_membership_before_next_collection(setup):
    db,_,p,r,s=setup;old=add_item(setup);ready(setup);index=IndexService(db,s,MemoryVector());assert run(setup,index)[0]=='SUCCEEDED'
    add_item(setup,revision='2');ready(setup)
    queued=index.enqueue(p);job=Queue(db).claim('selection-race',300)
    with db.transaction() as c:c.execute("UPDATE project_selections SET selection_mode='SELECTED',scope_ids='[\"t2\"]' WHERE project_uid=?",(p,))
    assert index.run(job)=='COMPLETED_WITH_ERRORS'
    assert set(active(setup)[1].values())=={old}


def test_queued_lexical_version_change_requires_rebuild_without_publication(setup,monkeypatch):
    import almrag.indexing as module
    db,_,p,_,processing=setup;add_item(setup);ready(setup)
    index=IndexService(db,processing,MemoryVector());queued=index.enqueue(p)
    monkeypatch.setattr(module,'LEXICAL_VERSION','future-metadata-version')
    assert index.run(Queue(db).claim('upgraded-worker',300))=='BLOCKED'
    assert Queue(db).get_job(queued['job_id'])['last_error_code']=='REBUILD_REQUIRED'
    assert active(setup)[0] is None
