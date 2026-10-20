"""SRS-053/055: PROCESS/EMBED worker dispatch and UI-independent CLI."""
import pytest
from almrag.queue import Queue
from almrag.storage import Database
from almrag.worker import run_once
from almrag import cli
from typer.testing import CliRunner

@pytest.mark.parametrize('stage',['PROCESS','EMBED'])
def test_processing_worker_dispatch(tmp_path,stage):
    db=Database(tmp_path/'db');db.migrate();i=db.add_instance('codebeamer','https://fixture.invalid','f','env:F');p=db.add_project(i,'p','P');q=Queue(db);job=q.enqueue(p,stage)
    class Service:
        def run(self,job,abort_check):
            assert not abort_check();q.finish(job['job_id'],job['fencing_token'],'SUCCEEDED')
    assert run_once(q,'test',processing_service=Service())
    assert q.get_job(job['job_id'])['state']=='SUCCEEDED'


def test_processing_cli_paths(monkeypatch,tmp_path):
    calls=[];monkeypatch.setattr(cli,'request',lambda *args:calls.append(args))
    config=tmp_path/'config.json';config.write_text('{"fields": []}')
    for args in [['processing-preflight','p'],['configure-processing','p',str(config)],['process','p'],['embed','p','--config-revision','pinned']]:
        result=CliRunner().invoke(cli.app,args);assert result.exit_code==0,result.output
    assert calls==[('POST','/projects/p/processing-preflight'),('PUT','/projects/p/processing-config',{'fields':[]}),('POST','/projects/p/jobs',{'stage':'PROCESS','config_revision':None}),('POST','/projects/p/jobs',{'stage':'EMBED','config_revision':'pinned'})]
