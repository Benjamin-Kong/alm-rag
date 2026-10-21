"""SRS-030/031/032 correction: offline source inputs and lease-safe slow I/O."""
import io,json,time,threading
import pytest
from test_operations import env,execute,package,envelope
from almrag.storage import Database,canonical_uid
from almrag.queue import Queue,LeaseLost
from almrag.operations import OperationsService,OperationsError
from almrag.processing import ProcessingService


def seed_latest(env):
    db,p,item,rev,s=env
    with db.transaction() as c:
        c.execute("INSERT INTO jobs(job_id,project_uid,stage,state,created_at,updated_at) VALUES('source',?,'COLLECT','SUCCEEDED',0,0)",(p,))
        c.execute("INSERT INTO item_collection_state VALUES(?,?,'source')",(item,rev))
        c.execute("INSERT INTO collection_memberships VALUES(?,'1','t','IN_SCOPE','source')",(p,))


def empty_target(env,tmp_path,scope='ALL'):
    db,p,*_=env;target=Database(tmp_path/'target'/'db.sqlite');target.migrate()
    with db.connect() as c:instance=c.execute('SELECT instance_uid FROM projects WHERE project_uid=?',(p,)).fetchone()[0]
    with target.transaction() as c:
        c.execute("INSERT INTO instances(instance_uid,source_type,base_url,display_name,auth_ref) VALUES(?,'codebeamer','https://fixture.invalid','Fixture','ENV:X')",(instance,))
        c.execute("INSERT INTO projects(project_uid,instance_uid,source_project_id,name) VALUES(?,?,'p','Fixture')",(p,instance))
        c.execute("INSERT INTO project_selections VALUES(?,?,'TRACKER',?,1,NULL,NULL)",(p,scope,'[]' if scope=='ALL' else '["different"]'))
    return target,instance


def test_import_initializes_latest_source_inputs_for_offline_process_embed_index_search(env,tmp_path):
    from test_processing import Runtime,execute as process_execute
    from test_indexing import MemoryVector,run as index_run
    from test_retrieval import Dense
    from almrag.indexing import IndexService
    from almrag.retrieval import SearchService,SearchRequest
    seed_latest(env);meta=package(env);db,instance=empty_target(env,tmp_path);p=env[1];ops=OperationsService(db)
    upload=ops.register_package(p,env[-1].read_artifact(meta['artifact_ref']));target=(db,p,env[2],env[3],ops)
    assert execute(target,ops.enqueue_import(p,upload['artifact_ref']))['state']=='SUCCEEDED'
    with db.connect() as c:
        assert ProcessingService._refs(c,p)[0]['revision_uid']==env[3]
        assert c.execute('SELECT active_revision_uid FROM items').fetchone()[0] is None
    runtime=Runtime();processing=ProcessingService(db,lambda _:runtime,allow_fixture=True);data=(db,instance,p,runtime,processing)
    assert process_execute(data)[0]=='SUCCEEDED';assert process_execute(data,'EMBED')[0]=='SUCCEEDED'
    vector=MemoryVector();assert index_run(data,IndexService(db,processing,vector))[0]=='SUCCEEDED'
    dense=Dense();dense.points={k:v for collection in vector.collections.values() for k,v in collection.items()}
    result=SearchService(db,lambda _:runtime,dense,allow_fixture=True).search(SearchRequest(query='original',project_uids=[p]),allowed_projects=[p])
    assert result['total']==1 and result['results'][0]['revision_uid']==env[3]


def test_import_preserves_target_newer_current_and_respects_selection(env,tmp_path):
    from almrag.collection import _digest
    seed_latest(env);meta=package(env);db,instance=empty_target(env,tmp_path,scope='SELECTED');p,item,revision=env[1:4];ops=OperationsService(db);target=(db,p,item,revision,ops)
    upload=ops.register_package(p,env[-1].read_artifact(meta['artifact_ref']));assert execute(target,ops.enqueue_import(p,upload['artifact_ref']))['state']=='SUCCEEDED'
    with db.connect() as c:assert ProcessingService._refs(c,p)==[]
    latest=canonical_uid('revision',item,'2');raw=envelope('2')
    with db.transaction() as c:
        c.execute('INSERT INTO item_revisions(revision_uid,item_uid,source_revision,raw_payload,hash) VALUES(?,?,?,?,?)',(latest,item,'2',json.dumps(raw),_digest({'envelope':raw,'attachment_checksums':[]})))
        c.execute("UPDATE item_collection_state SET latest_revision_uid=? WHERE item_uid=?",(latest,item))
    completed=execute(target,ops.enqueue_import(p,upload['artifact_ref']))
    assert completed['checkpoint']['source_inputs_kept'][0]['current_revision_uid']==latest
    with db.connect() as c:assert c.execute('SELECT latest_revision_uid FROM item_collection_state').fetchone()[0]==latest


def test_restore_preserves_inactive_source_latest_mapping(env):
    seed_latest(env);s=env[-1];backup=s.create_backup();confirmation=s.prepare_restore(backup['artifact_ref'],'admin');restored=s.restore(backup['artifact_ref'],confirmation['manifest_hash'],confirmation['confirmation_nonce'],'admin');db=Database(s.recovery_root/restored['recovery_ref']/'recovery.sqlite')
    with db.transaction() as c:
        c.execute("INSERT INTO project_selections VALUES(?,'ALL','TRACKER','[]',1,NULL,NULL)",(env[1],))
        # Fresh recovery has no selection until administrator configures it.
        c.execute("UPDATE collection_memberships SET state='IN_SCOPE' WHERE project_uid=?",(env[1],))
    with db.connect() as c:assert ProcessingService._refs(c,env[1])[0]['revision_uid']==env[3]


def test_slow_export_keeps_heartbeat_and_publishes_once(env):
    db,p,*_,service=env;queued=service.enqueue_export(p);queue=Queue(db);job=queue.claim('fixture',lease_seconds=.2);original=service._capture;errors=[];stop=threading.Event()
    def slow(*args):time.sleep(.5);return original(*args)
    service._capture=slow
    def heartbeat():
        while not stop.wait(.03):
            try:queue.heartbeat(job['job_id'],job['fencing_token'],lease_seconds=.2)
            except Exception as e:
                if isinstance(e,LeaseLost) and queue.get_job(job['job_id'])['state'] in {'SUCCEEDED','COMPLETED_WITH_ERRORS','BLOCKED','FAILED','CANCELLED','PAUSED'}:return
                errors.append(e);return
    thread=threading.Thread(target=heartbeat);thread.start()
    try:service.run(job,lambda:False)
    finally:stop.set();thread.join()
    assert not errors
    assert queue.get_job(queued['job_id'])['state']=='SUCCEEDED'
    assert len(service.list_artifacts(p))==1


def test_source_latest_uses_declared_source_state_not_revision_sort_and_rejects_forgery(env,tmp_path):
    import zipfile
    from almrag.collection import _digest
    seed_latest(env);db,p,item,rev,s=env;later=canonical_uid('revision',item,'zzz');raw=envelope('zzz')
    with db.transaction() as c:c.execute("INSERT INTO item_revisions(revision_uid,item_uid,source_revision,captured_at,raw_payload,hash) VALUES(?,?,?,'2099-01-01',?,?)",(later,item,'zzz',json.dumps(raw),_digest({'envelope':raw,'attachment_checksums':[]})))
    meta=package(env)
    with zipfile.ZipFile(io.BytesIO(s.read_artifact(meta['artifact_ref']))) as z:payload=json.loads(z.read('project.json'))
    assert payload['source_latest'][0]['revision_uid']==rev
    payload['source_latest'][0]['scope_id']='forged-scope'
    with pytest.raises(OperationsError):s.register_package(p,s.encode_package(payload))


def test_slow_import_validation_keeps_heartbeat(env):
    db,p,*_,s=env;meta=package(env);jobinfo=s.enqueue_import(p,meta['artifact_ref']);queue=Queue(db);job=queue.claim('fixture',lease_seconds=.2);original=s._decode;stop=threading.Event();errors=[]
    def slow(data):time.sleep(.5);return original(data)
    s._decode=slow
    def heartbeat():
        while not stop.wait(.03):
            try:queue.heartbeat(job['job_id'],job['fencing_token'],lease_seconds=.2)
            except Exception as e:
                if isinstance(e,LeaseLost) and queue.get_job(job['job_id'])['state'] in {'SUCCEEDED','COMPLETED_WITH_ERRORS','BLOCKED','FAILED','CANCELLED','PAUSED'}:return
                errors.append(e);return
    thread=threading.Thread(target=heartbeat);thread.start()
    try:s.run(job,lambda:False)
    finally:stop.set();thread.join()
    assert not errors and queue.get_job(jobinfo['job_id'])['state']=='SUCCEEDED'


def test_backup_manifest_has_app_version_and_rejects_unsupported_major(env):
    import zipfile
    s=env[-1];meta=s.create_backup()
    with zipfile.ZipFile(io.BytesIO(s.read_artifact(meta['artifact_ref']))) as z:files={k:z.read(k) for k in z.namelist()};manifest=json.loads(files['manifest.json'])
    assert manifest['app_version']
    manifest['app_version']='999.0.0';files['manifest.json']=json.dumps(manifest).encode();stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        for k,v in files.items():z.writestr(k,v)
    changed=s._store(stream.getvalue(),None,'BACKUP')
    with pytest.raises(OperationsError,match='BACKUP_APP_VERSION_UNSUPPORTED'):s.prepare_restore(changed['artifact_ref'],'admin')


def test_compressible_export_rejected_if_own_reader_uncompressed_limit_exceeded(env):
    from almrag.collection import _digest
    db,p,item,_,s=env;raw=envelope('2');raw['description']['raw']='A'*10000;rev=canonical_uid('revision',item,'2')
    with db.transaction() as c:c.execute('INSERT INTO item_revisions(revision_uid,item_uid,source_revision,raw_payload,hash) VALUES(?,?,?,?,?)',(rev,item,'2',json.dumps(raw),_digest({'envelope':raw,'attachment_checksums':[]})))
    s.MAX_BYTES=2048;done=execute(env,s.enqueue_export(p))
    assert done['state']=='BLOCKED' and done['last_error_code']=='PACKAGE_SIZE_LIMIT'
    assert s.list_artifacts(p)==[]


def test_backup_writer_enforces_reader_entry_count_before_publication(env):
    s=env[-1];s.MAX_ENTRIES=1
    with pytest.raises(OperationsError,match='BACKUP_SIZE_LIMIT'):s.create_backup()
    assert s.list_backups()==[]


def test_foreign_field_namespace_and_uid_mismatch_rejected(env):
    import zipfile
    meta=package(env);s=env[-1]
    with zipfile.ZipFile(io.BytesIO(s.read_artifact(meta['artifact_ref']))) as z:p=json.loads(z.read('project.json'))
    instance=p['project']['instance_uid'];uid=canonical_uid('field',instance,'foreign-project','TRACKER','foreign-tracker','legitimate-field')
    p['tables']['field_definitions']=[{'field_def_uid':uid,'instance_uid':instance,'scope':json.dumps(['foreign-project','TRACKER','foreign-tracker']),'source_field_id':'POISONED','kind':None,'data_type':None,'embed_policy':None}]
    with pytest.raises(OperationsError):s.register_package(env[1],s.encode_package(p))
    field=p['tables']['field_definitions'][0];field.update(field_def_uid=canonical_uid('field',instance,'p','TRACKER','t','other-id'),scope=json.dumps(['p','TRACKER','t']),source_field_id='f')
    p['tables']['field_values']=[{'revision_uid':env[3],'field_def_uid':field['field_def_uid'],'raw_value':'raw','normalized_value':None,'source_format':'text/plain'}]
    with pytest.raises(OperationsError):s.register_package(env[1],s.encode_package(p))


def test_foreign_relation_namespace_poison_rejected(env):
    import zipfile
    meta=package(env);s=env[-1]
    with zipfile.ZipFile(io.BytesIO(s.read_artifact(meta['artifact_ref']))) as z:p=json.loads(z.read('project.json'))
    p['tables']['relations']=[{'relation_uid':canonical_uid('relation','foreign-revision','0'),'revision_uid':env[3],'original_relation_type':'parent','source_target_id':'2','target_uid':None}]
    with pytest.raises(OperationsError):s.register_package(env[1],s.encode_package(p))


def test_recovery_preserves_safe_selection_and_offline_processing_index(env):
    from test_processing import Runtime,execute as process_execute
    from test_indexing import MemoryVector,run as index_run
    from almrag.indexing import IndexService
    seed_latest(env)
    with env[0].transaction() as c:c.execute("INSERT INTO project_selections VALUES(?,'ALL','TRACKER','[]',1,NULL,NULL)",(env[1],))
    s=env[-1];backup=s.create_backup();confirmation=s.prepare_restore(backup['artifact_ref'],'admin');result=s.restore(backup['artifact_ref'],confirmation['manifest_hash'],confirmation['confirmation_nonce'],'admin');db=Database(s.recovery_root/result['recovery_ref']/'recovery.sqlite')
    with db.connect() as c:instance=c.execute('SELECT instance_uid FROM projects WHERE project_uid=?',(env[1],)).fetchone()[0]
    runtime=Runtime();processing=ProcessingService(db,lambda _:runtime,allow_fixture=True);data=(db,instance,env[1],runtime,processing)
    assert process_execute(data)[0]=='SUCCEEDED';assert process_execute(data,'EMBED')[0]=='SUCCEEDED'
    assert index_run(data,IndexService(db,processing,MemoryVector()))[0]=='SUCCEEDED'


def test_import_attachment_io_failure_never_leaves_partial_published_file(env,tmp_path,monkeypatch):
    import hashlib,os
    s=env[-1];uid=canonical_uid('attachment','synthetic');data=b'synthetic complete bytes';checksum=hashlib.sha256(data).hexdigest();root=tmp_path/'atomic-attachments';payload={'tables':{'attachments':[{'attachment_uid':uid,'checksum':checksum,'disk_path':'attachments/'+uid}]}}
    def failure(fd):raise OSError('synthetic sync failure')
    monkeypatch.setattr(os,'fsync',failure)
    with pytest.raises(OSError):s._write_attachments(payload,{'attachments/'+uid:data},root)
    assert list(root.iterdir())==[]
