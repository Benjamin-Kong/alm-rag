"""Opt-in server diagnostics. Default inspection never opens network connections."""
import importlib.util
import os
from pathlib import Path
import sqlite3
import sys

from almrag.connection import Connections
from almrag.services import ServiceProbe
from almrag.storage import Database


def inspect_server(settings, *, services=False, alm_instance=None):
    checks=[]
    def record(name,status,code):
        checks.append({'check':name,'status':status,'code':code})
    dependencies=('fastapi','uvicorn','httpx','pydantic','tokenizers','cryptography')
    ready=(3,12)<=sys.version_info<(3,13) and all(importlib.util.find_spec(name) is not None for name in dependencies)
    record('runtime','PASS' if ready else 'FAIL','RUNTIME_READY' if ready else 'RUNTIME_DEPENDENCIES_MISSING')
    path=Path(settings.database_path)
    parent=path.parent
    while not parent.exists() and parent!=parent.parent:parent=parent.parent
    writable=os.access(parent,os.W_OK|os.X_OK)
    record('storage_parent','PASS' if writable else 'FAIL','PARENT_WRITABLE' if writable else 'PARENT_NOT_WRITABLE')
    if path.is_file():
        try:
            # No migration, journal-mode change, persistent temporary file or schema mutation.
            with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=5) as db:
                db.execute('PRAGMA query_only=ON')
                valid=db.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
                valid=valid and not db.execute('PRAGMA foreign_key_check').fetchall()
                actual={x[0] for x in db.execute('SELECT version FROM schema_migrations')}
                expected={int(p.name.split('_',1)[0]) for p in (Path(__file__).parent/'migrations').glob('[0-9]*_*.sql')}
                valid=valid and actual==expected
            record('sqlite','PASS' if valid else 'FAIL','SQLITE_READY' if valid else 'SQLITE_INTEGRITY_OR_SCHEMA_INVALID')
        except (sqlite3.Error,OSError,ValueError):
            record('sqlite','FAIL','SQLITE_UNREADABLE_OR_INVALID')
    else:record('sqlite','NOT VERIFIED','SQLITE_NOT_INITIALIZED')
    if settings.ca_bundle:
        import ssl
        try:
            ssl.create_default_context(cafile=settings.ca_bundle)
            record('ca_bundle','PASS','CA_BUNDLE_VALID')
        except (OSError,ValueError):record('ca_bundle','FAIL','CA_BUNDLE_INVALID')
    if settings.model_profile_path:
        from almrag.model_runtime import LocalModelProfile
        from almrag.embedding import LocalTokenizer
        try:
            profile_path=Path(settings.model_profile_path)
            profile=LocalModelProfile.model_validate_json(profile_path.read_bytes())
            tokenizer=Path(profile.tokenizer_path)
            if not tokenizer.is_absolute():tokenizer=profile_path.parent/tokenizer
            LocalTokenizer(tokenizer,profile.tokenizer_sha256)
            record('model_profile','PASS','LOCAL_PROFILE_VALID')
        except (ValueError,OSError):record('model_profile','FAIL','LOCAL_PROFILE_INVALID')
    else:record('model_profile','NOT VERIFIED','MODEL_PROFILE_UNCONFIGURED')
    connections=Connections(Database(path),settings)
    def resolve(ref):
        if ref.startswith('vault:') and not path.is_file():raise ValueError('DATABASE_MISSING')
        return connections.secret(ref)
    for service in ('ollama','qdrant'):
        if not services:
            record(service,'NOT VERIFIED','NETWORK_PROBE_NOT_REQUESTED')
            continue
        try:
            available=ServiceProbe(settings,secret_resolver=resolve).check(service)['available']
            record(service,'PASS' if available else 'FAIL','SERVICE_REACHABLE' if available else 'SERVICE_UNAVAILABLE')
        except Exception:
            # Neither exception strings nor URLs/credentials/customer metadata are emitted.
            record(service,'FAIL','SERVICE_PROBE_FAILED')
    if alm_instance is None:record('alm','NOT VERIFIED','NETWORK_PROBE_NOT_REQUESTED')
    elif not settings.live_alm_enabled or not path.is_file():record('alm','FAIL','ALM_PROBE_DISABLED_OR_DATABASE_MISSING')
    else:
        try:
            result=connections.connector(alm_instance).probe()
            ok=result.get('read_only') is True and isinstance(result.get('project_count'),int)
            record('alm','PASS' if ok else 'FAIL','ALM_READ_PROBE_OK' if ok else 'ALM_READ_PROBE_FAILED')
        except Exception:record('alm','FAIL','ALM_READ_PROBE_FAILED')
    return {'checks':checks,'summary':{status:sum(x['status']==status for x in checks) for status in ('PASS','FAIL','NOT VERIFIED')}}


def main():
    import argparse
    import json
    from almrag.config import Settings
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--services',action='store_true',help='Explicit read-only Ollama and Qdrant HTTP probes')
    parser.add_argument('--alm-instance',help='Explicit registered ALM read-only probe; local rate-limit state can change')
    args=parser.parse_args()
    try:report=inspect_server(Settings.from_env(),services=args.services,alm_instance=args.alm_instance)
    except (ValueError,OSError):
        report={'checks':[{'check':'configuration','status':'FAIL','code':'CONFIGURATION_INVALID'}],
                'summary':{'PASS':0,'FAIL':1,'NOT VERIFIED':0}}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 1 if report['summary']['FAIL'] else 0


if __name__=='__main__':raise SystemExit(main())
