"""SRS-051/052/059 static prerequisites; actual build/boot is separate evidence."""
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]


def test_deployment_uses_locks_nonroot_and_health():
    backend=(ROOT/'deploy/Dockerfile.backend').read_text()
    frontend=(ROOT/'deploy/Dockerfile.frontend').read_text()
    assert 'uv.lock' in backend and '--frozen' in backend
    assert 'USER ' in backend and 'HEALTHCHECK' in backend
    assert 'npm ci' in frontend and 'USER ' in frontend and 'HEALTHCHECK' in frontend
    for line in (backend+'\n'+frontend).splitlines():
        if line.startswith('FROM '):
            assert '@sha256:' in line
    compose=yaml.safe_load((ROOT/'deploy/compose.yaml').read_text())
    assert compose['services']['api']['environment']['ALMRAG_DATABASE_PATH']=='/app/data/alm.sqlite'
    assert compose['services']['worker']['environment']['ALMRAG_DATABASE_PATH']=='/app/data/alm.sqlite'
    assert compose['services']['worker']['healthcheck']['test'][-1]=='--health'
