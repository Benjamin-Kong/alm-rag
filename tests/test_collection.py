"""SRS-003/004/005/006/007/008/022/047/049/055 collection contracts."""
import copy
import json
from pathlib import Path
import sqlite3
import time
import pytest
from almrag.storage import Database
from almrag.queue import Queue, LeaseLost
from almrag.collection import CollectionService, CollectionError

class SourceError(Exception):
    def __init__(self,code,global_error=False,stop_state='BLOCKED'):
        self.code=code; self.global_error=global_error; self.stop_state=stop_state

class Adapter:
    def __init__(self,n=2):
        self.scopes=[{'id':'t1','kind':'TRACKER','name':'Requirements'},{'id':'t2','kind':'TRACKER','name':'Tests'}]
        self.refs=[{'id':str(i),'scope_id':'t1','revision':'1'} for i in range(n)]
        self.fail={}; self.downloads=[]; self.hook=None
    def probe(self): return {'status':'OK'}
    def list_projects(self): return [{'id':'p','name':'Project','url':'https://source.invalid/p'}]
    def list_scopes(self,p): return copy.deepcopy(self.scopes)
    def list_fields(self,p,scope_ids=None): return [{'id':'title','name':'Title'},{'id':'description','name':'Description'},{'id':'custom','name':'Custom'}]
    def iter_refs(self,p,scope_ids=None):
        yield from [r for r in self.refs if r['scope_id'] in scope_ids]
    def get_item(self,p,i):
        if self.hook: self.hook()
        if i in self.fail: raise self.fail[i]
        return {'id':i,'project_id':p,'scope_id':'t1','revision':'1','modified':'2026-10-20','title':'Title '+i,'description':{'format':'wiki','raw':'all original','html':'<p>all original</p>'},'fields':[{'source_field_id':'custom','name':'Custom','source_format':'json','raw_value':{'nested':['all','values']}}],'raw':{'source':'all','id':i},'relations':[{'type':'verifies','target_id':'external'}],'attachments':[{'id':'a','filename':'../../sensitive.txt','source_url':'https://source.invalid/a','path':'/a'}],'source_url':'https://source.invalid/'+i}
    def download_attachment(self,p,i,a): self.downloads.append((p,i,a['id'])); return b'fixture bytes'

@pytest.fixture
def setup(tmp_path):
    db=Database(tmp_path/'data.sqlite'); db.migrate()
    # Main owns ordered migrations; worktree begins with M1 runner.
    with db.transaction() as c:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='collection_configs'").fetchone():
            buffer=''
            for line in (Path(__file__).parents[1]/'src/almrag/migrations/002_collection.sql').read_text().splitlines(True):
                buffer+=line
                if sqlite3.complete_statement(buffer): c.execute(buffer); buffer=''
    instance=db.add_instance('codebeamer','https://source.invalid','Fixture','ENV:FIXTURE')
    adapter=Adapter(); service=CollectionService(db,lambda uid:adapter,tmp_path/'assets')
    project=service.configure_project(instance,'p','Project')
    return db,adapter,service,project

def execute(service,db,project):
    queued=service.enqueue(project); job=Queue(db).claim('test',300)
    assert job['job_id']==queued['job_id']
    return service.run(job),Queue(db).get_job(job['job_id'])

def test_discovery_preflight_and_pinned_stale_config(setup):
    """SRS-003/045/046/047: discovery, ALL expansion and stale revisions."""
    db,a,s,p=setup
    with pytest.raises(CollectionError): s.configure_project('unknown','invented','Bad')
    pre=s.preflight(p)
    assert pre['collect_ready'] and pre['sync_ready'] is False
    assert pre['source_scope_ids']==['t1','t2'] and pre['estimated_items']==2
    a.scopes.append({'id':'t3','kind':'TRACKER','name':'New'})
    with pytest.raises(CollectionError): s.enqueue(p,pre['config_revision'])
    job=s.enqueue(p)
    with db.connect() as c:
        snapshot=json.loads(c.execute('SELECT snapshot FROM collection_snapshots WHERE job_id=?',(job['job_id'],)).fetchone()[0])
        assert snapshot['source_scope_ids']==['t1','t2','t3']

def test_complete_raw_revision_and_safe_attachments_idempotent(setup):
    """SRS-004/005/006/010/022/049: no projection/truncation or publication."""
    db,a,s,p=setup
    assert execute(s,db,p)[0]=='SUCCEEDED'
    assert execute(s,db,p)[0]=='SUCCEEDED'
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==2
        assert c.execute('SELECT count(*) FROM attachments').fetchone()[0]==2
        row=c.execute('SELECT raw_payload FROM item_revisions').fetchone()
        envelope=json.loads(row[0]); assert envelope['fields'][0]['raw_value']=={'nested':['all','values']}
        assert envelope['description']['raw']=='all original' and envelope['raw']=={'source':'all','id':'0'}
        assert c.execute('SELECT count(*) FROM field_values').fetchone()[0]>=2
        assert c.execute('SELECT count(*) FROM relations').fetchone()[0]==2
        assert c.execute('SELECT count(*) FROM items WHERE active_revision_uid IS NOT NULL').fetchone()[0]==0
        for r in c.execute('SELECT disk_path,filename,checksum FROM attachments'):
            path=Path(r['disk_path']); assert path.is_relative_to(s.attachment_root)
            assert path.read_bytes()==b'fixture bytes' and r['filename']=='../../sensitive.txt'

def test_isolated_failures_100_refs_and_no_fake_revision(setup):
    """SRS-055: 100 listed refs, 3 pre-revision failures and consistent counters."""
    db,a,s,p=setup; a.refs=[{'id':str(i),'scope_id':'t1'} for i in range(100)]
    a.fail={str(i):SourceError('ITEM_INVALID') for i in [2,44,78]}
    state,job=execute(s,db,p)
    assert state=='COMPLETED_WITH_ERRORS'
    assert (job['progress_total'],job['succeeded_items'],job['failed_items'])==(100,97,3)
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==97
        assert c.execute('SELECT count(*) FROM collection_failures WHERE revision_uid IS NULL').fetchone()[0]==3

def test_changed_same_source_revision_blocks_preserves_prior(setup):
    """SRS-006/055: immutable source revision conflict stops globally."""
    db,a,s,p=setup; assert execute(s,db,p)[0]=='SUCCEEDED'
    original=a.get_item
    def changed(p,i):
        e=original(p,i); e['title']='mutated'; return e
    a.get_item=changed
    state,job=execute(s,db,p); assert state=='BLOCKED' and job['last_error_code']=='REVISION_CONFLICT'
    with db.connect() as c: assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==2

def test_no_revision_surrogate_explicit_and_original_none(setup):
    db,a,s,p=setup; original=a.get_item
    def no_revision(p,i):
        e=original(p,i); e['revision']=None; return e
    a.get_item=no_revision; assert execute(s,db,p)[0]=='SUCCEEDED'
    with db.connect() as c:
        r=c.execute('SELECT * FROM item_revisions').fetchone()
        assert r['source_revision'].startswith('observed:') and json.loads(r['raw_payload'])['revision'] is None

def test_lease_loss_after_remote_result_never_commits(setup):
    """SRS-055: late result cannot write after lease replacement."""
    db,a,s,p=setup; s.enqueue(p); job=Queue(db).claim('old',300)
    def expire():
        with db.transaction() as c: c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(job['job_id'],))
    a.hook=expire
    with pytest.raises(LeaseLost): s.run(job)
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM collection_outcomes').fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM collection_failures').fetchone()[0]==0

def test_auth_global_and_partial_listing_never_success(setup):
    db,a,s,p=setup; a.fail['0']=SourceError('UNAUTHORIZED',True)
    assert execute(s,db,p)[0]=='BLOCKED'
    a.fail={}
    s.enqueue(p)
    def broken(*args,**kwargs):
        yield {'id':'0','scope_id':'t1'}
        raise SourceError('PAGE_ERROR')
    a.iter_refs=broken; job=Queue(db).claim('test',300)
    assert s.run(job)=='BLOCKED'

def test_missing_listing_and_404_not_deleted(setup):
    """SRS-008: only explicit deletion evidence can mark deleted."""
    db,a,s,p=setup; execute(s,db,p)
    a.refs=a.refs[:1]; a.fail['0']=SourceError('NOT_FOUND')
    assert execute(s,db,p)[0]=='COMPLETED_WITH_ERRORS'
    with db.connect() as c:
        assert c.execute("SELECT count(*) FROM items WHERE deleted_state='deleted'").fetchone()[0]==0
        assert c.execute("SELECT state FROM collection_memberships WHERE source_item_id='1'").fetchone()[0]=='MISSING'

def test_resume_same_job_avoids_duplicate_outcomes(setup):
    db,a,s,p=setup; s.enqueue(p); job=Queue(db).claim('test',300)
    calls=0
    def abort():
        nonlocal calls
        calls+=1
        return calls>4
    assert s.run(job,abort_check=abort)=='CANCELLED'
    with db.transaction() as c: c.execute("UPDATE jobs SET state='QUEUED' WHERE job_id=?",(job['job_id'],))
    resumed=Queue(db).claim('new',300); assert s.run(resumed)=='SUCCEEDED'
    final=Queue(db).get_job(job['job_id']); assert final['succeeded_items']==2 and final['progress_total']==2

def test_attachment_storage_error_global_preserves_prior_outcomes(setup,monkeypatch):
    """SRS-055: filesystem capacity errors must halt, never 100 local failures."""
    db,a,s,p=setup
    original=a.download_attachment
    def disk_full(*args): raise OSError(28,'no space')
    a.download_attachment=disk_full
    state,job=execute(s,db,p)
    assert state=='BLOCKED' and job['last_error_code']=='STORAGE_ERROR'
    assert job['failed_items']==0

def test_connector_wait_abort_includes_lease_guard(setup):
    """SRS-055: connector transport waits must notice revoked worker ownership."""
    from types import SimpleNamespace
    db,a,s,p=setup; a.client=SimpleNamespace(abort_check=lambda:False)
    s.enqueue(p); job=Queue(db).claim('old',300)
    original=a.get_item
    def late(p,i):
        with db.transaction() as c: c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(job['job_id'],))
        try:
            a.client.abort_check()
        except LeaseLost:
            a.detected_in_transport=True
            raise
        return original(p,i)
    a.get_item=late
    with pytest.raises(LeaseLost): s.run(job)
    assert a.detected_in_transport  # detected before get_item returned

def test_explicit_deletion_out_of_scope_and_active_preservation(setup):
    """SRS-008/023: collect state never deactivates active revisions."""
    db,a,s,p=setup; execute(s,db,p)
    with db.transaction() as c:
        for row in c.execute('SELECT item_uid,latest_revision_uid FROM item_collection_state').fetchall():
            c.execute('UPDATE items SET active_revision_uid=? WHERE item_uid=?',(row['latest_revision_uid'],row['item_uid']))
    a.refs.append({'id':'outside','scope_id':'t2'})
    original=a.get_item
    def changed(p,i):
        e=original(p,i)
        if i=='outside': e['scope_id']='t2'
        if i=='0': e.update(revision='2',deleted=True,deletion_evidence={'source':'explicit flag'})
        return e
    a.get_item=changed; assert execute(s,db,p)[0]=='SUCCEEDED'
    instance=s._config(p)['instance_uid']
    s.configure_project(instance,'p','Project',selection_mode='SELECTED',scope_ids=['t1'])
    assert execute(s,db,p)[0]=='SUCCEEDED'
    with db.connect() as c:
        assert c.execute("SELECT deleted_state FROM items WHERE source_item_id='0'").fetchone()[0]=='deleted'
        assert c.execute("SELECT state FROM collection_memberships WHERE source_item_id='outside'").fetchone()[0]=='OUT_OF_SCOPE'
        assert c.execute("SELECT count(*) FROM items WHERE active_revision_uid IS NOT NULL").fetchone()[0]==2

def test_resume_after_committed_item_pins_refs_and_counts(setup):
    db,a,s,p=setup; s.enqueue(p); job=Queue(db).claim('old',300)
    def abort():
        with db.connect() as c: return c.execute('SELECT count(*) FROM collection_outcomes').fetchone()[0]==1
    assert s.run(job,abort_check=abort)=='CANCELLED'
    a.refs.append({'id':'new','scope_id':'t1'})
    with db.transaction() as c: c.execute("UPDATE jobs SET state='QUEUED' WHERE job_id=?",(job['job_id'],))
    resumed=Queue(db).claim('new',300)
    assert s.run(resumed)=='SUCCEEDED'
    final=Queue(db).get_job(job['job_id'])
    assert final['progress_total']==2 and final['succeeded_items']==2

def test_failed_item_after_lease_revocation_cannot_record_failure(setup):
    db,a,s,p=setup; s.enqueue(p); job=Queue(db).claim('old',300)
    def failed_after_revoke(*args):
        with db.transaction() as c: c.execute('UPDATE jobs SET fencing_token=? WHERE job_id=?',('replacement',job['job_id']))
        raise SourceError('ITEM_INVALID')
    a.get_item=failed_after_revoke
    with pytest.raises(LeaseLost): s.run(job)
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM collection_failures').fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM collection_outcomes').fetchone()[0]==0
        assert c.execute('SELECT checkpoint FROM jobs WHERE job_id=?',(job['job_id'],)).fetchone()[0]=='{}'

def test_invalid_nested_metadata_rolls_back_whole_item_only(setup):
    db,a,s,p=setup; original=a.get_item
    def invalid(p,i):
        e=original(p,i)
        if i=='0': e['relations']=[{'type':'verifies'}]
        return e
    a.get_item=invalid
    state,job=execute(s,db,p)
    assert state=='COMPLETED_WITH_ERRORS' and job['succeeded_items']==1 and job['failed_items']==1
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM items').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM field_values').fetchone()[0]==1

def test_selected_scope_revalidation_and_field_readability(setup):
    db,a,s,p=setup; instance=s._config(p)['instance_uid']
    for kwargs in [{'scope_kind':'WORK_ITEM_TYPE'}, {'selection_mode':'SELECTED','scope_ids':[]}, {'selection_mode':'SELECTED','scope_ids':['invented']}]:
        with pytest.raises(CollectionError): s.configure_project(instance,'p','Project',**kwargs)
    s.configure_project(instance,'p','Project',selection_mode='SELECTED',scope_ids=['t1'])
    a.scopes=a.scopes[1:]
    pre=s.preflight(p); assert pre['status']=='BLOCKED' and not pre['collect_ready']
    a.scopes=[{'id':'t1','kind':'TRACKER','name':'Requirements'}]
    s.configure_project(instance,'p','Project',embedding_fields=['missing_field'])
    assert s.preflight(p)['diagnostics']==['FIELD_NOT_READABLE']

def test_polarion_scope_discriminator_and_instance_identity(setup):
    db,a,s,p=setup
    instance=db.add_instance('polarion','https://polarion.invalid','Polarion','ENV:OTHER')
    a.scopes=[{'id':'t1','kind':'WORK_ITEM_TYPE','name':'Requirement'}]
    other=s.configure_project(instance,'p','Same ID',scope_kind='WORK_ITEM_TYPE')
    assert other!=p and s.preflight(other)['scope_kind']=='WORK_ITEM_TYPE'
    with pytest.raises(CollectionError): s.configure_project(instance,'p','Bad',scope_kind='TRACKER')

def test_global_pause_retains_committed_first_item(setup):
    db,a,s,p=setup; a.fail['1']=SourceError('SERVER_PAUSED',True,'PAUSED')
    state,job=execute(s,db,p)
    assert state=='PAUSED' and job['succeeded_items']==1 and job['failed_items']==0
    with db.connect() as c: assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==1

def test_attachment_byte_change_same_revision_blocks(setup):
    """SRS-005/006: identical attachment metadata cannot hide changed bytes."""
    db,a,s,p=setup; execute(s,db,p)
    a.download_attachment=lambda *args:b'changed bytes'
    state,job=execute(s,db,p)
    assert state=='BLOCKED' and job['last_error_code']=='REVISION_CONFLICT'

def test_revisionless_attachment_change_creates_observation(setup):
    db,a,s,p=setup; original=a.get_item
    def revisionless(p,i):
        e=original(p,i); e['revision']=None; return e
    a.get_item=revisionless; assert execute(s,db,p)[0]=='SUCCEEDED'
    a.download_attachment=lambda *args:b'changed bytes'
    assert execute(s,db,p)[0]=='SUCCEEDED'
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==4
        assert c.execute('SELECT count(*) FROM attachments').fetchone()[0]==4


def test_preflight_request_count_is_explicitly_unknown(setup):
    """OI-039, SRS-047: details side-pages, pagination and retry costs are unknown."""
    db,a,s,p=setup
    pre=s.preflight(p)
    assert pre['collect_ready'] and pre['estimated_items']==2
    assert pre['request_count_lower_bound']==2
    assert pre['estimated_requests'] is None
    assert pre['request_estimate_kind']=='UNKNOWN'
    assert 'REQUEST_COUNT_UNKNOWN_PAGINATION_ATTACHMENTS_RETRIES' in pre['diagnostics']
    a.scopes=[]
    blocked=s.preflight(p)
    assert blocked['estimated_requests'] is None and blocked['request_estimate_kind']=='UNKNOWN'
    assert blocked['request_count_lower_bound'] is None


def test_source_catalog_and_normalized_envelope_fields_are_distinct(setup):
    """OI-041, SRS-004/047: title aliases are capabilities, never source field IDs."""
    db,a,s,p=setup
    source_fields=[{'id':'2','name':'Summary','scope_id':'t1'},{'id':'80','name':'Description','scope_id':'t1'}]
    a.list_fields=lambda project,scope_ids=None: copy.deepcopy(source_fields)
    a.normalized_fields=('title','description')
    pre=s.preflight(p)
    assert pre['collect_ready'],pre
    assert set(pre['normalized_fields'])=={'title','description'}
    assert pre['readable_fields']==source_fields
    assert {field['id'] for field in pre['readable_fields']}=={'2','80'}
    assert execute(s,db,p)[0]=='SUCCEEDED'


def test_unknown_normalized_capability_does_not_invent_aliases(setup):
    db,a,s,p=setup
    assert s.preflight(p)['normalized_fields']==[]
    a.list_fields=lambda project,scope_ids=None:[{'id':'2','name':'Summary'}]
    pre=s.preflight(p)
    assert not pre['collect_ready'] and pre['diagnostics']==['FIELD_NOT_READABLE']
    assert pre['normalized_fields']==[]


def test_policy_change_invalidates_preflight_fingerprint(setup):
    """SRS-047/053, OI-039: policy is part of reviewed preflight configuration."""
    from types import SimpleNamespace
    from almrag.alm_http import HttpPolicy
    db,a,s,p=setup
    a.client=SimpleNamespace(policy=HttpPolicy(requests_per_second=1))
    before=s.preflight(p)
    assert before['collect_ready']
    a.client.policy=HttpPolicy(requests_per_second=.5)
    after=s.preflight(p)
    assert after['config_revision']!=before['config_revision']
    with pytest.raises(CollectionError) as error:
        s.enqueue(p,before['config_revision'])
    assert error.value.code=='STALE_PREFLIGHT'


def test_same_source_field_id_in_two_trackers_has_distinct_identity(setup):
    """OI-040, SRS-004: tracker-specific fields cannot share project-wide identity."""
    db,a,s,p=setup
    a.refs=[{'id':'0','scope_id':'t1'},{'id':'1','scope_id':'t2'}]
    original=a.get_item
    def scoped(project,item):
        envelope=original(project,item)
        envelope['scope_id']='t1' if item=='0' else 't2'
        envelope['fields'][0]['raw_value']={'tracker':envelope['scope_id']}
        return envelope
    a.get_item=scoped
    assert execute(s,db,p)[0]=='SUCCEEDED'
    with db.connect() as c:
        definitions=c.execute("SELECT * FROM field_definitions WHERE source_field_id='custom'").fetchall()
        assert len(definitions)==2
        assert {tuple(json.loads(row['scope'])) for row in definitions}=={('p','TRACKER','t1'),('p','TRACKER','t2')}
        assert len({row['field_def_uid'] for row in definitions})==2
        values=c.execute('SELECT field_def_uid,raw_value FROM field_values').fetchall()
        assert len({row['field_def_uid'] for row in values})==2
        assert {json.loads(row['raw_value'])['tracker'] for row in values}=={'t1','t2'}


def test_scoped_field_fix_keeps_legacy_revision_and_field_records(setup):
    """OI-040: new identities never rewrite M1/project-scoped historical records."""
    from almrag.storage import canonical_uid
    db,a,s,p=setup
    instance=s._config(p)['instance_uid']
    legacy_field=canonical_uid('field',instance,'p','custom')
    with db.transaction() as c:
        c.execute('INSERT INTO items(item_uid,project_uid,source_item_id) VALUES(?,?,?)',('legacy-item',p,'legacy'))
        c.execute('INSERT INTO item_revisions(revision_uid,item_uid,source_revision,raw_payload,hash) VALUES(?,?,?,?,?)',('legacy-revision','legacy-item','original','{"legacy":true}','legacy-hash'))
        c.execute('INSERT INTO field_definitions(field_def_uid,instance_uid,scope,source_field_id) VALUES(?,?,?,?)',(legacy_field,instance,'p','custom'))
        c.execute('INSERT INTO field_values(revision_uid,field_def_uid,raw_value,source_format) VALUES(?,?,?,?)',('legacy-revision',legacy_field,'{"old":1}','json'))
        c.execute('UPDATE items SET active_revision_uid=? WHERE item_uid=?',('legacy-revision','legacy-item'))
    assert execute(s,db,p)[0]=='SUCCEEDED'
    with db.connect() as c:
        assert c.execute('SELECT scope FROM field_definitions WHERE field_def_uid=?',(legacy_field,)).fetchone()[0]=='p'
        assert c.execute('SELECT raw_value FROM field_values WHERE revision_uid=?',('legacy-revision',)).fetchone()[0]=='{"old":1}'
        assert tuple(c.execute('SELECT raw_payload,hash FROM item_revisions WHERE revision_uid=?',('legacy-revision',)).fetchone())==('{"legacy":true}','legacy-hash')
        assert c.execute('SELECT active_revision_uid FROM items WHERE item_uid=?',('legacy-item',)).fetchone()[0]=='legacy-revision'
        assert c.execute('SELECT count(*) FROM field_definitions').fetchone()[0]==2
