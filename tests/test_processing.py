"""SRS-009/011/012/013/014/015/016/048/049/050 processing contracts."""
import copy
import json
import time

import pytest

from almrag.chunking import ChunkConfig
from almrag.embedding import ModelConfig, ModelError, fingerprint
from almrag.processing import FieldRef, ProcessingError, ProcessingPolicy, ProcessingService
from almrag.queue import LeaseLost, Queue
from almrag.storage import Database, canonical_uid


class ExactFixture:
    identity = 'fixture:unicode-codepoints-v1'
    def count(self, text): return len(text)


class Runtime:
    def __init__(self):
        self.tokenizer = ExactFixture()
        self.config = ModelConfig(expected_digest='sha256:'+'a'*64, vector_dimension=2)
        self.calls = []
        self.abort_check = lambda: False
        self.hook = None
        self.error = None
        self._profile = {'state':'FIXTURE_ONLY','tokenizer_id':self.tokenizer.identity,'model_digest':self.config.expected_digest,'config':self.config.model_dump(),'calibration_evidence':['fixture']}
        self._profile['fingerprint'] = fingerprint(self._profile)
    @property
    def profile(self): return copy.deepcopy(self._profile)
    def verify_runtime(self): raise AssertionError('cached profile should be reused')
    def embed(self,text,*,expected_tokens):
        assert not self.abort_check()
        if self.hook: self.hook()
        if self.error: raise self.error
        assert expected_tokens == len(text)
        self.calls.append(text)
        return [1.0,2.0]


@pytest.fixture
def setup(tmp_path):
    db = Database(tmp_path/'db.sqlite'); db.migrate()
    instance = db.add_instance('codebeamer','https://source.invalid','Fixture','ENV:FIXTURE')
    project = db.add_project(instance,'source-p','Fixture')
    runtime = Runtime()
    service = ProcessingService(db,lambda p:runtime,allow_fixture=True)
    with db.transaction() as c:
        c.execute("INSERT INTO jobs(job_id,project_uid,stage,state,created_at,updated_at) VALUES('collect',?,'COLLECT','SUCCEEDED',0,0)",(project,))
    return db,instance,project,runtime,service


def add_item(setup,item='1',revision='1',scope='t1',title='Title',description='Description',fields=None):
    db,instance,project,_,_ = setup
    item_uid = canonical_uid('item',project,item)
    revision_uid = canonical_uid('revision',item_uid,revision)
    envelope = {'id':item,'project_id':'source-p','scope_id':scope,'revision':revision,'title':title,'description':{'format':'text/plain','raw':description},'fields':fields or [],'raw':{'complete':'unselected'},'attachments':[],'relations':[]}
    with db.transaction() as c:
        c.execute('INSERT OR IGNORE INTO items(item_uid,project_uid,source_item_id) VALUES(?,?,?)',(item_uid,project,item))
        c.execute('INSERT INTO item_revisions(revision_uid,item_uid,source_revision,raw_payload,hash) VALUES(?,?,?,?,?)',(revision_uid,item_uid,revision,json.dumps(envelope),fingerprint(envelope)))
        c.execute("INSERT INTO item_collection_state VALUES(?,?,'collect') ON CONFLICT(item_uid) DO UPDATE SET latest_revision_uid=excluded.latest_revision_uid",(item_uid,revision_uid))
        c.execute("INSERT INTO collection_memberships VALUES(?,?,?,'IN_SCOPE','collect') ON CONFLICT(project_uid,source_item_id) DO UPDATE SET scope_id=excluded.scope_id",(project,item,scope))
    return revision_uid


def execute(setup,stage='PROCESS'):
    db,_,project,_,service = setup
    queued = service.enqueue(project,stage)
    job = Queue(db).claim('fixture',300)
    assert job['job_id'] == queued['job_id']
    state = service.run(job)
    return state,Queue(db).get_job(job['job_id'])


def test_policy_inheritance_and_typed_source_collision(setup):
    """SRS-009/012: source title ID is distinct from normalized title."""
    db,instance,p,r,s=setup
    s.configure_instance(instance,ProcessingPolicy(fields=[FieldRef(kind='SOURCE',key='title')]))
    s.configure(p,ProcessingPolicy(scope_fields={'t2':[FieldRef(kind='NORMALIZED',key='description')]}))
    add_item(setup,fields=[{'source_field_id':'title','raw_value':'SOURCE VALUE','source_format':'text/plain'}])
    add_item(setup,'2',scope='t2')
    assert execute(setup)[0]=='SUCCEEDED'
    with db.connect() as c:
        texts=[x[0] for x in c.execute('SELECT input_text FROM chunks')]
        assert any('SOURCE VALUE' in t for t in texts)
        assert any('Field: normalized:description' in t for t in texts)
        assert all('Field: normalized:title' not in t for t in texts)
        assert c.execute("SELECT count(*) FROM field_definitions WHERE kind='normalized'").fetchone()[0]==1


def test_process_embed_idempotence_and_metadata_only_revision(setup):
    """SRS-013/015/016/049: content cache survives revision ownership changes."""
    db,_,p,r,s=setup
    first=add_item(setup)
    assert execute(setup)[0]=='SUCCEEDED'
    assert execute(setup,'EMBED')[0]=='SUCCEEDED'
    calls=len(r.calls); assert calls>0
    assert execute(setup)[0]=='SUCCEEDED'
    assert execute(setup,'EMBED')[0]=='SUCCEEDED'
    assert len(r.calls)==calls
    second=add_item(setup,revision='2')
    assert execute(setup)[0]=='SUCCEEDED'
    assert execute(setup,'EMBED')[0]=='SUCCEEDED'
    assert len(r.calls)==calls
    with db.connect() as c:
        assert {x[0] for x in c.execute('SELECT DISTINCT revision_uid FROM chunks')}=={first,second}
        assert c.execute('SELECT count(*) FROM items WHERE active_revision_uid IS NOT NULL').fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM index_generations').fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM processing_results WHERE state=\'EMBED_READY\'').fetchone()[0]==2


def test_snapshots_pin_revision_and_effective_policy(setup):
    """SRS-048/049/050: execution cannot read newer mutable input."""
    db,_,p,r,s=setup
    old=add_item(setup,description='OLD')
    q=s.enqueue(p)
    add_item(setup,revision='2',description='NEW')
    s.configure(p,ProcessingPolicy(fields=[FieldRef(kind='NORMALIZED',key='title')]))
    assert s.run(Queue(db).claim('fixture',300))=='SUCCEEDED'
    with db.connect() as c:
        assert {x[0] for x in c.execute('SELECT DISTINCT revision_uid FROM chunks')}=={old}
        assert any('OLD' in x[0] for x in c.execute('SELECT input_text FROM chunks'))
    with pytest.raises(ProcessingError,match='PROCESS_REQUIRED'):s.enqueue(p,'EMBED')


def test_item_failure_continues_and_raw_is_complete(setup):
    """SRS-011/055: opaque table values fail locally and siblings continue."""
    db,_,p,r,s=setup
    s.configure(p,ProcessingPolicy(fields=[FieldRef(kind='SOURCE',key='table')]))
    add_item(setup,fields=[{'source_field_id':'table','raw_value':{'rows':[[1,2]]},'source_format':'json'}])
    add_item(setup,'2',fields=[{'source_field_id':'table','raw_value':True,'source_format':'json'}])
    state,job=execute(setup)
    assert state=='COMPLETED_WITH_ERRORS'
    assert (job['progress_total'],job['succeeded_items'],job['failed_items'])==(2,1,1)
    with db.connect() as c:
        assert c.execute('SELECT error_class FROM failed_items').fetchone()[0]=='FIELD_VALUE_UNSUPPORTED'
        assert json.loads(c.execute('SELECT raw_payload FROM item_revisions ORDER BY source_revision LIMIT 1').fetchone()[0])['raw']=={'complete':'unselected'}


def test_runtime_unconfigured_and_fixture_not_promoted(setup):
    db,_,p,r,s=setup
    add_item(setup)
    production=ProcessingService(db,lambda p:r)
    assert production.preflight(p)['status']=='BLOCKED'
    assert 'MODEL_RUNTIME_UNVERIFIED' in production.preflight(p)['diagnostics']
    missing=ProcessingService(db,lambda p:None)
    with pytest.raises(ProcessingError,match='MODEL_PROFILE_UNCONFIGURED'):missing.enqueue(p)
    with db.connect() as c: assert c.execute("SELECT count(*) FROM jobs WHERE stage='PROCESS'").fetchone()[0]==0


def test_cache_corruption_global_failure(setup):
    """SRS-016/055: invalid cached vectors cannot be reused or overwrite ready state."""
    db,_,p,r,s=setup
    add_item(setup); execute(setup); execute(setup,'EMBED')
    with db.transaction() as c:c.execute("UPDATE embedding_cache SET vector_json='[0,0]'")
    state,job=execute(setup,'EMBED')
    assert state=='BLOCKED' and job['last_error_code']=='VECTOR_CACHE_CORRUPT'


def test_fencing_during_embedding_writes_nothing(setup):
    """SRS-048/049: an expired owner cannot commit vectors, counters or outcomes."""
    db,_,p,r,s=setup
    add_item(setup); execute(setup)
    s.enqueue(p,'EMBED');job=Queue(db).claim('old',300)
    def expire():
        with db.transaction() as c:c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(job['job_id'],))
    r.hook=expire
    with pytest.raises(LeaseLost):s.run(job)
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM embedding_cache').fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM processing_outcomes WHERE job_id=?',(job['job_id'],)).fetchone()[0]==0
    r.hook=None
    reclaimed=Queue(db).claim('new',300)
    assert s.run(reclaimed)=='SUCCEEDED'


def test_model_error_stop_state_and_abort_restore(setup):
    db,_,p,r,s=setup
    add_item(setup);execute(setup)
    previous=r.abort_check;r.error=ModelError('MODEL_SERVER_PAUSED',stop_state='PAUSED')
    state,job=execute(setup,'EMBED')
    assert state=='PAUSED' and job['last_error_code']=='MODEL_SERVER_PAUSED'
    assert r.abort_check is previous


def test_processor_version_drift_blocks_pinned_job(setup,monkeypatch):
    """SRS-048/050: a queued input must not silently use a new processor."""
    import almrag.processing as processing
    db,_,p,r,s=setup
    add_item(setup);s.enqueue(p)
    monkeypatch.setattr(processing,'NORMALIZER_VERSION','different-version')
    assert s.run(Queue(db).claim('fixture',300))=='BLOCKED'
    with db.connect() as c:assert c.execute('SELECT count(*) FROM processing_results').fetchone()[0]==0


def reprofile(runtime,**changes):
    runtime.config=runtime.config.model_copy(update=changes)
    runtime._profile['config']=runtime.config.model_dump()
    runtime._profile['model_digest']=runtime.config.expected_digest
    runtime._profile['fingerprint']=fingerprint({k:v for k,v in runtime._profile.items() if k!='fingerprint'})


def test_changed_selection_reuses_unchanged_chunks_and_config_namespaces(setup):
    """SRS-009/013/015: changing selected fields reuses exact-input cache entries."""
    db,_,p,r,s=setup
    add_item(setup)
    s.configure(p,ProcessingPolicy(fields=[FieldRef(kind='NORMALIZED',key='title')]))
    execute(setup);execute(setup,'EMBED');assert len(r.calls)==1
    s.configure(p,ProcessingPolicy(fields=[FieldRef(kind='NORMALIZED',key='title'),FieldRef(kind='NORMALIZED',key='description')]))
    execute(setup);execute(setup,'EMBED');assert len(r.calls)==2
    s.configure(p,ProcessingPolicy(chunking=ChunkConfig(prefix='New prefix')))
    execute(setup);execute(setup,'EMBED');assert len(r.calls)==4
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM processing_results').fetchone()[0]==3
        assert c.execute('SELECT count(*) FROM chunks').fetchone()[0]==5


def test_changed_model_requires_process_and_does_not_reuse_cache(setup):
    """SRS-014/015/016: model fingerprints isolate vectors and prepared chunks."""
    db,_,p,r,s=setup
    add_item(setup);execute(setup);execute(setup,'EMBED');calls=len(r.calls)
    reprofile(r,expected_digest='sha256:'+'b'*64)
    with pytest.raises(ProcessingError,match='PROCESS_REQUIRED'):s.enqueue(p,'EMBED')
    execute(setup);execute(setup,'EMBED');assert len(r.calls)==calls*2
    with db.connect() as c:assert c.execute('SELECT count(DISTINCT model_fingerprint) FROM embedding_cache').fetchone()[0]==2


def test_model_token_bound_clamps_default_chunk_budget(setup):
    """SRS-013/014: policy defaults must not expand verified model context."""
    db,_,p,r,s=setup
    reprofile(r,effective_max_input_tokens=128)
    add_item(setup,description='가나다라 ' * 3000)
    assert execute(setup)[0]=='SUCCEEDED'
    assert execute(setup,'EMBED')[0]=='SUCCEEDED'
    with db.connect() as c:
        chunks=c.execute('SELECT input_tokens,effective_max_input_tokens FROM chunks').fetchall()
        assert len(chunks)>100
        assert all(row[0]<=row[1]==128 for row in chunks)


def test_partial_cache_restart_keeps_result_unready_then_reuses_committed_chunks(setup):
    """SRS-048/049: partial vectors survive restart without falsely marking ready."""
    db,_,p,r,s=setup
    add_item(setup);execute(setup);s.enqueue(p,'EMBED');job=Queue(db).claim('old',300)
    n=0
    def expire_second():
        nonlocal n
        n+=1
        if n==2:
            with db.transaction() as c:c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(job['job_id'],))
    r.hook=expire_second
    with pytest.raises(LeaseLost):s.run(job)
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM embedding_cache').fetchone()[0]==1
        assert c.execute('SELECT state FROM processing_results').fetchone()[0]=='PROCESS_READY'
        assert c.execute('SELECT count(*) FROM embedding_manifests').fetchone()[0]==0
    calls=len(r.calls);r.hook=None
    restarted=ProcessingService(db,lambda p:r,allow_fixture=True)
    assert restarted.run(Queue(db).claim('new',300))=='SUCCEEDED'
    assert len(r.calls)==calls+1


def test_missing_selected_field_is_item_local_and_distinct(setup):
    """SRS-009/055: missing fields cannot be silently replaced with empty data."""
    db,_,p,r,s=setup
    s.configure(p,ProcessingPolicy(fields=[FieldRef(kind='SOURCE',key='title')]))
    add_item(setup)
    state,job=execute(setup)
    assert state=='COMPLETED_WITH_ERRORS' and job['failed_items']==1
    with db.connect() as c:
        assert c.execute('SELECT error_class FROM failed_items').fetchone()[0]=='SELECTED_FIELD_MISSING'
        assert c.execute('SELECT count(*) FROM processing_results').fetchone()[0]==0


def test_queued_runtime_drift_blocks_all_derived_writes(setup):
    """SRS-014/050: runtime configuration is pinned before execution."""
    db,_,p,r,s=setup
    add_item(setup);s.enqueue(p)
    reprofile(r,expected_digest='sha256:'+'b'*64)
    job=Queue(db).claim('fixture',300)
    assert s.run(job)=='BLOCKED'
    assert Queue(db).get_job(job['job_id'])['last_error_code']=='MODEL_RUNTIME_DRIFT'
    with db.connect() as c:assert c.execute('SELECT count(*) FROM processing_results').fetchone()[0]==0


def test_embedding_cache_is_project_scoped(setup):
    """SRS-016/041: equal inputs in a second project cannot share vector rows."""
    db,instance,p,r,s=setup
    add_item(setup);execute(setup);execute(setup,'EMBED');calls=len(r.calls)
    second=db.add_project(instance,'other-p','Other project')
    second_setup=(db,instance,second,r,s)
    add_item(second_setup)
    assert execute(second_setup)[0]=='SUCCEEDED'
    assert execute(second_setup,'EMBED')[0]=='SUCCEEDED'
    assert len(r.calls)==calls*2
    with db.connect() as c:
        assert c.execute('SELECT count(DISTINCT project_uid) FROM embedding_cache').fetchone()[0]==2


def test_unchanged_source_revision_changed_description_only_embeds_changed_chunk(setup):
    """SRS-013/015: independent fields preserve the unchanged title vector."""
    db,_,p,r,s=setup
    add_item(setup);execute(setup);execute(setup,'EMBED');calls=len(r.calls)
    add_item(setup,revision='2',description='Changed description')
    execute(setup);execute(setup,'EMBED')
    assert len(r.calls)==calls+1


def test_per_item_embed_error_continues_siblings(setup):
    """SRS-055: a local model input rejection cannot stop unrelated Items."""
    db,_,p,r,s=setup
    add_item(setup,title='Rejected');add_item(setup,'2',title='Accepted');execute(setup)
    original=r.embed
    def embed(text,*,expected_tokens):
        if 'Title: Rejected' in text:raise ModelError('INPUT_REJECTED',False)
        return original(text,expected_tokens=expected_tokens)
    r.embed=embed
    state,job=execute(setup,'EMBED')
    assert state=='COMPLETED_WITH_ERRORS'
    assert (job['succeeded_items'],job['failed_items'])==(1,1)
    with db.connect() as c:
        assert c.execute("SELECT count(*) FROM processing_results WHERE state='EMBED_READY'").fetchone()[0]==1
        assert c.execute("SELECT error_class FROM failed_items WHERE failed_stage='EMBED'").fetchone()[0]=='INPUT_REJECTED'


def test_processing_schema_rejects_cross_revision_membership(setup):
    """SRS-041/049: a derived result cannot claim another revision's chunks."""
    import sqlite3
    db,_,p,r,s=setup
    add_item(setup);add_item(setup,'2');execute(setup)
    with db.connect() as c:
        results=c.execute('SELECT result_uid,revision_uid FROM processing_results ORDER BY result_uid').fetchall()
        other_chunk=c.execute('SELECT chunk_uid FROM chunks WHERE revision_uid=?',(results[1]['revision_uid'],)).fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as c:c.execute('INSERT INTO processing_membership VALUES(?,?)',(results[0]['result_uid'],other_chunk))
