"""SRS-030/031/032/027: local package queue, restore nonce and negative ACL."""
import pytest
from test_m2_api import env,register,project
from almrag.queue import Queue
from almrag.worker import run_once


class Operations:
    def __init__(self,p):self.p=p;self.calls=[];self.ref='00000000-0000-0000-0000-000000000001'
    def get_artifact(self,ref):
        self.calls.append(('meta',ref));return dict(artifact_ref=self.ref,project_uid=self.p,kind='EXPORT',sha256='a'*64,size=3,state='READY',created_at=1.)
    def read_artifact(self,ref):self.calls.append(('read',ref));return b'zip'
    def enqueue_export(self,p):
        self.calls.append(('export',p));return dict(job_id='job',project_uid=p,stage='EXPORT',state='QUEUED')
    def enqueue_import(self,p,**kw):
        self.calls.append(('import',p,kw));return dict(job_id='job',project_uid=p,stage='IMPORT',state='QUEUED')
    def list_artifacts(self,p):return [self.get_artifact(self.ref)]
    def create_backup(self):self.calls.append(('backup',));return {**self.get_artifact(self.ref),'project_uid':None,'kind':'BACKUP'}
    def list_backups(self):return [self.create_backup()]
    def prepare_restore(self,ref,actor):
        self.calls.append(('prepare',ref,actor));return dict(manifest_hash='a'*64,confirmation_nonce='b'*40,expires_at=123.,state='RAW_ONLY_REBUILD_REQUIRED')
    def restore(self,ref,**kw):
        self.calls.append(('restore',ref,kw));return dict(recovery_ref=self.ref,state='RAW_ONLY_REBUILD_REQUIRED',auth_state='REREGISTRATION_REQUIRED')
    def configure_backup_schedule(self,**kw):self.calls.append(('schedule',kw));return kw


def test_project_operation_acl_and_download_precedes_file_read(env):
    app,c,h,db,calls=env;p=project(env,register(env));ops=Operations(p);app.state.operations=ops
    _,reader=app.state.security.create_key('reader',[p],['project_read'],actor='admin')
    _,manager=app.state.security.create_key('manager',[p],['project_manage','project_read'],actor='admin')
    _,foreign=app.state.security.create_key('other',['foreign'],['project_read','project_manage','system_admin'],actor='admin');c.cookies.clear()
    rh={'X-API-Key':reader};mh={'X-API-Key':manager};fh={'X-API-Key':foreign}
    base=f'/api/v1/projects/{p}'
    for suffix in ['/export','/import']:
        assert c.post(base+suffix,headers=rh,json={'artifact_ref':ops.ref}).status_code==403
        assert c.post(base+suffix,headers=fh,json={'artifact_ref':ops.ref}).status_code==404
    assert not ops.calls
    assert c.post(base+'/export',headers=mh).status_code==202
    assert c.post(base+'/import',headers=mh,json={'artifact_ref':ops.ref}).status_code==202
    before=len([x for x in ops.calls if x[0]=='read'])
    assert c.get('/api/v1/artifacts/'+ops.ref+'/download',headers=fh).status_code==404
    assert len([x for x in ops.calls if x[0]=='read'])==before
    assert c.get('/api/v1/artifacts/'+ops.ref+'/download',headers=rh).content==b'zip'
    assert c.get(base+'/artifacts',headers=rh).status_code==200
    assert c.post(base+'/artifacts/stage',headers=mh,content=b'bad').status_code==415
    assert c.post('/api/v1/backups',headers=fh).status_code==403  # Project-limited system_admin key is not global session.


def test_global_backup_restore_workflow_binds_admin_identity(env):
    app,c,h,db,calls=env;p=project(env,register(env));ops=Operations(p);app.state.operations=ops
    assert c.post('/api/v1/backups',headers=h).status_code==201
    pre=c.post(f'/api/v1/backups/{ops.ref}/prepare-restore',headers=h)
    assert pre.status_code==200 and len(ops.calls[-1][2])==64
    result=c.post(f'/api/v1/backups/{ops.ref}/restore',headers=h,json={'manifest_hash':'a'*64,'confirmation_nonce':'b'*40})
    assert result.status_code==200 and result.json()['state']=='RAW_ONLY_REBUILD_REQUIRED'
    assert c.put('/api/v1/backups/schedule',headers=h,json={'interval_seconds':60,'retention':2}).status_code==200
    assert c.post(f'/api/v1/backups/{ops.ref}/restore',headers=h,json={'manifest_hash':'bad','confirmation_nonce':'yes'}).status_code==422


def test_worker_dispatches_operation_stages_through_same_fifo(tmp_path):
    from almrag.storage import Database
    db=Database(tmp_path/'db');db.migrate();i=db.add_instance('codebeamer','https://fixture.invalid','F','env:F');p=db.add_project(i,'p','P');q=Queue(db)
    class Service:
        def run(self,job,abort_check):
            assert not abort_check();q.finish(job['job_id'],job['fencing_token'])
    for stage in ['EXPORT','IMPORT']:
        job=q.enqueue(p,stage)
        assert run_once(q,'fixture',operations_service=Service())
        assert q.get_job(job['job_id'])['state']=='SUCCEEDED'


def test_local_operations_audit_actions_are_retained_without_raw_content():
    from almrag.security import safe_event
    for action in ['artifact_export','artifact_import','backup_create','backup_restore']:
        event=safe_event(action=action,outcome='ok',raw='customer text')
        assert event.get('action')==action and 'raw' not in event


def test_worker_does_not_report_lease_loss_after_own_terminal_transition(tmp_path):
    import time
    from almrag.storage import Database
    db=Database(tmp_path/'db');db.migrate();i=db.add_instance('codebeamer','https://fixture.invalid','F','env:F');p=db.add_project(i,'p','P');q=Queue(db)
    job=q.enqueue(p,'EXPORT')
    class Service:
        def run(self,claimed,abort_check):
            q.finish(claimed['job_id'],claimed['fencing_token'])
            time.sleep(.1)  # A terminal service can return after a scheduled heartbeat.
    assert run_once(q,'fixture',operations_service=Service(),lease_seconds=.2,heartbeat_interval=.02)
    assert q.get_job(job['job_id'])['state']=='SUCCEEDED'


def test_worker_stays_revoked_if_replacement_already_finished(tmp_path):
    import time
    from almrag.storage import Database
    from almrag.queue import LeaseLost
    db=Database(tmp_path/'db');db.migrate();i=db.add_instance('codebeamer','https://fixture.invalid','F','env:F');p=db.add_project(i,'p','P');q=Queue(db);job=q.enqueue(p,'EXPORT')
    class Service:
        def run(self,claimed,abort_check):
            with db.transaction() as c:c.execute('UPDATE jobs SET lease_expires_at=0 WHERE job_id=?',(claimed['job_id'],))
            replacement=q.claim('replacement')
            q.finish(replacement['job_id'],replacement['fencing_token'])
            time.sleep(.1)
            abort_check()
    with pytest.raises(LeaseLost):run_once(q,'old',operations_service=Service(),lease_seconds=.2,heartbeat_interval=.02)
    assert q.get_job(job['job_id'])['state']=='SUCCEEDED'
