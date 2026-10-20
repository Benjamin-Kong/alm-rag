# OI-038 independent reproduction — 2026-10-20

QA ran the following exact diagnostic from Main. Temporary SQLite and synthetic injected client only; no live calls/file edits. Exit0 means the diagnostic executed, not that the implementation passed. The malformed case fails SRS-055; the control confirms the second Item is processable.

```sh
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from almrag.storage import Database
from almrag.queue import Queue
from almrag.connectors import CodebeamerConnector
from almrag.collection import CollectionService
class FakeClient:
 base_url = 'https://synthetic.invalid'
 def __init__(self, malformed):
  self.malformed = malformed
  self.detail_requests = []
 def get_json(self, path, params=None):
  if path == '/v3/projects': return [{'id': 'p', 'name': 'Synthetic'}]
  if path == '/v3/projects/p/trackers': return [{'id': '10', 'name': 'Requirements'}]
  if path == '/v3/trackers/10/fields': return [{'id': '1', 'name': 'Source field'}]
  if path == '/v3/trackers/10/items': return [{'id': '1', 'version': 1}, {'id': '2', 'version': 1}]
  if path in ('/v3/items/1', '/v3/items/2'):
   self.detail_requests.append(path)
   item_id = path.rsplit('/', 1)[-1]
   return {'id': item_id, 'tracker': {'id': '10'}, 'version': 1, 'name': 'Synthetic ' + item_id,
           'descriptionFormat': 'PlainText', 'description': 'Fixture',
           'customFields': {'unexpected': 'shape'} if self.malformed and item_id == '1' else []}
  if path.endswith('/relations'): return {}
  if path.endswith('/attachments'): return []
  raise AssertionError('Unexpected fake request')
for malformed in (True, False):
 with TemporaryDirectory(prefix='almrag-qa-local-item-') as temporary:
  root = Path(temporary)
  db = Database(root / 'fixture.sqlite'); db.migrate()
  instance = db.add_instance('codebeamer', FakeClient.base_url, 'Synthetic', 'ENV:SYNTHETIC')
  client = FakeClient(malformed)
  connector = CodebeamerConnector(client)
  service = CollectionService(db, lambda _: connector, root / 'assets')
  project = service.configure_project(instance, 'p', 'Synthetic', embedding_fields=['1'])
  queued = service.enqueue(project)
  claimed = Queue(db).claim('qa', 300)
  assert claimed['job_id'] == queued['job_id']
  state = service.run(claimed)
  job = Queue(db).get_job(claimed['job_id'])
  with db.connect() as connection:
   counts = {table: connection.execute('SELECT count(*) FROM ' + table).fetchone()[0]
             for table in ('collection_failures', 'collection_outcomes', 'item_revisions')}
  print(json.dumps({'malformed_first_item': malformed, 'state': state,
                    'progress_total': job['progress_total'], 'succeeded_items': job['succeeded_items'],
                    'failed_items': job['failed_items'], 'last_error_code': job['last_error_code'],
                    'detail_requests': client.detail_requests, **counts}, sort_keys=True))
PY
```

Actual independent QA output:

```json
{"collection_failures":0,"collection_outcomes":0,"detail_requests":["/v3/items/1"],"failed_items":0,"item_revisions":0,"last_error_code":"INVALID_SOURCE_PAYLOAD","malformed_first_item":true,"progress_total":2,"state":"BLOCKED","succeeded_items":0}
{"collection_failures":0,"collection_outcomes":2,"detail_requests":["/v3/items/1","/v3/items/2"],"failed_items":0,"item_revisions":2,"last_error_code":null,"malformed_first_item":false,"progress_total":2,"state":"SUCCEEDED","succeeded_items":2}
```

Both independent QA and the collector specialist confirmed Major: this blocks all healthy siblings and records no failed Item. Existing data stays protected; no data loss is claimed. FAIL_SAFE_AND_REPLAY.md section1 requires local field-conversion failures to be recorded while continuing other Items. No implementation correction has been attempted for OI-038 pending the new Human Gate.
