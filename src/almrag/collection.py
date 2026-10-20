"""Read-only collection with immutable observations and lease-fenced persistence.

Collection readiness deliberately excludes processing, embeddings and publication.
All source I/O is performed by an injected connector, which owns shared transport.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

from .queue import LeaseLost, Queue
from .storage import canonical_uid


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


class CollectionError(ValueError):
    def __init__(self, code, *, global_error=True, stop_state='BLOCKED'):
        super().__init__(code)
        self.code = code
        self.global_error = global_error
        self.stop_state = stop_state


def _error_code(error):
    code = getattr(error, 'code', 'ITEM_ERROR')
    return code if isinstance(code, str) and re.fullmatch('[A-Z][A-Z0-9_]{0,63}', code) else 'ITEM_ERROR'


class CollectionService:
    def __init__(self, db, connector_factory, attachment_root):
        self.db = db
        self.connector_factory = connector_factory
        self.attachment_root = Path(attachment_root).resolve()
        self.queue = Queue(db)

    def _instance(self, instance_uid):
        with self.db.connect() as c:
            row = c.execute('SELECT * FROM instances WHERE instance_uid=?', (instance_uid,)).fetchone()
        if row is None:
            raise CollectionError('INSTANCE_NOT_FOUND')
        return dict(row)

    def configure_project(self, instance_uid, source_project_id, name,
                          selection_mode='ALL', scope_kind='TRACKER', scope_ids=None,
                          embedding_fields=None):
        instance = self._instance(instance_uid)
        expected = 'TRACKER' if instance['source_type'] == 'codebeamer' else 'WORK_ITEM_TYPE'
        if selection_mode not in {'ALL', 'SELECTED'} or scope_kind != expected:
            raise CollectionError('INVALID_SCOPE')
        scope_ids = sorted(set(str(x) for x in (scope_ids or [])))
        embedding_fields = sorted(set(embedding_fields if embedding_fields is not None else ['title', 'description']))
        if not embedding_fields or not all(isinstance(x, str) and x for x in embedding_fields):
            raise CollectionError('INVALID_FIELDS')
        if selection_mode == 'SELECTED' and not scope_ids:
            raise CollectionError('EMPTY_SCOPE')
        adapter = self.connector_factory(instance_uid)
        projects = adapter.list_projects()
        if str(source_project_id) not in {str(x['id']) for x in projects}:
            raise CollectionError('PROJECT_NOT_DISCOVERED')
        catalog = adapter.list_scopes(str(source_project_id))
        if any(x.get('kind', expected) != expected for x in catalog):
            raise CollectionError('INVALID_SCOPE_KIND')
        if set(scope_ids) - {str(x['id']) for x in catalog}:
            raise CollectionError('SCOPE_NOT_DISCOVERED')
        project_uid = canonical_uid('project', instance_uid, str(source_project_id))
        with self.db.transaction() as c:
            c.execute('INSERT INTO projects(project_uid,instance_uid,source_project_id,name) VALUES(?,?,?,?) ON CONFLICT(project_uid) DO UPDATE SET name=excluded.name',
                      (project_uid, instance_uid, str(source_project_id), name))
            c.execute('INSERT INTO project_selections(project_uid,selection_mode,scope_kind,scope_ids,config_revision) VALUES(?,?,?,?,1) ON CONFLICT(project_uid) DO UPDATE SET selection_mode=excluded.selection_mode,scope_kind=excluded.scope_kind,scope_ids=excluded.scope_ids,config_revision=project_selections.config_revision+1,preflight_status=NULL,scope_snapshot_hash=NULL',
                      (project_uid, selection_mode, scope_kind, _json(scope_ids)))
            c.execute('INSERT INTO collection_configs VALUES(?,?) ON CONFLICT(project_uid) DO UPDATE SET embedding_fields=excluded.embedding_fields', (project_uid, _json(embedding_fields)))
        return project_uid

    def _config(self, project_uid, c=None):
        if c is None:
            with self.db.connect() as connection:
                return self._config(project_uid, connection)
        row = c.execute('SELECT p.project_uid,p.instance_uid,p.source_project_id,s.selection_mode,s.scope_kind,s.scope_ids,s.config_revision,c.embedding_fields FROM projects p JOIN project_selections s USING(project_uid) JOIN collection_configs c USING(project_uid) WHERE project_uid=?', (project_uid,)).fetchone()
        if row is None:
            raise CollectionError('PROJECT_NOT_CONFIGURED')
        result = dict(row)
        result['scope_ids'] = json.loads(result['scope_ids'])
        result['embedding_fields'] = json.loads(result['embedding_fields'])
        return result

    def _preflight(self, project_uid):
        config = self._config(project_uid)
        adapter = self.connector_factory(config['instance_uid'])
        probe = adapter.probe()
        if probe.get('ok') is False or probe.get('status') in {'FAILED', 'BLOCKED', 'ERROR'}:
            raise CollectionError('PROBE_FAILED')
        if config['source_project_id'] not in {str(x['id']) for x in adapter.list_projects()}:
            raise CollectionError('PROJECT_NOT_DISCOVERED')
        scopes = adapter.list_scopes(config['source_project_id'])
        expected = config['scope_kind']
        if any(x.get('kind', expected) != expected for x in scopes):
            raise CollectionError('INVALID_SCOPE_KIND')
        catalog_ids = sorted({str(x['id']) for x in scopes})
        chosen = catalog_ids if config['selection_mode'] == 'ALL' else config['scope_ids']
        if not chosen or set(chosen) - set(catalog_ids):
            raise CollectionError('SCOPE_NOT_DISCOVERED')
        fields = adapter.list_fields(config['source_project_id'], chosen)
        field_ids = {str(x['id']) for x in fields}
        # These are envelope capabilities, not synthetic source catalog entries.
        normalized_fields = getattr(adapter, 'normalized_fields', ())
        if not isinstance(normalized_fields, (list, tuple, set, frozenset)) or not all(isinstance(x, str) and x for x in normalized_fields):
            raise CollectionError('INVALID_NORMALIZED_FIELDS')
        normalized_fields = sorted(set(normalized_fields))
        if set(config['embedding_fields']) - (field_ids | set(normalized_fields)):
            raise CollectionError('FIELD_NOT_READABLE')
        refs = list(adapter.iter_refs(config['source_project_id'], chosen))
        # Count complete enumeration only; a partial generator never becomes READY.
        self._validate_refs(refs, chosen)
        snapshot = {**config, 'source_scope_ids': chosen, 'readable_fields': fields,
                    'normalized_fields': normalized_fields,
                    'scope_catalog': sorted(scopes, key=lambda x: str(x['id']))}
        policy = getattr(getattr(adapter, 'client', None), 'policy', None)
        if policy is not None:
            if hasattr(policy, 'model_dump'):
                snapshot['http_policy'] = policy.model_dump(mode='json')
            elif isinstance(policy, dict):
                snapshot['http_policy'] = policy
            else:
                raise CollectionError('INVALID_TRANSPORT_POLICY')
        revision = _digest(snapshot)
        pre = {'status': 'READY', 'collect_ready': True, 'sync_ready': False,
               'scope_kind': expected, 'source_scope_ids': chosen, 'readable_fields': fields,
               'normalized_fields': normalized_fields,
               'estimated_items': len({str(x['id']) for x in refs}),
               'estimated_requests': None, 'request_estimate_kind': 'UNKNOWN',
               # Only the mandatory Item detail calls are a defensible lower bound.
               'request_count_lower_bound': len({str(x['id']) for x in refs}),
               'config_revision': revision,
               'diagnostics': ['PROCESS_EMBED_INDEX_NOT_AVAILABLE',
                               'REQUEST_COUNT_UNKNOWN_PAGINATION_ATTACHMENTS_RETRIES']}
        return pre, snapshot

    def preflight(self, project_uid):
        try:
            return self._preflight(project_uid)[0]
        except (LeaseLost, sqlite3.Error):
            raise
        except Exception as error:
            return {'status': 'BLOCKED', 'collect_ready': False, 'sync_ready': False,
                    'scope_kind': None, 'source_scope_ids': [], 'readable_fields': [],
                    'normalized_fields': [], 'request_estimate_kind': 'UNKNOWN',
                    'request_count_lower_bound': None,
                    'estimated_items': None, 'estimated_requests': None, 'config_revision': None,
                    'diagnostics': [_error_code(error)]}

    def enqueue(self, project_uid, config_revision=None):
        pre, snapshot = self._preflight(project_uid)
        if config_revision is not None and config_revision != pre['config_revision']:
            raise CollectionError('STALE_PREFLIGHT')
        job_id = str(uuid.uuid4())
        now = time.time()
        with self.db.transaction() as c:
            # Do not pin a catalog retrieved for a concurrently changed local config.
            if self._config(project_uid, c) != {key: snapshot[key] for key in self._config(project_uid, c)}:
                raise CollectionError('STALE_PREFLIGHT')
            c.execute('INSERT INTO jobs(job_id,project_uid,stage,created_at,updated_at) VALUES(?,?,?,?,?)', (job_id, project_uid, 'COLLECT', now, now))
            c.execute('INSERT INTO collection_snapshots VALUES(?,?,?)', (job_id, pre['config_revision'], _json(snapshot)))
            Queue._event(c, job_id, 'QUEUED', now)
            return Queue._row(c.execute('SELECT * FROM jobs WHERE job_id=?', (job_id,)).fetchone())

    def _guard(self, c, job):
        Queue._guard(c, job['job_id'], job['fencing_token'], time.time())

    def _live(self, job, abort_check):
        with self.db.transaction() as c:
            self._guard(c, job)
        if abort_check():
            raise CollectionError('ABORT_REQUESTED', stop_state='CANCELLED')

    @staticmethod
    def _validate_refs(refs, chosen):
        seen = {}
        for ref in refs:
            if not isinstance(ref, dict) or not str(ref.get('id', '')) or str(ref.get('scope_id')) not in chosen:
                raise CollectionError('INVALID_ITEM_REFERENCE')
            key = str(ref['id'])
            if key in seen and seen[key] != ref:
                raise CollectionError('DUPLICATE_ITEM_REFERENCE')
            seen[key] = ref
        return list(seen.values())

    def _snapshot(self, job):
        with self.db.connect() as c:
            row = c.execute('SELECT snapshot FROM collection_snapshots WHERE job_id=?', (job['job_id'],)).fetchone()
        if row is None:
            raise CollectionError('COLLECTION_SNAPSHOT_MISSING')
        snapshot = json.loads(row['snapshot'])
        if snapshot['project_uid'] != job['project_uid']:
            raise CollectionError('SNAPSHOT_PROJECT_MISMATCH')
        return snapshot

    def _list(self, adapter, snapshot, job, abort_check):
        self._live(job, abort_check)
        if snapshot['source_project_id'] not in {str(x['id']) for x in adapter.list_projects()}:
            raise CollectionError('PROJECT_NOT_DISCOVERED')
        self._live(job, abort_check)
        scopes = adapter.list_scopes(snapshot['source_project_id'])
        if set(snapshot['source_scope_ids']) - {str(x['id']) for x in scopes}:
            raise CollectionError('SCOPE_NOT_DISCOVERED')
        if 'refs' in snapshot:
            return snapshot['refs']
        self._live(job, abort_check)
        iterator = iter(adapter.iter_refs(snapshot['source_project_id'], snapshot['source_scope_ids']))
        refs = []
        while True:
            self._live(job, abort_check)
            try:
                refs.append(next(iterator))
            except StopIteration:
                break
        refs = self._validate_refs(refs, snapshot['source_scope_ids'])
        snapshot['refs'] = refs
        with self.db.transaction() as c:
            self._guard(c, job)
            c.execute('UPDATE collection_snapshots SET snapshot=? WHERE job_id=?', (_json(snapshot), job['job_id']))
            c.execute('UPDATE jobs SET progress_total=?,updated_at=? WHERE job_id=?', (len(refs), time.time(), job['job_id']))
        return refs

    def run(self, job, abort_check=lambda: False):
        if job.get('stage') != 'COLLECT':
            raise CollectionError('STAGE_NOT_IMPLEMENTED')
        adapter = None
        previous_abort = None
        try:
            self._live(job, abort_check)
            snapshot = self._snapshot(job)
            adapter = self.connector_factory(snapshot['instance_uid'])
            if hasattr(adapter, 'client'):
                previous_abort = getattr(adapter.client, 'abort_check', None)
                def transport_abort():
                    with self.db.transaction() as c:
                        self._guard(c, job)
                    return abort_check()
                adapter.client.abort_check = transport_abort
            try:
                refs = self._list(adapter, snapshot, job, abort_check)
            except (CollectionError, LeaseLost, sqlite3.Error):
                raise
            except Exception as error:
                raise CollectionError(_error_code(error), stop_state=getattr(error, 'stop_state', 'BLOCKED')) from error
            for ref in refs:
                self._live(job, abort_check)
                source_id = str(ref['id'])
                with self.db.connect() as c:
                    done = c.execute('SELECT 1 FROM collection_outcomes WHERE job_id=? AND source_item_id=?', (job['job_id'], source_id)).fetchone()
                if done:
                    continue
                try:
                    envelope = adapter.get_item(snapshot['source_project_id'], source_id)
                    self._live(job, abort_check)
                    self._validate_envelope(envelope, ref, snapshot)
                    files = self._attachments(adapter, snapshot, envelope, job, abort_check)
                    self._save(snapshot, ref, envelope, files, job)
                except (LeaseLost, sqlite3.Error):
                    raise
                except OSError as error:
                    raise CollectionError('STORAGE_ERROR') from error
                except Exception as error:
                    code = _error_code(error)
                    if getattr(error, 'global_error', False) or code in {'UNAUTHORIZED', 'AUTH_FAILED', 'HTTP_401', 'CIRCUIT_OPEN', 'INTEGRITY_ERROR', 'REVISION_CONFLICT'}:
                        raise CollectionError(code, stop_state=getattr(error, 'stop_state', 'BLOCKED')) from error
                    self._failure(job, snapshot, ref, code)
            self._memberships(job, snapshot, refs)
            with self.db.transaction() as c:
                self._guard(c, job)
                failed = c.execute("SELECT count(*) FROM collection_outcomes WHERE job_id=? AND state='FAILED'", (job['job_id'],)).fetchone()[0]
            state = 'COMPLETED_WITH_ERRORS' if failed else 'SUCCEEDED'
            self.queue.finish(job['job_id'], job['fencing_token'], state)
            return state
        except LeaseLost:
            raise
        except sqlite3.Error:
            self.queue.finish(job['job_id'], job['fencing_token'], 'BLOCKED', 'STORAGE_ERROR')
            return 'BLOCKED'
        except Exception as error:
            state = getattr(error, 'stop_state', 'BLOCKED')
            if state not in {'PAUSED', 'BLOCKED', 'FAILED', 'CANCELLED'}:
                state = 'BLOCKED'
            self.queue.finish(job['job_id'], job['fencing_token'], state, _error_code(error))
            return state
        finally:
            if adapter is not None and hasattr(adapter, 'client'):
                adapter.client.abort_check = previous_abort

    @staticmethod
    def _validate_envelope(envelope, ref, snapshot):
        if not isinstance(envelope, dict) or str(envelope.get('id')) != str(ref['id']):
            raise CollectionError('ITEM_ID_MISMATCH')
        if str(envelope.get('project_id')) != snapshot['source_project_id']:
            raise CollectionError('ITEM_PROJECT_MISMATCH')
        if str(envelope.get('scope_id')) != str(ref['scope_id']):
            raise CollectionError('ITEM_SCOPE_MISMATCH')
        if any(key not in envelope for key in ('raw', 'fields', 'relations', 'attachments', 'description')):
            raise ValueError('incomplete envelope')
        _json(envelope)  # Reject NaN and non-JSON values without truncation.

    def _attachments(self, adapter, snapshot, envelope, job, abort_check):
        files = []
        for index, attachment in enumerate(envelope['attachments']):
            self._live(job, abort_check)
            data = adapter.download_attachment(snapshot['source_project_id'], str(envelope['id']), attachment)
            if not isinstance(data, bytes):
                raise ValueError('attachment must contain bytes')
            self._live(job, abort_check)
            checksum = hashlib.sha256(data).hexdigest()
            attachment_id = canonical_uid('attachment', snapshot['project_uid'], str(envelope['id']), _digest(envelope), str(attachment.get('id', index)), checksum)
            self.attachment_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            target = self.attachment_root / (attachment_id + '-' + checksum)
            temporary = self.attachment_root / (str(uuid.uuid4()) + '.part')
            try:
                with temporary.open('xb') as stream:
                    os.chmod(temporary, 0o600)
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            files.append((attachment_id, attachment, checksum, str(target)))
        return files

    def _save(self, snapshot, ref, envelope, files, job):
        item_uid = canonical_uid('item', snapshot['project_uid'], str(ref['id']))
        digest = _digest({'envelope': envelope, 'attachment_checksums': [entry[2] for entry in files]})
        source_revision = str(envelope['revision']) if envelope.get('revision') is not None else 'observed:' + digest
        revision_uid = canonical_uid('revision', item_uid, source_revision)
        with self.db.transaction() as c:
            self._guard(c, job)
            c.execute('INSERT INTO items(item_uid,project_uid,source_item_id,type,status) VALUES(?,?,?,?,?) ON CONFLICT(item_uid) DO NOTHING', (item_uid, snapshot['project_uid'], str(ref['id']), envelope.get('type'), envelope.get('status')))
            existing = c.execute('SELECT hash FROM item_revisions WHERE revision_uid=?', (revision_uid,)).fetchone()
            if existing and existing['hash'] != digest:
                raise CollectionError('REVISION_CONFLICT')
            if not existing:
                c.execute('INSERT INTO item_revisions(revision_uid,item_uid,source_revision,modified_at,raw_payload,hash) VALUES(?,?,?,?,?,?)', (revision_uid, item_uid, source_revision, envelope.get('modified'), _json(envelope), digest))
                for field in envelope['fields']:
                    source_field_id = str(field['source_field_id'])
                    # A source field ID can be reused with different meaning by another
                    # tracker/type. Keep old project-scoped rows untouched for history.
                    field_scope = _json([snapshot['source_project_id'], snapshot['scope_kind'], str(envelope['scope_id'])])
                    field_uid = canonical_uid('field', snapshot['instance_uid'], snapshot['source_project_id'], snapshot['scope_kind'], str(envelope['scope_id']), source_field_id)
                    c.execute('INSERT INTO field_definitions(field_def_uid,instance_uid,scope,source_field_id) VALUES(?,?,?,?) ON CONFLICT(field_def_uid) DO NOTHING', (field_uid, snapshot['instance_uid'], field_scope, source_field_id))
                    c.execute('INSERT INTO field_values(revision_uid,field_def_uid,raw_value,source_format) VALUES(?,?,?,?)', (revision_uid, field_uid, _json(field.get('raw_value')), field.get('source_format')))
                for index, relation in enumerate(envelope['relations']):
                    relation_uid = canonical_uid('relation', revision_uid, str(index))
                    c.execute('INSERT INTO relations(relation_uid,revision_uid,original_relation_type,source_target_id) VALUES(?,?,?,?)', (relation_uid, revision_uid, str(relation['type']), str(relation['target_id'])))
                for attachment_uid, metadata, checksum, disk_path in files:
                    c.execute('INSERT INTO attachments(attachment_uid,item_uid,revision_uid,source_url,filename,checksum,disk_path,download_status) VALUES(?,?,?,?,?,?,?,?)', (attachment_uid, item_uid, revision_uid, metadata.get('source_url'), metadata.get('filename'), checksum, disk_path, 'DOWNLOADED'))
            c.execute('INSERT INTO item_collection_state VALUES(?,?,?) ON CONFLICT(item_uid) DO UPDATE SET latest_revision_uid=excluded.latest_revision_uid,last_job_id=excluded.last_job_id', (item_uid, revision_uid, job['job_id']))
            # Absence, a status string or a 404 cannot establish deletion.
            deleted = envelope.get('deleted') is True and bool(envelope.get('deletion_evidence'))
            c.execute('UPDATE items SET deleted_state=? WHERE item_uid=?', ('deleted' if deleted else 'active', item_uid))
            self._membership(c, job, snapshot, ref, 'DELETED' if deleted else 'IN_SCOPE')
            c.execute('INSERT INTO collection_outcomes VALUES(?,?,?,?,?,NULL)', (job['job_id'], str(ref['id']), item_uid, revision_uid, 'SUCCEEDED'))
            self._progress(c, job, str(ref['id']))

    def _failure(self, job, snapshot, ref, code):
        item_uid = canonical_uid('item', snapshot['project_uid'], str(ref['id']))
        with self.db.transaction() as c:
            self._guard(c, job)
            existing = c.execute('SELECT item_uid FROM items WHERE item_uid=?', (item_uid,)).fetchone()
            item_uid = item_uid if existing else None
            c.execute('INSERT INTO collection_failures(job_id,source_item_id,project_uid,item_uid,error_code) VALUES(?,?,?,?,?)', (job['job_id'], str(ref['id']), snapshot['project_uid'], item_uid, code))
            c.execute('INSERT INTO collection_outcomes VALUES(?,?,?,NULL,?,?)', (job['job_id'], str(ref['id']), item_uid, 'FAILED', code))
            state = 'UNAUTHORIZED' if code in {'FORBIDDEN', 'HTTP_403'} else 'MISSING' if code in {'NOT_FOUND', 'HTTP_404'} else 'IN_SCOPE'
            self._membership(c, job, snapshot, ref, state)
            self._progress(c, job, str(ref['id']))

    @staticmethod
    def _membership(c, job, snapshot, ref, state):
        c.execute('INSERT INTO collection_memberships VALUES(?,?,?,?,?) ON CONFLICT(project_uid,source_item_id) DO UPDATE SET scope_id=excluded.scope_id,state=excluded.state,last_job_id=excluded.last_job_id', (snapshot['project_uid'], str(ref['id']), str(ref['scope_id']), state, job['job_id']))

    @staticmethod
    def _progress(c, job, source_id):
        counts = dict(c.execute('SELECT state,count(*) FROM collection_outcomes WHERE job_id=? GROUP BY state', (job['job_id'],)).fetchall())
        c.execute('UPDATE jobs SET succeeded_items=?,failed_items=?,skipped_items=?,checkpoint=?,updated_at=? WHERE job_id=?', (counts.get('SUCCEEDED', 0), counts.get('FAILED', 0), counts.get('SKIPPED', 0), _json({'last_source_item_id': source_id, 'outcomes': sum(counts.values())}), time.time(), job['job_id']))

    def _memberships(self, job, snapshot, refs):
        ids = {str(x['id']) for x in refs}
        with self.db.transaction() as c:
            self._guard(c, job)
            prior = c.execute('SELECT source_item_id,scope_id FROM collection_memberships WHERE project_uid=?', (snapshot['project_uid'],)).fetchall()
            for row in prior:
                if row['source_item_id'] not in ids:
                    state = 'MISSING' if row['scope_id'] in snapshot['source_scope_ids'] else 'OUT_OF_SCOPE'
                    c.execute('UPDATE collection_memberships SET state=?,last_job_id=? WHERE project_uid=? AND source_item_id=?', (state, job['job_id'], snapshot['project_uid'], row['source_item_id']))
