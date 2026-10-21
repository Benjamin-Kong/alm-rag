"""SRS-030/031/032/049/059: authenticated API + actual worker/package/recovery."""
from fastapi.testclient import TestClient
from test_pipeline import setup,collection_setup,run
from almrag.api import create_app
from almrag.config import Settings
from almrag.operations import OperationsService
from almrag.queue import Queue
from almrag.storage import Database
from almrag.worker import run_once


def test_api_worker_export_upload_import_and_nonce_recovery_roundtrip(setup,tmp_path):
    db,source,p,runtime,pipeline,index=setup
    assert run(setup)[0]=='SUCCEEDED'
    operations=OperationsService(db,artifact_root=tmp_path/'artifacts',attachment_root=pipeline.collection.attachment_root)
    app=create_app(Settings(database_path=str(db.path)),db=db,collection=pipeline.collection,processing=pipeline.processing,indexing=index,pipeline=pipeline,operations=operations)
    app.state.security.bootstrap('admin','synthetic long password')
    _,key=app.state.security.create_key('manager',[p],['project_manage','project_read'],actor='admin')
    _,other=app.state.security.create_key('other',['foreign'],['project_manage','project_read'],actor='admin')
    headers={'X-API-Key':key};base=f'/api/v1/projects/{p}'
    with db.connect() as c:before=dict(c.execute('SELECT item_uid,active_revision_uid FROM items'))
    with TestClient(app,base_url='https://testserver') as client:
        queued=client.post(base+'/export',headers=headers)
        assert queued.status_code==202,queued.text
        assert run_once(Queue(db),'export-http',operations_service=operations)
        assert Queue(db).get_job(queued.json()['job_id'])['state']=='SUCCEEDED'
        metadata=client.get(base+'/artifacts',headers=headers).json()[0];ref=metadata['artifact_ref']
        artifact=client.get('/api/v1/artifacts/'+ref+'/download',headers=headers)
        assert artifact.status_code==200 and artifact.headers['content-type']=='application/zip'
        assert client.get('/api/v1/artifacts/'+ref+'/download',headers={'X-API-Key':other}).status_code==404
        staged=client.post(base+'/artifacts/stage',headers={**headers,'Content-Type':'application/zip'},content=artifact.content)
        assert staged.status_code==201,staged.text
        assert client.post(base+'/artifacts/stage',headers={**headers,'Content-Type':'application/zip'},content=b'not zip').status_code==422
        imported=client.post(base+'/import',headers=headers,json={'artifact_ref':staged.json()['artifact_ref'],'import_mode':'MERGE_ONLY','expected_sha256':metadata['sha256']})
        assert imported.status_code==202,imported.text
        assert run_once(Queue(db),'import-http',operations_service=operations)
        assert Queue(db).get_job(imported.json()['job_id'])['state']=='SUCCEEDED'
        with db.connect() as c:
            assert dict(c.execute('SELECT item_uid,active_revision_uid FROM items'))==before
            assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==2
        login=client.post('/api/v1/auth/login',headers={'Origin':'https://localhost:8443'},json={'username':'admin','password':'synthetic long password'})
        assert login.status_code==204
        admin={'Origin':'https://localhost:8443','X-CSRF-Token':client.cookies['almrag_csrf']}
        backup=client.post('/api/v1/backups',headers=admin)
        assert backup.status_code==201,backup.text
        ref=backup.json()['artifact_ref']
        preparation=client.post('/api/v1/backups/'+ref+'/prepare-restore',headers=admin)
        assert preparation.status_code==200,preparation.text
        payload={k:preparation.json()[k] for k in ['manifest_hash','confirmation_nonce']}
        recovered=client.post('/api/v1/backups/'+ref+'/restore',headers=admin,json=payload)
        assert recovered.status_code==200,recovered.text
        assert recovered.json()['state']=='RAW_ONLY_REBUILD_REQUIRED'
        assert client.post('/api/v1/backups/'+ref+'/restore',headers=admin,json=payload).status_code==409
        restored=Database(operations.recovery_root/recovered.json()['recovery_ref']/'recovery.sqlite')
        with restored.connect() as c:
            assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==2
            assert c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('administrators','sessions','api_keys','secrets')").fetchone() is None
        with db.connect() as c:assert c.execute('SELECT count(*) FROM administrators').fetchone()[0]==1
