#!/usr/bin/env python3
"""Static documentation baseline validation; NOT application/unit/integration tests."""
from pathlib import Path
from collections import Counter
import csv, json, re, tomllib, hashlib, sys
try: import yaml
except ImportError: print("BLOCKED: PyYAML is required for schema validation");sys.exit(2)
root=Path(__file__).resolve().parents[1]
def t(p):return (root/p).read_text(encoding="utf-8-sig")
q=list(csv.DictReader((root/"docs/requirements/DECISION_COVERAGE.csv").open(encoding="utf-8-sig")))
legacy=list(csv.DictReader((root/"docs/requirements/LEGACY_REQ_TRACEABILITY.csv").open(encoding="utf-8-sig")))
trace=list(csv.DictReader((root/"docs/requirements/TRACEABILITY.csv").open(encoding="utf-8-sig")))
srs_ids=set(re.findall(r"\| (SRS-\d{3}) \|",t("docs/requirements/SRS.md")))
srs_ids.discard('SRS-xxx')
assert len(q)==50 and not [x for x in q if x['coverage_status']!='DECISION_MAPPED']
assert len(legacy)==252
assert len(trace)==59 and {x['srs_id'] for x in trace}==srs_ids
assert all(x['primary_milestone'] in {'M1','M2','M3','M4','M5','M6'} for x in trace)
assert len({x['verification_id'] for x in trace})==59
for row in trace:
 p=next(root.glob('plans/'+row['primary_milestone']+'_*.md'))
 assert row['srs_id'] in p.read_text(),(row['srs_id'],p)
conf=tomllib.loads(t('.codex/config.toml'))
assert conf['features']['multi_agent'] and len([x for x in conf['agents'] if isinstance(conf['agents'][x],dict)])==6
for name,d in conf['agents'].items():
 if isinstance(d,dict):assert (root/'.codex'/d['config_file']).exists(),name
api=yaml.safe_load(t('docs/api/openapi.yaml'))
assert api['openapi'].startswith('3.')
ops=[]
for path,methods in api['paths'].items():
 for verb,o in methods.items():
  if verb not in ('get','post','put','delete','patch'):continue
  ops.append(o['operationId'])
  assert o.get('x-required-scope'),(path,verb)
  param_names={x['name'] for x in o.get('parameters',[]) if x.get('in')=='path'}
  assert set(re.findall(r'\{(\w+)\}',path))==param_names,(path,param_names)
assert len(ops)==len(set(ops)),"duplicate operationId"
assert 'not probability' not in t('docs/api/openapi.yaml')
refs=re.findall(r'#/components/schemas/([A-Za-z0-9_]+)',t('docs/api/openapi.yaml'))
assert set(refs).issubset(api['components']['schemas']),set(refs)-set(api['components']['schemas'])
for f in root.rglob('*.toml'):tomllib.loads(f.read_text())
for f in root.rglob('*.yaml'):yaml.safe_load(f.read_text())
print('DOC_STATIC_PASS: 50 decisions, 252 legacy mapping rows, 59 SRS, 59 assigned milestones/tests, 6 subagents, '+str(len(ops))+' draft API operations, YAML+TOML valid')
print('LIMITATIONS: original legacy REQ text unavailable; no live backend, database, ALM, Docker, model, Codex runtime tests executed')
