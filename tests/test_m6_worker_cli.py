"""SRS-033/034/025/058: independent quality jobs and authenticated CLI."""
from almrag.queue import Queue
from almrag.worker import run_once
from almrag.storage import Database
from typer.testing import CliRunner
from almrag import cli

def test_worker_dispatches_integrity_and_evaluate_without_collection(tmp_path):
    db=Database(tmp_path/'db');db.migrate();i=db.add_instance('codebeamer','https://fixture.invalid','F','env:F');p=db.add_project(i,'p','P');q=Queue(db)
    class Service:
        def run(self,job,abort_check):
            assert not abort_check();q.finish(job['job_id'],job['fencing_token'])
    for stage in ['INTEGRITY','EVALUATE']:
        job=q.enqueue(p,stage)
        assert run_once(q,'quality',quality_service=Service())
        assert q.get_job(job['job_id'])['state']=='SUCCEEDED'

def test_cli_quality_project_and_job_paths_encoded(monkeypatch):
    calls=[];monkeypatch.setattr(cli,'request',lambda *a:calls.append(a));r=CliRunner()
    for args in [['integrity','p/id'],['evaluate','p','dataset'],['quality-report','job/id']]:
        result=r.invoke(cli.app,args);assert result.exit_code==0,result.output
    assert calls[0]==('POST','/projects/p%2Fid/integrity')
    assert calls[1][2]=={'project_uids':['p'],'dataset_ref':'dataset','methods':['dense','keyword','hybrid'],'top_k':10}
    assert calls[2]==('GET','/jobs/job%2Fid/quality-report')

def test_safe_job_log_retains_all_implemented_stage_names():
    from almrag.security import safe_event
    for stage in ['EXPORT','IMPORT','INTEGRITY','EVALUATE','REPLAY','REBUILD']:
        assert safe_event(stage=stage,raw='private text').get('stage')==stage
