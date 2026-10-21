"""SRS-030/031/032: local raw-only preservation and safe merge/recovery."""
import io,json,zipfile,hashlib
import pytest
from almrag.storage import Database,canonical_uid
from almrag.queue import Queue
from almrag.operations import OperationsService,OperationsError
from almrag.collection import _digest

def envelope(revision="1",attachments=None):
    return {"id":"1","project_id":"p","scope_id":"t","revision":revision,"title":"Title","description":{"format":"text/plain","raw":"original"},"fields":[{"source_field_id":"f","raw_value":"raw","source_format":"text/plain"}],"raw":{"body":"original"},"attachments":attachments or [],"relations":[]}

@pytest.fixture
def env(tmp_path):
    db=Database(tmp_path/'db.sqlite');db.migrate();i=db.add_instance('codebeamer','https://fixture.invalid','Fixture','ENV:TOP_SECRET');p=db.add_project(i,'p','Fixture')
    item=canonical_uid('item',p,'1');rev=canonical_uid('revision',item,'1')
    with db.transaction() as c:
        c.execute('INSERT INTO items(item_uid,project_uid,source_item_id) VALUES(?,?,?)',(item,p,'1'))
        c.execute('INSERT INTO item_revisions(revision_uid,item_uid,source_revision,raw_payload,hash) VALUES(?,?,?,?,?)',(rev,item,'1',json.dumps(envelope()),_digest({'envelope':envelope(),'attachment_checksums':[]})))
    return db,p,item,rev,OperationsService(db)

def execute(env,job):
    q=Queue(env[0]);claimed=q.claim('fixture');assert claimed['job_id']==job['job_id'];env[-1].run(claimed,lambda:False);return q.get_job(job['job_id'])

def test_export_preserves_original_excludes_secrets_embeddings(env):
    db,p,item,rev,s=env
    assert execute(env,s.enqueue_export(p))['state']=='SUCCEEDED'
    meta=s.list_artifacts(p)[0];data=s.read_artifact(meta['artifact_ref'])
    assert b'TOP_SECRET' not in data
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        payload=json.loads(z.read('project.json'));assert json.loads(payload['tables']['item_revisions'][0]['raw_payload'])==envelope()
        assert 'embedding_cache' not in payload['tables'];assert payload['rebuild_required'] is True
    assert 'path' not in meta

def package(env):
    execute(env,env[-1].enqueue_export(env[1]));return env[-1].list_artifacts(env[1])[0]

def test_import_duplicate_idempotent_and_never_activates(env):
    meta=package(env);s=env[-1]
    for _ in range(2):assert execute(env,s.enqueue_import(env[1],meta['artifact_ref']))['state']=='SUCCEEDED'
    with env[0].connect() as c:
        assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==1
        assert c.execute('SELECT active_revision_uid FROM items').fetchone()[0] is None

def test_import_malformed_zip_traversal_and_hash_fail_before_writes(env):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:z.writestr('../evil','bad')
    with pytest.raises(OperationsError):env[-1].register_package(env[1],stream.getvalue())
    meta=package(env)
    with pytest.raises(OperationsError):env[-1].enqueue_import(env[1],meta['artifact_ref'],expected_sha256='0'*64)

def test_import_conflict_quarantined_and_missing_never_deletes(env):
    meta=package(env);s=env[-1];raw=s.read_artifact(meta['artifact_ref'])
    with zipfile.ZipFile(io.BytesIO(raw)) as z:payload=json.loads(z.read('project.json'))
    changed_envelope=envelope();changed_envelope['raw']['body']='conflict'
    payload['tables']['item_revisions'][0]['raw_payload']=json.dumps(changed_envelope)
    payload['tables']['item_revisions'][0]['hash']=_digest({'envelope':changed_envelope,'attachment_checksums':[]})
    changed=s.register_package(env[1],s.encode_package(payload))
    assert execute(env,s.enqueue_import(env[1],changed['artifact_ref']))['state']=='COMPLETED_WITH_ERRORS'
    with env[0].connect() as c:assert json.loads(c.execute('SELECT raw_payload FROM item_revisions').fetchone()[0])==envelope()
    assert s.get_artifact(changed['artifact_ref'])['state']=='QUARANTINED'

def test_restore_nonce_bound_one_use_isolated_and_no_auth_loss(env):
    s=env[-1];backup=s.create_backup();prepared=s.prepare_restore(backup['artifact_ref'],'admin')
    with pytest.raises(OperationsError):s.restore(backup['artifact_ref'],prepared['manifest_hash'],prepared['confirmation_nonce'],'other')
    result=s.restore(backup['artifact_ref'],prepared['manifest_hash'],prepared['confirmation_nonce'],'admin')
    assert result['state']=='RAW_ONLY_REBUILD_REQUIRED'
    with pytest.raises(OperationsError):s.restore(backup['artifact_ref'],prepared['manifest_hash'],prepared['confirmation_nonce'],'admin')
    with env[0].connect() as c:assert c.execute('SELECT auth_ref FROM instances').fetchone()[0]=='ENV:TOP_SECRET'
    recovery=s.recovery_root/result['recovery_ref']/'recovery.sqlite'
    with Database(recovery).connect() as c:
        assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM api_principals').fetchone()[0]==0
        assert c.execute('SELECT auth_ref FROM instances').fetchone()[0]=='RECOVERY_REGISTRATION_REQUIRED'

def test_schedule_retention_and_expiry(env):
    s=env[-1];now=[100.];s.clock=lambda:now[0];s.configure_backup_schedule(10,2)
    for t in (110,120,130):now[0]=t;s.maintenance()
    backups=s.list_backups();assert len(backups)==2
    prepared=s.prepare_restore(backups[0]['artifact_ref'],'admin');now[0]+=301
    with pytest.raises(OperationsError):s.restore(backups[0]['artifact_ref'],prepared['manifest_hash'],prepared['confirmation_nonce'],'admin')

def test_import_foreign_project_rejected_before_queue(env):
    meta=package(env);other=env[0].add_project(env[0].add_instance('polarion','https://other.invalid','Other','ENV:X'),'p','Other')
    with pytest.raises(OperationsError):env[-1].enqueue_import(other,meta['artifact_ref'])

def test_export_stale_lease_cannot_publish(env):
    db,p,*_,s=env;job=s.enqueue_export(p);claimed=Queue(db).claim('fixture')
    with db.transaction() as c:c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(job['job_id'],))
    from almrag.queue import LeaseLost
    with pytest.raises(LeaseLost):s.run(claimed,lambda:False)
    assert s.list_artifacts(p)==[]


def test_archive_identity_paths_and_duplicate_entries_are_rejected(env):
    meta=package(env);s=env[-1]
    with zipfile.ZipFile(io.BytesIO(s.read_artifact(meta['artifact_ref']))) as z:p=json.loads(z.read('project.json'))
    p['tables']['attachments']=[{'attachment_uid':'../../escape','item_uid':env[2],'revision_uid':env[3],'source_url':None,'filename':'f','checksum':hashlib.sha256(b'x').hexdigest(),'disk_path':None,'download_status':'MISSING'}]
    with pytest.raises(OperationsError):s.register_package(env[1],s.encode_package(p))
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('project.json','{}')
        with pytest.warns(UserWarning):z.writestr('project.json','{}')
    with pytest.raises(OperationsError):s.register_package(env[1],out.getvalue())


def test_all_revisions_normalized_tables_and_attachment_roundtrip(env,tmp_path):
    db,p,item,rev,s=env;field=canonical_uid('field',p,'f');block=canonical_uid('block',rev,'1');content=b'\x00synthetic attachment\xff';checksum=hashlib.sha256(content).hexdigest()
    s.attachment_root.mkdir();path=s.attachment_root/'fixture';path.write_bytes(content)
    second=canonical_uid('revision',item,'2');second_envelope=envelope('2',[{'id':'f','filename':'f'}]);attachment=canonical_uid('attachment',p,'1',_digest(second_envelope),'f',checksum)
    with db.transaction() as c:
        instance=c.execute('SELECT instance_uid FROM projects WHERE project_uid=?',(p,)).fetchone()[0]
        c.execute('INSERT INTO item_revisions(revision_uid,item_uid,source_revision,raw_payload,hash) VALUES(?,?,?,?,?)',(second,item,'2',json.dumps(second_envelope),_digest({'envelope':second_envelope,'attachment_checksums':[checksum]})))
        field=canonical_uid('field',instance,'p','TRACKER','t','f')
        c.execute('INSERT INTO field_definitions(field_def_uid,instance_uid,scope,source_field_id) VALUES(?,?,?,?)',(field,instance,json.dumps(['p','TRACKER','t']),'f'))
        c.execute('INSERT INTO field_values(revision_uid,field_def_uid,raw_value,normalized_value) VALUES(?,?,?,?)',(rev,field,'raw','normalized'))
        c.execute("INSERT INTO content_blocks(block_uid,revision_uid,field_def_uid,block_order,type,raw_html,table_json,normalized_text) VALUES(?,?,?,0,'table',?,?,?)",(block,rev,field,'<table>raw</table>','{"rows":[["a"]]}','a'))
        c.execute('INSERT INTO attachments VALUES(?,?,?,?,?,?,?,?)',(attachment,item,second,'https://fixture.invalid/f','f',checksum,str(path),'DOWNLOADED'))
    meta=package(env);fresh=Database(tmp_path/'fresh'/'db.sqlite');fresh.migrate()
    with fresh.transaction() as c:
        c.execute("INSERT INTO instances(instance_uid,source_type,base_url,display_name,auth_ref) VALUES(?,'codebeamer','https://fixture.invalid','Fixture','ENV:X')",(instance,))
        c.execute('INSERT INTO projects(project_uid,instance_uid,source_project_id,name) VALUES(?,?,?,?)',(p,instance,'p','Fixture'))
    target=OperationsService(fresh);uploaded=target.register_package(p,s.read_artifact(meta['artifact_ref']))
    targetenv=(fresh,p,item,rev,target)
    assert execute(targetenv,target.enqueue_import(p,uploaded['artifact_ref']))['state']=='SUCCEEDED'
    with fresh.connect() as c:
        assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==2
        assert c.execute('SELECT normalized_value FROM field_values').fetchone()[0]=='normalized'
        assert c.execute('SELECT table_json FROM content_blocks').fetchone()[0]=='{"rows":[["a"]]}'
        restored=c.execute('SELECT disk_path FROM attachments').fetchone()[0]
    from pathlib import Path
    assert Path(restored).read_bytes()==content
    backup=s.create_backup();confirm=s.prepare_restore(backup['artifact_ref'],'admin');recovered=s.restore(backup['artifact_ref'],confirm['manifest_hash'],confirm['confirmation_nonce'],'admin')
    with Database(s.recovery_root/recovered['recovery_ref']/'recovery.sqlite').connect() as c:assert Path(c.execute('SELECT disk_path FROM attachments').fetchone()[0]).read_bytes()==content


def test_import_prevalidates_sql_types_and_foreign_fields(env):
    meta=package(env);s=env[-1]
    with zipfile.ZipFile(io.BytesIO(s.read_artifact(meta['artifact_ref']))) as z:p=json.loads(z.read('project.json'))
    p['tables']['items'][0]['source_item_id']=['not','scalar']
    with pytest.raises(OperationsError):s.register_package(env[1],s.encode_package(p))


def test_same_revision_hash_ignores_capture_time_and_mutable_item_status(env):
    meta=package(env);s=env[-1]
    with zipfile.ZipFile(io.BytesIO(s.read_artifact(meta['artifact_ref']))) as z:p=json.loads(z.read('project.json'))
    p['tables']['items'][0]['status']='historic';p['tables']['item_revisions'][0]['captured_at']='2000-01-01'
    uploaded=s.register_package(env[1],s.encode_package(p))
    assert execute(env,s.enqueue_import(env[1],uploaded['artifact_ref']))['state']=='SUCCEEDED'


def test_missing_items_never_delete_and_abort_rolls_back(env):
    meta=package(env);s=env[-1]
    with zipfile.ZipFile(io.BytesIO(s.read_artifact(meta['artifact_ref']))) as z:p=json.loads(z.read('project.json'))
    p['tables']={k:[] for k in p['tables']};p['source_latest']=[];empty=s.register_package(env[1],s.encode_package(p))
    assert execute(env,s.enqueue_import(env[1],empty['artifact_ref']))['state']=='SUCCEEDED'
    with env[0].connect() as c:assert c.execute('SELECT count(*) FROM items').fetchone()[0]==1
    calls=[False,True];job=s.enqueue_import(env[1],meta['artifact_ref']);claimed=Queue(env[0]).claim('fixture');s.run(claimed,lambda:calls.pop(0))
    assert Queue(env[0]).get_job(job['job_id'])['state']=='BLOCKED'
    with env[0].connect() as c:assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==1


def test_export_commit_crash_reclaim_reuses_published_artifact(env):
    db,p,*_,s=env;job=s.enqueue_export(p);claimed=Queue(db).claim('fixture');finish=s.queue.finish
    class Crash(BaseException):pass
    s.queue.finish=lambda *a,**k:(_ for _ in ()).throw(Crash())
    with pytest.raises(Crash):s.run(claimed,lambda:False)
    assert len(s.list_artifacts(p))==1
    s.queue.finish=finish
    with db.transaction() as c:c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(job['job_id'],))
    reclaimed=Queue(db).claim('recovery');s.run(reclaimed,lambda:False)
    assert len(s.list_artifacts(p))==1
    assert Queue(db).get_job(job['job_id'])['state']=='SUCCEEDED'


def test_backup_manifest_records_schema_model_compatibility_and_disallows_secrets(env):
    backup=env[-1].create_backup()
    with zipfile.ZipFile(io.BytesIO(env[-1].read_artifact(backup['artifact_ref']))) as z:
        manifest=json.loads(z.read('manifest.json'))
        with env[0].connect() as c:assert manifest['schema_versions']==[r[0] for r in c.execute('SELECT version FROM schema_migrations ORDER BY version')]
        assert 'generation_compatibility' in manifest
        assert manifest['state']=='RAW_ONLY_REBUILD_REQUIRED'
        assert manifest['auth_state']=='REREGISTRATION_REQUIRED'
        assert b'TOP_SECRET' not in z.read('database.sqlite')


def test_original_revision_hash_and_declared_algorithm_verified(env):
    meta=package(env);s=env[-1]
    with zipfile.ZipFile(io.BytesIO(s.read_artifact(meta['artifact_ref']))) as z:p=json.loads(z.read('project.json'))
    p['tables']['item_revisions'][0]['hash']='0'*64
    with pytest.raises(OperationsError):s.register_package(env[1],s.encode_package(p))
    p['hash_algorithm']='unknown-v0'
    with pytest.raises(OperationsError):s.register_package(env[1],s.encode_package(p))


def test_attachment_order_uses_original_envelope_and_missing_bytes_rejected(env):
    db,p,item,_,s=env;original=envelope('2',[{'id':'z'},{'id':'a'}]);digest=_digest(original);rev=canonical_uid('revision',item,'2');files={};rows=[]
    for source_id,content in [('z',b'first'),('a',b'second')]:
        checksum=hashlib.sha256(content).hexdigest();uid=canonical_uid('attachment',p,'1',digest,source_id,checksum);files['attachments/'+uid]=content
        rows.append({'attachment_uid':uid,'item_uid':item,'revision_uid':rev,'source_url':None,'filename':source_id,'checksum':checksum,'disk_path':'attachments/'+uid,'download_status':'DOWNLOADED'})
    meta=package(env)
    with zipfile.ZipFile(io.BytesIO(s.read_artifact(meta['artifact_ref']))) as z:payload=json.loads(z.read('project.json'))
    row=dict(payload['tables']['item_revisions'][0]);row.update(revision_uid=rev,source_revision='2',raw_payload=json.dumps(original),hash=_digest({'envelope':original,'attachment_checksums':[rows[0]['checksum'],rows[1]['checksum']]}));payload['tables']['item_revisions']=[row];payload['tables']['attachments']=list(reversed(rows))
    uploaded=s.register_package(p,s.encode_package(payload,files));assert uploaded['state']=='AVAILABLE'
    rows[0]['disk_path']=None;rows[0]['download_status']='MISSING';del files['attachments/'+rows[0]['attachment_uid']]
    with pytest.raises(OperationsError):s.register_package(p,s.encode_package(payload,files))


def test_schema_not_null_is_rejected_before_package_registration(env):
    meta=package(env);s=env[-1]
    with zipfile.ZipFile(io.BytesIO(s.read_artifact(meta['artifact_ref']))) as z:p=json.loads(z.read('project.json'))
    with env[0].connect() as c:instance=c.execute('SELECT instance_uid FROM projects WHERE project_uid=?',(env[1],)).fetchone()[0]
    p['tables']['field_definitions']=[{'field_def_uid':canonical_uid('field',instance,'x'),'instance_uid':instance,'scope':'scope','source_field_id':None,'kind':None,'data_type':None,'embed_policy':None}]
    with pytest.raises(OperationsError):s.register_package(env[1],s.encode_package(p))
