"""SRS-025/030/031/057: operations via authenticated API, no local live DB replacement."""
from typer.testing import CliRunner
from almrag import cli


def test_operation_cli_paths_are_opaque_and_authorization_is_server_side(monkeypatch):
    calls=[];monkeypatch.setattr(cli,'request',lambda *args:calls.append(args));runner=CliRunner()
    for args in [['export-project','p/id'],['import-project','p','ref','--expected-sha256','a'*64],['artifacts','p'],['backups'],['create-backup'],['prepare-restore','backup/id'],['restore-backup','backup','--manifest-hash','a'*64,'--confirmation-nonce','b'*40],['diagnostics','job/id']]:
        response=runner.invoke(cli.app,args);assert response.exit_code==0,response.output
    assert calls[0]==('POST','/projects/p%2Fid/export')
    assert calls[1][2]=={'artifact_ref':'ref','import_mode':'MERGE_ONLY','expected_sha256':'a'*64}
    assert calls[5]==('POST','/backups/backup%2Fid/prepare-restore')
    assert calls[6][2]=={'manifest_hash':'a'*64,'confirmation_nonce':'b'*40}
    assert calls[7]==('GET','/jobs/job%2Fid/diagnostics?limit=100&offset=0')
