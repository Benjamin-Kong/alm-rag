"""SRS-029/044/057: scoped explorer and effective-principal contracts."""
from test_m2_api import env,register,project


def test_effective_principal_and_profiles_do_not_expose_credentials(env):
    app,c,h,db,calls=env;p=project(env,register(env))
    response=c.get('/api/v1/auth/me',headers=h)
    assert response.status_code==200,response.text
    assert response.json()['admin_session'] is True and 'csrf_hash' not in response.text
    response=c.get('/api/v1/alm-instances',headers=h)
    assert response.status_code==200 and len(response.json())==1
    assert 'auth_ref' not in response.text and 'fixture-token' not in response.text
    _,key=app.state.security.create_key('reader',[p],['project_read'],actor='admin');c.cookies.clear();headers={'X-API-Key':key}
    response=c.get('/api/v1/auth/me',headers=headers)
    assert response.status_code==200 and response.json()=={'admin_session':False,'project_uids':[p],'permissions':['project_read']}
    assert c.get('/api/v1/alm-instances',headers=headers).status_code==403


def test_project_explorer_requires_read_grant_and_hides_foreign_items(env):
    from almrag.storage import canonical_uid
    import json
    app,c,h,db,calls=env;p=project(env,register(env));uid=canonical_uid('item',p,'x');revision=canonical_uid('revision',uid,'1')
    with db.transaction() as sql:
        sql.execute('INSERT INTO items(item_uid,project_uid,source_item_id) VALUES(?,?,?)',(uid,p,'x'))
        sql.execute('INSERT INTO item_revisions(revision_uid,item_uid,source_revision,raw_payload,hash) VALUES(?,?,?,?,?)',(revision,uid,'1',json.dumps({'title':'<script>fixture</script>','raw':{'complete':True}}),'synthetic-hash'))
    _,key=app.state.security.create_key('reader',[p],['project_read'],actor='admin')
    _,foreign=app.state.security.create_key('foreign',['other'],['project_read'],actor='admin');c.cookies.clear();headers={'X-API-Key':key};other={'X-API-Key':foreign}
    result=c.get(f'/api/v1/projects/{p}/items',headers=headers)
    assert result.status_code==200 and result.json()[0]['source_item_id']=='x'
    result=c.get(f'/api/v1/items/{uid}/revisions',headers=headers)
    assert result.status_code==200 and result.json()[0]['item']['raw']=={'complete':True}
    assert c.get(f'/api/v1/items/{uid}/chunks',headers=headers).json()==[]
    for path in [f'/projects/{p}/items',f'/items/{uid}/revisions',f'/items/{uid}/chunks']:
        assert c.get('/api/v1'+path,headers=other).status_code==404
    assert c.get(f'/api/v1/projects/{p}/items?limit=0',headers=headers).status_code==422


def test_diagnostics_include_successful_and_pre_revision_failed_items(env):
    from almrag.queue import Queue
    app,c,h,db,calls=env;p=project(env,register(env));job=Queue(db).enqueue(p,'COLLECT')['job_id']
    with db.transaction() as sql:
        sql.execute("INSERT INTO collection_outcomes(job_id,source_item_id,state) VALUES(?,'1','SUCCEEDED')",(job,))
        sql.execute("INSERT INTO collection_outcomes(job_id,source_item_id,state,error_code) VALUES(?,'2','FAILED','HTTP_503')",(job,))
    response=c.get(f'/api/v1/jobs/{job}/diagnostics',headers=h)
    assert response.status_code==200
    assert {r['state'] for r in response.json()}=={'SUCCEEDED','FAILED'}
    assert all(r['stage']=='COLLECT' and r['job_id']==job for r in response.json())
    assert next(r for r in response.json() if r['state']=='FAILED')['http_status']==503


def test_document_summary_outbox_admin_only_and_rejects_confidential_payload(env):
    app,c,h,db,calls=env;p=project(env,register(env))
    summary=dict(commit='a'*40,milestone='M5',status='IN_PROGRESS',srs_ids=['SRS-042'],passed=1,failed=0,not_verified=2)
    response=c.post('/api/v1/docs/summaries',headers=h,json=summary)
    assert response.status_code==202,response.text
    assert response.json()['state']=='PENDING'
    assert c.post('/api/v1/docs/summaries',headers=h,json={**summary,'raw_item':'confidential'}).status_code==422
    _,key=app.state.security.create_key('project-admin',[p],['system_admin'],actor='admin');c.cookies.clear()
    assert c.post('/api/v1/docs/summaries',headers={'X-API-Key':key},json=summary).status_code==403
    with db.connect() as sql:assert sql.execute("SELECT count(*) FROM doc_summary_outbox WHERE state='PENDING'").fetchone()[0]==1


def test_job_progress_counts_are_visible_without_internal_lease_fields(env):
    from almrag.queue import Queue
    app,c,h,db,calls=env;p=project(env,register(env));job=Queue(db).enqueue(p,'SYNC')['job_id']
    with db.transaction() as sql:sql.execute('UPDATE jobs SET progress_total=10,succeeded_items=7,failed_items=3 WHERE job_id=?',(job,))
    response=c.get('/api/v1/jobs/'+job,headers=h)
    assert response.status_code==200
    assert (response.json()['progress_total'],response.json()['succeeded_items'],response.json()['failed_items'])==(10,7,3)
    assert 'fencing_token' not in response.text and 'checkpoint' not in response.text
