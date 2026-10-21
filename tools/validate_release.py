"""Static M1..M6 evidence/CI presence checks; never proof of test execution or chronology."""
import json
from pathlib import Path

REQUIRED_CI=('pytest','validate_baseline.py','validate_release.py','pip-audit','npm test','npm run build','playwright','test:e2e','npm audit','compose','--wait','smoke_m6.py','generate:api','git diff --exit-code')

def validate_manifest(root,payload):
    errors=[];entries=payload.get('milestones',[]) if isinstance(payload,dict) else []
    if len(entries)!=6 or {x.get('id') for x in entries}!={'M'+str(i) for i in range(1,7)}:return ['six unique milestones required']
    root=Path(root).resolve()
    for entry in entries:
        paths=entry.get('tdd')
        if not isinstance(paths,list) or not paths:errors.append(entry['id']+': missing TDD refs');continue
        for name in paths:
            if not isinstance(name,str):errors.append(entry['id']+': invalid evidence ref');continue
            path=(root/name).resolve()
            if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size==0:errors.append(entry['id']+': missing evidence '+name)
        exception=entry.get('exception')
        expected={'issue':'OI-045','status':'TDD_NOT_EVIDENCED','disposition':'USER_ACCEPTED_CHRONOLOGY_EXCEPTION'}
        if exception is not None and (entry['id']!='M2' or exception!=expected):errors.append(entry['id']+': unacknowledged exception')
    return errors

def validate_ci(text):
    return ['missing CI gate '+token for token in REQUIRED_CI if token not in text]

def main():
    root=Path(__file__).resolve().parents[1]
    payload=json.loads((root/'docs/milestones/QUALITY_EVIDENCE.json').read_text())
    errors=validate_manifest(root,payload)+validate_ci((root/'.github/workflows/m1.yml').read_text())
    if errors:
        print('\n'.join(errors));return 1
    print('DOCUMENT_EVIDENCE_PASS_WITH_EXCEPTION: six milestone TDD references and CI gate presence')
    print('LIMITATIONS: static presence only, actual Red/Green execution and chronology require evidence review; M2 OI-045 remains TDD_NOT_EVIDENCED, not PASS')
    return 0

if __name__=='__main__':raise SystemExit(main())
