"""SRS-025..029/051/052/059: explicit, sanitized deployment diagnostics."""
import json
import sqlite3

from almrag.config import Settings
from almrag.doctor import inspect_server
from almrag.storage import Database


def test_offline_never_connects_or_creates_database(tmp_path, monkeypatch):
    import httpx
    monkeypatch.setattr(httpx.Client, 'get', lambda *a, **k: (_ for _ in ()).throw(AssertionError('network')))
    path=tmp_path/'missing'/'alm.sqlite'
    report=inspect_server(Settings(database_path=str(path)))
    assert not path.exists() and not path.parent.exists()
    checks={row['check']:row for row in report['checks']}
    assert checks['sqlite']['status']=='NOT VERIFIED'
    assert checks['ollama']['status']=='NOT VERIFIED'
    assert checks['qdrant']['status']=='NOT VERIFIED'
    assert checks['alm']['status']=='NOT VERIFIED'


def test_existing_database_read_only_and_healthy(tmp_path):
    path=tmp_path/'alm.sqlite'
    Database(path).migrate()
    before=path.read_bytes()
    report=inspect_server(Settings(database_path=str(path)))
    checks={row['check']:row for row in report['checks']}
    assert checks['sqlite']['status']=='PASS'
    assert before==path.read_bytes()


def test_corrupt_db_is_failure_without_leaking_paths(tmp_path):
    path=tmp_path/'customer-secret.sqlite'
    path.write_text('not sqlite')
    report=inspect_server(Settings(database_path=str(path),master_key='never-print-this'))
    assert any(x['check']=='sqlite' and x['status']=='FAIL' for x in report['checks'])
    assert 'customer-secret' not in json.dumps(report)
    assert 'never-print-this' not in json.dumps(report)


def test_explicit_service_probes_use_resolver_and_hide_errors(tmp_path, monkeypatch):
    from almrag.services import ServiceProbe
    calls=[]
    def check(self,service):
        calls.append((service,self.secret_resolver('env:TEST_DOCTOR_SECRET')))
        return {'service':service,'available':service=='ollama'}
    monkeypatch.setenv('TEST_DOCTOR_SECRET','do-not-print')
    monkeypatch.setattr(ServiceProbe,'check',check)
    settings=Settings(database_path=str(tmp_path/'absent'),ollama_auth_ref='env:TEST_DOCTOR_SECRET')
    report=inspect_server(settings,services=True)
    checks={row['check']:row for row in report['checks']}
    assert checks['ollama']['status']=='PASS' and checks['qdrant']['status']=='FAIL'
    assert len(calls)==2 and all(secret=='do-not-print' for _,secret in calls)
    assert 'do-not-print' not in json.dumps(report)


def test_schema_drift_fails_without_migrating(tmp_path):
    path=tmp_path/'old.sqlite'
    with sqlite3.connect(path) as c:c.execute('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY)')
    report=inspect_server(Settings(database_path=str(path)))
    assert any(x['check']=='sqlite' and x['status']=='FAIL' for x in report['checks'])
    with sqlite3.connect(path) as c:assert c.execute('SELECT count(*) FROM schema_migrations').fetchone()[0]==0


def test_alm_probe_success_uses_read_only_connector_contract(tmp_path,monkeypatch):
    from almrag.connection import Connections
    path=tmp_path/'alm.sqlite'
    Database(path).migrate()
    class Connector:
        def probe(self):return {'read_only':True,'project_count':1,'server_compatibility':'NOT_VERIFIED'}
    monkeypatch.setattr(Connections,'connector',lambda self,uid:Connector())
    report=inspect_server(Settings(database_path=str(path),live_alm_enabled=True),alm_instance='synthetic-id')
    assert any(x['check']=='alm' and x['status']=='PASS' for x in report['checks'])


def test_service_vault_reference_does_not_create_missing_database(tmp_path):
    from cryptography.fernet import Fernet
    path=tmp_path/'missing.sqlite'
    settings=Settings(database_path=str(path),master_key=Fernet.generate_key().decode(),
                      ollama_auth_ref='vault:missing',qdrant_auth_ref='vault:missing')
    report=inspect_server(settings,services=True)
    assert not path.exists()
    assert all(x['status']=='FAIL' for x in report['checks'] if x['check'] in {'ollama','qdrant'})


def test_cli_output_and_exit_status(tmp_path,monkeypatch,capsys):
    from almrag.doctor import main
    monkeypatch.setenv('ALMRAG_DATABASE_PATH',str(tmp_path/'none.sqlite'))
    monkeypatch.setattr('sys.argv',['check_server.py'])
    assert main()==0
    output=json.loads(capsys.readouterr().out)
    assert output['summary']['NOT VERIFIED']>=4


def test_standalone_deployment_security_and_shared_environment():
    from pathlib import Path
    import yaml
    config=yaml.safe_load((Path(__file__).parents[1]/'deploy/compose.intranet.yaml').read_text())
    services=config['services']
    assert services['api']['env_file']==services['worker']['env_file']
    assert services['api']['environment']==services['worker']['environment']
    for name in ('api','worker'):
        assert 'ports' not in services[name]
        assert services[name]['restart']=='unless-stopped'
        assert any(str(v).endswith(':/app/config:ro') for v in services[name]['volumes'])
    assert 'ports' not in services['qdrant']
    assert services['qdrant']['environment']['QDRANT__SERVICE__API_KEY'].startswith('${ALMRAG_QDRANT_API_KEY:?')
