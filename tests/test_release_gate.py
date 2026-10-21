"""SRS-039/058/059: static evidence gate cannot substitute for real test execution."""
import importlib.util
from pathlib import Path
import pytest

def module():
    spec=importlib.util.spec_from_file_location('release_gate',Path(__file__).resolve().parents[1]/'tools/validate_release.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def fixture(tmp_path):
    for name in ['red.md','green.md']:(tmp_path/name).write_text(name)
    return {'milestones':[{'id':'M'+str(i),'tdd':['red.md','green.md'],'exception':None} for i in range(1,7)]}

def test_missing_evidence_and_unacknowledged_tdd_exception_fail(tmp_path):
    m=module();payload=fixture(tmp_path)
    assert m.validate_manifest(tmp_path,payload)==[]
    payload['milestones'][1]['tdd']=['missing.md']
    assert m.validate_manifest(tmp_path,payload)
    payload=fixture(tmp_path);payload['milestones'][1]['exception']='unexplained historical failure'
    assert m.validate_manifest(tmp_path,payload)
    payload['milestones'][1]['exception']={'issue':'OI-045','status':'TDD_NOT_EVIDENCED','disposition':'USER_ACCEPTED_CHRONOLOGY_EXCEPTION'}
    assert not m.validate_manifest(tmp_path,payload)

def test_ci_gate_missing_required_execution_is_detected():
    m=module();required=['pytest','validate_baseline.py','validate_release.py','pip-audit','npm test','npm run build','playwright','test:e2e','npm audit','compose','--wait','smoke_m6.py','generate:api','git diff --exit-code']
    good='\n'.join(required)
    assert m.validate_ci(good)==[]
    assert m.validate_ci(good.replace('test:e2e',''))
