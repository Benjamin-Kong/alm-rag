"""Local versioned raw packages and isolated recovery; no remote/active DB writes."""
import hashlib
import io
import json
import os
from pathlib import Path,PurePosixPath
import sqlite3
import stat
import time
import uuid
import zipfile
from .queue import Queue,LeaseLost
from .storage import Database,canonical_uid
from .source_scope import allows_scope
from importlib.metadata import version,PackageNotFoundError

def _app_version():
    try:return version('alm-rag')
    except PackageNotFoundError:return '0.1.0'


def _json(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def _hash(data):return hashlib.sha256(data).hexdigest()

class OperationsError(ValueError):
    def __init__(self,code,status=422):self.code=code;self.status=status;super().__init__(code)

HASH_ALGORITHM='sha256-canonical-collection-envelope-attachments-v1'
TABLES=('items','item_revisions','field_definitions','field_values','content_blocks','attachments','relations')
KEYS={'items':('item_uid',),'item_revisions':('revision_uid',),'field_definitions':('field_def_uid',),'field_values':('revision_uid','field_def_uid'),'content_blocks':('revision_uid','block_uid'),'attachments':('attachment_uid',),'relations':('relation_uid',)}

class OperationsService:
    MAX_BYTES=256*1024*1024
    MAX_ENTRIES=10000
    def __init__(self,db,artifact_root=None,attachment_root=None,clock=time.time):
        self.db=db;self.queue=Queue(db);self.clock=clock
        self.artifact_root=Path(artifact_root or db.path.parent/'exports').resolve()
        self.attachment_root=Path(attachment_root or db.path.parent/'attachments').resolve()
        self.recovery_root=self.artifact_root/'recoveries'
        self.artifact_root.mkdir(mode=0o700,parents=True,exist_ok=True)
    def _path(self,ref):
        try:assert str(uuid.UUID(ref))==ref
        except (ValueError,TypeError,AssertionError):raise OperationsError('ARTIFACT_NOT_FOUND',404)
        path=self.artifact_root/(ref+'.zip')
        if path.is_symlink():raise OperationsError('ARTIFACT_INVALID')
        return path
    def _project(self,c,p):
        row=c.execute('SELECT p.project_uid,p.instance_uid,p.source_project_id,i.source_type FROM projects p JOIN instances i USING(instance_uid) WHERE project_uid=?',(p,)).fetchone()
        if row is None:raise OperationsError('PROJECT_NOT_FOUND',404)
        return dict(row)
    @staticmethod
    def encode_package(payload,files=None):
        entries={'project.json':_json(payload).encode(),**(files or {})}
        manifest={'format':'ALMRAG_PACKAGE','version':1,'entries':{k:{'sha256':_hash(v),'size':len(v)} for k,v in entries.items()}}
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('manifest.json',_json(manifest))
            for name,value in entries.items():z.writestr(name,value)
        return out.getvalue()
    def _archive_budget(self,data,prefix='PACKAGE'):
        if len(data)>self.MAX_BYTES:raise OperationsError(prefix+'_SIZE_LIMIT')
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            entries=z.infolist()
            if len(entries)>self.MAX_ENTRIES or sum(x.file_size for x in entries)>self.MAX_BYTES:raise OperationsError(prefix+'_SIZE_LIMIT')
    def _decode(self,data):
        if not isinstance(data,bytes) or len(data)>self.MAX_BYTES:raise OperationsError('PACKAGE_SIZE_LIMIT')
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                infos=z.infolist();names=[x.filename for x in infos]
                if len(infos)>self.MAX_ENTRIES or len(names)!=len(set(names)) or sum(x.file_size for x in infos)>self.MAX_BYTES:raise OperationsError('PACKAGE_SIZE_LIMIT')
                for x in infos:
                    p=PurePosixPath(x.filename)
                    if p.is_absolute() or '..' in p.parts or '\\' in x.filename or x.is_dir() or stat.S_ISLNK(x.external_attr>>16) or x.flag_bits&1:raise OperationsError('PACKAGE_PATH_INVALID')
                entries={x.filename:z.read(x) for x in infos}
            manifest=json.loads(entries.pop('manifest.json'))
            if set(manifest)!= {'format','version','entries'} or manifest['format']!='ALMRAG_PACKAGE' or manifest['version']!=1 or set(manifest['entries'])!=set(entries):raise OperationsError('PACKAGE_MANIFEST_INVALID')
            for k,v in entries.items():
                if manifest['entries'][k]!={'sha256':_hash(v),'size':len(v)}:raise OperationsError('PACKAGE_CHECKSUM_MISMATCH')
            if any(k!='project.json' and not k.startswith('attachments/') for k in entries):raise OperationsError('PACKAGE_ENTRY_INVALID')
            payload=json.loads(entries['project.json']);self._validate(payload,entries)
            return payload,entries,manifest
        except OperationsError:raise
        except (ValueError,KeyError,TypeError,zipfile.BadZipFile,RuntimeError,OverflowError):raise OperationsError('PACKAGE_INVALID') from None
    def _validate(self,p,entries):
        if set(p)!={'version','hash_algorithm','project','tables','source_latest','rebuild_required'} or p.get('hash_algorithm')!=HASH_ALGORITHM or p['version']!=1 or p['rebuild_required'] is not True or set(p['tables'])!=set(TABLES):raise OperationsError('PACKAGE_SCHEMA_INVALID')
        project=p['project'];uid=project['project_uid']
        if set(project)!={'project_uid','instance_uid','source_project_id','source_type'} or project['source_type'] not in ('codebeamer','polarion') or uid!=canonical_uid('project',project['instance_uid'],project['source_project_id']):raise OperationsError('PACKAGE_IDENTITY_INVALID')
        with self.db.connect() as c:
            for t in TABLES:
                info=list(c.execute('PRAGMA table_info('+t+')'));columns={r['name'] for r in info};required={r['name'] for r in info if r['notnull'] or r['pk']}
                seen=set()
                if not isinstance(p['tables'][t],list):raise OperationsError('PACKAGE_SCHEMA_INVALID')
                for row in p['tables'][t]:
                    if not isinstance(row,dict) or set(row)!=columns:raise OperationsError('PACKAGE_SCHEMA_INVALID')
                    if any(row[k] is None for k in required):raise OperationsError('PACKAGE_SCHEMA_INVALID')
                    for name,value in row.items():
                        if name=='block_order':
                            if type(value) is not int or value<0:raise OperationsError('PACKAGE_SCHEMA_INVALID')
                        elif value is not None and not isinstance(value,str):raise OperationsError('PACKAGE_SCHEMA_INVALID')
                        if name.endswith('_uid') and value is not None:
                            try:valid=str(uuid.UUID(value))==value
                            except ValueError:valid=False
                            if not valid:raise OperationsError('PACKAGE_IDENTITY_INVALID')
                    if t=='items' and row['deleted_state'] not in ('active','deleted','missing','unauthorized'):raise OperationsError('PACKAGE_SCHEMA_INVALID')
                    if t=='content_blocks' and row['type'] not in ('text','table'):raise OperationsError('PACKAGE_SCHEMA_INVALID')
                    key=tuple(row[k] for k in KEYS[t])
                    if key in seen:raise OperationsError('PACKAGE_IDENTITY_INVALID')
                    seen.add(key)
        items={x['item_uid']:x for x in p['tables']['items']};revs={x['revision_uid']:x for x in p['tables']['item_revisions']};fields={x['field_def_uid'] for x in p['tables']['field_definitions']}
        for item in items.values():
            if item['project_uid']!=uid or item['item_uid']!=canonical_uid('item',uid,item['source_item_id']) or item['active_revision_uid'] is not None:raise OperationsError('PACKAGE_IDENTITY_INVALID')
        for r in revs.values():
            if r['item_uid'] not in items or r['revision_uid']!=canonical_uid('revision',r['item_uid'],r['source_revision']):raise OperationsError('PACKAGE_IDENTITY_INVALID')
            original=json.loads(r['raw_payload'])
            if not isinstance(original,dict) or not {'id','project_id','scope_id','revision','title','description','fields','raw','attachments','relations'}.issubset(original):raise OperationsError('REVISION_FORMAT_UNKNOWN')
            if str(original['id'])!=items[r['item_uid']]['source_item_id'] or str(original['project_id'])!=project['source_project_id'] or not isinstance(original['attachments'],list):raise OperationsError('PACKAGE_IDENTITY_INVALID')
            attachments=[a for a in p['tables']['attachments'] if a['revision_uid']==r['revision_uid']]
            checksums=[];used=set();envelope_digest=_hash(_json(original).encode())
            for index,metadata in enumerate(original['attachments']):
                if not isinstance(metadata,dict):raise OperationsError('REVISION_FORMAT_UNKNOWN')
                matches=[a for a in attachments if a['attachment_uid']==canonical_uid('attachment',uid,str(original['id']),envelope_digest,str(metadata.get('id',index)),a['checksum'])]
                if len(matches)!=1 or matches[0]['attachment_uid'] in used:raise OperationsError('ATTACHMENT_IDENTITY_MISMATCH')
                used.add(matches[0]['attachment_uid']);checksums.append(matches[0]['checksum'])
            if len(used)!=len(attachments):raise OperationsError('ATTACHMENT_IDENTITY_MISMATCH')
            digest=_hash(_json({'envelope':original,'attachment_checksums':checksums}).encode())
            if r['hash']!=digest:raise OperationsError('REVISION_HASH_MISMATCH')
            source_revision=str(original['revision']) if original['revision'] is not None else 'observed:'+digest
            if r['source_revision']!=source_revision:raise OperationsError('PACKAGE_IDENTITY_INVALID')
        latest=p['source_latest']
        if not isinstance(latest,list) or len(latest)!=len(items) or {r.get('item_uid') for r in latest if isinstance(r,dict)}!=set(items):raise OperationsError('SOURCE_LATEST_INVALID')
        for row in latest:
            if not isinstance(row,dict) or set(row)!={'item_uid','revision_uid','scope_id','state'}:raise OperationsError('SOURCE_LATEST_INVALID')
            if row['revision_uid'] is None:
                if row['scope_id'] is not None or row['state']!='UNAVAILABLE':raise OperationsError('SOURCE_LATEST_INVALID')
            else:
                revision=revs.get(row['revision_uid'])
                if revision is None or revision['item_uid']!=row['item_uid'] or row['state'] not in ('IN_SCOPE','OUT_OF_SCOPE','MISSING','UNAUTHORIZED','DELETED'):raise OperationsError('SOURCE_LATEST_INVALID')
                original=json.loads(revision['raw_payload'])
                if not isinstance(row['scope_id'],str) or str(original['scope_id'])!=row['scope_id']:raise OperationsError('SOURCE_LATEST_INVALID')
        scope_kind='TRACKER' if project['source_type']=='codebeamer' else 'WORK_ITEM_TYPE'
        for r in p['tables']['field_definitions']:
            if r['instance_uid']!=project['instance_uid']:raise OperationsError('PACKAGE_IDENTITY_INVALID')
            normalized=r['kind']=='normalized'
            if r['kind'] not in (None,'source','normalized'):raise OperationsError('FIELD_IDENTITY_INVALID')
            references=[v for t in ('field_values','content_blocks') for v in p['tables'][t] if v['field_def_uid']==r['field_def_uid']]
            if not references:raise OperationsError('FIELD_IDENTITY_INVALID')
            for ref in references:
                revision=revs.get(ref['revision_uid'])
                if revision is None:raise OperationsError('FIELD_IDENTITY_INVALID')
                original=json.loads(revision['raw_payload']);scope=str(original['scope_id'])
                expected_scope=(["NORMALIZED"] if normalized else [])+[project['source_project_id'],scope_kind,scope]
                if json.loads(r['scope'])!=expected_scope:raise OperationsError('FIELD_IDENTITY_INVALID')
                source_id=r['source_field_id']
                if normalized:
                    if source_id not in ('normalized:title','normalized:description'):raise OperationsError('FIELD_IDENTITY_INVALID')
                elif not any(str(field.get('source_field_id'))==source_id for field in original['fields'] if isinstance(field,dict)):raise OperationsError('FIELD_IDENTITY_INVALID')
                expected=canonical_uid('normalized-field' if normalized else 'field',project['instance_uid'],project['source_project_id'],scope_kind,scope,source_id)
                if r['field_def_uid']!=expected:raise OperationsError('FIELD_IDENTITY_INVALID')
        expected_relations={}
        for revision in revs.values():
            original=json.loads(revision['raw_payload'])
            if not isinstance(original['relations'],list):raise OperationsError('RELATION_IDENTITY_INVALID')
            for index,relation in enumerate(original['relations']):
                if not isinstance(relation,dict) or 'type' not in relation or 'target_id' not in relation:raise OperationsError('RELATION_IDENTITY_INVALID')
                expected_relations[canonical_uid('relation',revision['revision_uid'],str(index))]=(revision['revision_uid'],str(relation['type']),str(relation['target_id']))
        if {r['relation_uid'] for r in p['tables']['relations']}!=set(expected_relations):raise OperationsError('RELATION_IDENTITY_INVALID')
        for r in p['tables']['relations']:
            if (r['revision_uid'],r['original_relation_type'],r['source_target_id'])!=expected_relations[r['relation_uid']]:raise OperationsError('RELATION_IDENTITY_INVALID')
            if r['target_uid'] is not None and r['target_uid']!=canonical_uid('item',uid,r['source_target_id']):raise OperationsError('RELATION_IDENTITY_INVALID')
        for t in ('field_values','content_blocks','attachments','relations'):
            for r in p['tables'][t]:
                if r['revision_uid'] not in revs:raise OperationsError('PACKAGE_IDENTITY_INVALID')
                if r.get('field_def_uid') is not None and r['field_def_uid'] not in fields:raise OperationsError('PACKAGE_IDENTITY_INVALID')
                if t=='relations' and r['target_uid'] is not None and r['target_uid'] not in items:raise OperationsError('PACKAGE_IDENTITY_INVALID')
                if t=='attachments':
                    if r['disk_path'] is None or r['download_status']!='DOWNLOADED':raise OperationsError('ATTACHMENT_UNAVAILABLE')
                    if r['item_uid']!=revs[r['revision_uid']]['item_uid']:raise OperationsError('PACKAGE_IDENTITY_INVALID')
                    if r['disk_path'] is not None:
                        if not isinstance(r['checksum'],str) or len(r['checksum'])!=64 or any(ch not in '0123456789abcdef' for ch in r['checksum']):raise OperationsError('ATTACHMENT_CHECKSUM_MISMATCH')
                        name='attachments/'+r['attachment_uid']
                        if r['disk_path']!=name or name not in entries or _hash(entries[name])!=r['checksum']:raise OperationsError('ATTACHMENT_CHECKSUM_MISMATCH')
        expected={'project.json'}|{'attachments/'+r['attachment_uid'] for r in p['tables']['attachments'] if r['disk_path'] is not None}
        if set(entries)!=expected:raise OperationsError('PACKAGE_ENTRY_INVALID')
    def _capture(self,c,p):
        project=self._project(c,p)
        tables={}
        tables['items']=[dict(x) for x in c.execute('SELECT * FROM items WHERE project_uid=?',(p,))]
        for x in tables['items']:x['active_revision_uid']=None
        itemids={x['item_uid'] for x in tables['items']}
        for t in TABLES[1:]:
            if t=='item_revisions':sql='SELECT t.* FROM item_revisions t JOIN items i USING(item_uid) WHERE i.project_uid=?'
            elif t=='field_definitions':sql='SELECT DISTINCT t.* FROM field_definitions t WHERE field_def_uid IN (SELECT f.field_def_uid FROM field_values f JOIN item_revisions r USING(revision_uid) JOIN items i USING(item_uid) WHERE i.project_uid=? UNION SELECT b.field_def_uid FROM content_blocks b JOIN item_revisions r USING(revision_uid) JOIN items i USING(item_uid) WHERE i.project_uid=?)'
            else:sql='SELECT t.* FROM '+t+' t JOIN item_revisions r USING(revision_uid) JOIN items i ON i.item_uid=r.item_uid WHERE i.project_uid=?'
            tables[t]=[dict(x) for x in c.execute(sql,(p,p) if t=='field_definitions' else (p,))]
        files={}
        for r in tables['relations']:
            if r['target_uid'] not in itemids:r['target_uid']=None
        for r in tables['attachments']:
            if r['disk_path']:
                path=Path(r['disk_path']);resolved=path.resolve()
                if path.is_symlink() or not resolved.is_relative_to(self.attachment_root):raise OperationsError('ATTACHMENT_PATH_INVALID')
                data=resolved.read_bytes()
                if _hash(data)!=r['checksum']:raise OperationsError('ATTACHMENT_CHECKSUM_MISMATCH')
                name='attachments/'+r['attachment_uid'];files[name]=data;r['disk_path']=name
        latest=[]
        for item in tables['items']:
            source=c.execute('SELECT s.latest_revision_uid,m.scope_id,m.state FROM item_collection_state s LEFT JOIN collection_memberships m ON m.project_uid=? AND m.source_item_id=? WHERE s.item_uid=?',(p,item['source_item_id'],item['item_uid'])).fetchone()
            if source is None or source['scope_id'] is None:latest.append({'item_uid':item['item_uid'],'revision_uid':None,'scope_id':None,'state':'UNAVAILABLE'})
            else:latest.append({'item_uid':item['item_uid'],'revision_uid':source['latest_revision_uid'],'scope_id':source['scope_id'],'state':source['state']})
        payload={'version':1,'hash_algorithm':HASH_ALGORITHM,'project':project,'tables':tables,'source_latest':latest,'rebuild_required':True}
        self._validate(payload,{'project.json':_json(payload).encode(),**files})
        return payload,files
    def _store(self,data,p,kind,*,c=None,manifest=None):
        ref=str(uuid.uuid4());path=self._path(ref)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        row=(ref,p,kind,_hash(data),len(data),'AVAILABLE',self.clock(),_json(manifest or {}))
        try:
            if c is not None:c.execute('INSERT INTO operation_artifacts VALUES(?,?,?,?,?,?,?,?)',row)
            else:
                with self.db.transaction() as own:own.execute('INSERT INTO operation_artifacts VALUES(?,?,?,?,?,?,?,?)',row)
        except BaseException:path.unlink(missing_ok=True);raise
        return dict(zip(('artifact_ref','project_uid','kind','sha256','size','state','created_at'),row[:7]))
    def register_package(self,project_uid,data):
        payload,_,manifest=self._decode(data)
        with self.db.connect() as c:
            if self._project(c,project_uid)!=payload['project']:raise OperationsError('PACKAGE_PROJECT_MISMATCH')
        return self._store(data,project_uid,'PACKAGE',manifest=manifest)
    def list_artifacts(self,project_uid=None):
        with self.db.connect() as c:
            rows=c.execute('SELECT artifact_ref,project_uid,kind,sha256,size,state,created_at FROM operation_artifacts'+(' WHERE project_uid=?' if project_uid else '')+' ORDER BY created_at DESC,artifact_ref', (project_uid,) if project_uid else ())
            return [dict(x) for x in rows]
    def get_artifact(self,ref):
        self._path(ref)
        with self.db.connect() as c:row=c.execute('SELECT artifact_ref,project_uid,kind,sha256,size,state,created_at FROM operation_artifacts WHERE artifact_ref=?',(ref,)).fetchone()
        if row is None:raise OperationsError('ARTIFACT_NOT_FOUND',404)
        return dict(row)
    def read_artifact(self,ref):
        meta=self.get_artifact(ref)
        try:data=self._path(ref).read_bytes()
        except OSError:raise OperationsError('ARTIFACT_UNAVAILABLE',409) from None
        if len(data)!=meta['size'] or _hash(data)!=meta['sha256']:raise OperationsError('ARTIFACT_CHECKSUM_MISMATCH')
        return data
    def _enqueue(self,p,stage,snapshot):
        with self.db.transaction() as c:
            self._project(c,p);jobid=str(uuid.uuid4());now=self.clock()
            c.execute('INSERT INTO jobs(job_id,project_uid,stage,created_at,updated_at) VALUES(?,?,?,?,?)',(jobid,p,stage,now,now));Queue._event(c,jobid,'QUEUED',now)
            c.execute('INSERT INTO operation_snapshots VALUES(?,?)',(jobid,_json(snapshot)))
            return Queue._row(c.execute('SELECT * FROM jobs WHERE job_id=?',(jobid,)).fetchone())
    def enqueue_export(self,project_uid):return self._enqueue(project_uid,'EXPORT',{})
    def enqueue_import(self,project_uid,artifact_ref,import_mode='MERGE_ONLY',expected_sha256=None):
        if import_mode!='MERGE_ONLY':raise OperationsError('IMPORT_MODE_INVALID')
        meta=self.get_artifact(artifact_ref);data=self.read_artifact(artifact_ref);payload,_,_=self._decode(data)
        if meta['kind']!='PACKAGE' or meta['state']!='AVAILABLE' or meta['project_uid']!=project_uid:raise OperationsError('PACKAGE_PROJECT_MISMATCH')
        with self.db.connect() as c:
            if self._project(c,project_uid)!=payload['project']:raise OperationsError('PACKAGE_PROJECT_MISMATCH')
        if expected_sha256 is not None and expected_sha256!=meta['sha256']:raise OperationsError('PACKAGE_CHECKSUM_MISMATCH')
        return self._enqueue(project_uid,'IMPORT',{'artifact_ref':artifact_ref,'sha256':meta['sha256']})
    def _merge(self,c,payload,entries,attachment_root,renew=lambda:None):
        for t in TABLES:
            for original in payload['tables'][t]:
                renew()
                row=dict(original);key=KEYS[t];where=' AND '.join(k+'=?' for k in key)
                existing=c.execute('SELECT * FROM '+t+' WHERE '+where,tuple(row[k] for k in key)).fetchone()
                if t=='attachments' and row['disk_path']:
                    destination=attachment_root/(row['attachment_uid']+'-'+row['checksum']);row['disk_path']=str(destination)
                if existing:
                    compare=dict(existing)
                    if t=='items':
                        compare={k:compare[k] for k in ('item_uid','project_uid','source_item_id')}
                        row={k:row[k] for k in compare}
                    if t=='item_revisions':compare['captured_at']=row['captured_at']
                    if t=='attachments':compare['disk_path']=row['disk_path']
                    if compare!=row:raise OperationsError('IMPORT_IMMUTABLE_CONFLICT')
                    continue
                columns=list(row);c.execute('INSERT INTO '+t+'('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',tuple(row[k] for k in columns))
    def _write_attachments(self,payload,entries,root):
        root.mkdir(mode=0o700,parents=True,exist_ok=True)
        for row in payload['tables']['attachments']:
            if row['disk_path']:
                path=root/(row['attachment_uid']+'-'+row['checksum'])
                if path.is_symlink():raise OperationsError('ATTACHMENT_PATH_INVALID')
                if path.exists():
                    if _hash(path.read_bytes())!=row['checksum']:raise OperationsError('ATTACHMENT_CHECKSUM_MISMATCH')
                else:
                    temporary=root/(str(uuid.uuid4())+'.part')
                    try:
                        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                        with os.fdopen(fd,'wb') as f:
                            f.write(entries['attachments/'+row['attachment_uid']]);f.flush();os.fsync(f.fileno())
                        os.replace(temporary,path)
                    finally:temporary.unlink(missing_ok=True)
    def _initialize_inputs(self,c,payload,job_id,*,honor_selection=True):
        result={'source_inputs_initialized':[],'source_inputs_kept':[],'source_inputs_unavailable':[]}
        project=payload['project']['project_uid']
        for row in payload['source_latest']:
            item=row['item_uid'];incoming=row['revision_uid']
            if incoming is None:
                result['source_inputs_unavailable'].append(item);continue
            current=c.execute('SELECT latest_revision_uid FROM item_collection_state WHERE item_uid=?',(item,)).fetchone()
            active=c.execute('SELECT active_revision_uid,source_item_id FROM items WHERE item_uid=?',(item,)).fetchone()
            incompatible=current is not None and current[0]!=incoming or current is None and active['active_revision_uid'] is not None and active['active_revision_uid']!=incoming
            if incompatible:
                result['source_inputs_kept'].append({'item_uid':item,'incoming_revision_uid':incoming,'current_revision_uid':current[0] if current else active['active_revision_uid']});continue
            if current is not None:continue
            c.execute('INSERT INTO item_collection_state VALUES(?,?,?)',(item,incoming,job_id))
            state=row['state']
            if honor_selection and not allows_scope(c,project,row['scope_id']):state='OUT_OF_SCOPE'
            c.execute('INSERT INTO collection_memberships VALUES(?,?,?,?,?) ON CONFLICT(project_uid,source_item_id) DO NOTHING',(project,active['source_item_id'],row['scope_id'],state,job_id))
            result['source_inputs_initialized'].append({'item_uid':item,'revision_uid':incoming,'state':state})
        return result
    def _renew_guard(self,c,job,abort_check):
        if abort_check():raise OperationsError('OPERATIONS_ABORTED')
        now=time.time();Queue._guard(c,job['job_id'],job['fencing_token'],now)
        span=max(.05,job['lease_expires_at']-job['updated_at'])
        c.execute('UPDATE jobs SET lease_expires_at=?,updated_at=? WHERE job_id=?',(now+span,now,job['job_id']))
    def run(self,job,abort_check):
        temporary=None;published_path=None;committed=False;snapshot={}
        try:
            # Long snapshot capture/compression uses a read transaction so the worker
            # heartbeat can retain ownership in WAL mode. No writer lock spans file I/O.
            with self.db.connect() as c:
                c.execute('BEGIN');Queue._guard(c,job['job_id'],job['fencing_token'],time.time())
                stored=c.execute('SELECT snapshot FROM operation_snapshots WHERE job_id=?',(job['job_id'],)).fetchone()
                if stored is None:raise OperationsError('OPERATIONS_SNAPSHOT_MISSING')
                snapshot=json.loads(stored[0]);checkpoint=json.loads(c.execute('SELECT checkpoint FROM jobs WHERE job_id=?',(job['job_id'],)).fetchone()[0])
                if abort_check():raise OperationsError('OPERATIONS_ABORTED')
                if job['stage']=='EXPORT' and not checkpoint.get('artifact_ref'):payload,files=self._capture(c,job['project_uid'])
                c.commit()
            if job['stage']=='EXPORT':
                if checkpoint.get('artifact_ref'):
                    meta=self.get_artifact(checkpoint['artifact_ref'])
                    if meta['project_uid']!=job['project_uid'] or meta['kind']!='PACKAGE':raise OperationsError('OPERATIONS_CHECKPOINT_INVALID')
                    self.read_artifact(meta['artifact_ref'])
                else:
                    if len(_json(payload).encode())+sum(map(len,files.values()))>self.MAX_BYTES or len(files)+2>self.MAX_ENTRIES:raise OperationsError('PACKAGE_SIZE_LIMIT')
                    data=self.encode_package(payload,files)
                    self._archive_budget(data)
                    ref=str(uuid.uuid4());temporary=self.artifact_root/(ref+'.part');published_path=self._path(ref)
                    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                    with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
                    checkpoint={'artifact_ref':ref,'rebuild_required':True}
                with self.db.transaction() as c:
                    self._renew_guard(c,job,abort_check)
                    if temporary is not None:
                        os.replace(temporary,published_path);temporary=None
                        c.execute('INSERT INTO operation_artifacts VALUES(?,?,?,?,?,?,?,?)',(ref,job['project_uid'],'PACKAGE',_hash(data),len(data),'AVAILABLE',self.clock(),'{}'))
                    c.execute('UPDATE jobs SET checkpoint=? WHERE job_id=?',(_json(checkpoint),job['job_id']))
                committed=True
            elif job['stage']=='IMPORT':
                data=self.read_artifact(snapshot['artifact_ref'])
                if _hash(data)!=snapshot['sha256']:raise OperationsError('PACKAGE_CHECKSUM_MISMATCH')
                payload,entries,_=self._decode(data)
                with self.db.connect() as c:
                    if self._project(c,job['project_uid'])!=payload['project']:raise OperationsError('PACKAGE_PROJECT_MISMATCH')
                if abort_check():raise OperationsError('OPERATIONS_ABORTED')
                self._write_attachments(payload,entries,self.attachment_root)
                with self.db.transaction() as c:
                    self._renew_guard(c,job,abort_check)
                    self._merge(c,payload,entries,self.attachment_root,renew=lambda:self._renew_guard(c,job,abort_check))
                    checkpoint={'artifact_ref':snapshot['artifact_ref'],'rebuild_required':True,**self._initialize_inputs(c,payload,job['job_id'])}
                    self._renew_guard(c,job,abort_check)
                    c.execute('UPDATE jobs SET checkpoint=? WHERE job_id=?',(_json(checkpoint),job['job_id']))
                committed=True
            else:raise OperationsError('OPERATIONS_STAGE_INVALID')
            self.queue.finish(job['job_id'],job['fencing_token'])
        except LeaseLost:raise
        except OperationsError as e:
            if e.code=='IMPORT_IMMUTABLE_CONFLICT':
                with self.db.transaction() as c:
                    self._renew_guard(c,job,abort_check);c.execute("UPDATE operation_artifacts SET state='QUARANTINED' WHERE artifact_ref=?",(snapshot['artifact_ref'],))
            self.queue.finish(job['job_id'],job['fencing_token'],'COMPLETED_WITH_ERRORS' if e.code=='IMPORT_IMMUTABLE_CONFLICT' else 'BLOCKED',e.code)
        except (OSError,sqlite3.Error,ValueError,KeyError,TypeError):self.queue.finish(job['job_id'],job['fencing_token'],'BLOCKED','OPERATIONS_INTEGRITY_ERROR')
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
            if published_path is not None and not committed:published_path.unlink(missing_ok=True)
    def create_backup(self):
        import tempfile
        from .lexical import LEXICAL_VERSION
        with self.db.connect() as c:
            c.execute('BEGIN')
            schema=[r[0] for r in c.execute('SELECT version FROM schema_migrations ORDER BY version')]
            captures=[self._capture(c,r[0]) for r in c.execute('SELECT project_uid FROM projects ORDER BY project_uid')]
            selections=[dict(r) for r in c.execute('SELECT * FROM project_selections ORDER BY project_uid')]
            generations=[dict(r) for r in c.execute('SELECT generation_uid,project_uid,state FROM index_generations ORDER BY generation_uid')]
            compatibility=[]
            for row in c.execute('SELECT generation_uid,config_fingerprint,model_profile,lexical_version,cleanup_state FROM generation_configs ORDER BY generation_uid'):
                profile=json.loads(row['model_profile'])
                compatibility.append({'generation_uid':row['generation_uid'],'config_fingerprint':row['config_fingerprint'],'model_fingerprint':profile.get('fingerprint'),'model_digest':profile.get('model_digest'),'tokenizer_id':profile.get('tokenizer_id'),'lexical_version':row['lexical_version'],'cleanup_state':row['cleanup_state'],'dense_snapshot_included':False})
            c.commit()
        files={}
        with tempfile.TemporaryDirectory(prefix='.backup-',dir=self.artifact_root) as temp:
            fresh=Database(Path(temp)/'recovery.sqlite');fresh.migrate()
            with fresh.transaction() as c:
                for payload,attachments in captures:
                    p=payload['project']
                    c.execute("INSERT OR IGNORE INTO instances(instance_uid,source_type,base_url,display_name,auth_ref) VALUES(?,?,?,?,'RECOVERY_REGISTRATION_REQUIRED')",(p['instance_uid'],p['source_type'],'https://recovery-'+p['instance_uid']+'.invalid','Recovery registration required'))
                    c.execute('INSERT INTO projects(project_uid,instance_uid,source_project_id,name) VALUES(?,?,?,?)',(p['project_uid'],p['instance_uid'],p['source_project_id'],'Recovered project'))
                    self._merge(c,payload,attachments,Path('attachments'))
                    job_id=str(uuid.uuid4());now=self.clock()
                    c.execute("INSERT INTO jobs(job_id,project_uid,stage,state,created_at,updated_at) VALUES(?,?,'RECOVERED','SUCCEEDED',?,?)",(job_id,p['project_uid'],now,now))
                    self._initialize_inputs(c,payload,job_id,honor_selection=False)
                    for selection in selections:
                        if selection['project_uid']==p['project_uid']:
                            c.execute('INSERT INTO project_selections VALUES(?,?,?,?,?,?,?)',(selection['project_uid'],selection['selection_mode'],selection['scope_kind'],selection['scope_ids'],selection['config_revision'],None,selection['scope_snapshot_hash']))
                    for row in payload['tables']['attachments']:
                        if row['disk_path']:files['attachments/'+row['attachment_uid']+'-'+row['checksum']]=attachments[row['disk_path']]
            with fresh.connect() as c:c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            files['database.sqlite']=fresh.path.read_bytes()
        manifest={'format':'ALMRAG_RAW_BACKUP','version':1,'app_version':_app_version(),'state':'RAW_ONLY_REBUILD_REQUIRED','schema_versions':schema,'lexical_version':LEXICAL_VERSION,'generations':generations,'generation_compatibility':compatibility,'auth_state':'REREGISTRATION_REQUIRED','entries':{k:{'sha256':_hash(v),'size':len(v)} for k,v in files.items()}}
        if len(files)+1>self.MAX_ENTRIES or sum(map(len,files.values()))+len(_json(manifest).encode())>self.MAX_BYTES:raise OperationsError('BACKUP_SIZE_LIMIT')
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('manifest.json',_json(manifest))
            for k,v in files.items():z.writestr(k,v)
        self._archive_budget(stream.getvalue(),'BACKUP')
        return self._store(stream.getvalue(),None,'BACKUP',manifest=manifest)
    def list_backups(self):return [r for r in self.list_artifacts() if r['kind']=='BACKUP']
    def _backup(self,ref):
        meta=self.get_artifact(ref)
        if meta['kind']!='BACKUP' or meta['state']!='AVAILABLE':raise OperationsError('BACKUP_NOT_AVAILABLE')
        try:
            with zipfile.ZipFile(io.BytesIO(self.read_artifact(ref))) as z:
                infos=z.infolist();names=[x.filename for x in infos]
                if len(names)!=len(set(names)) or len(names)>self.MAX_ENTRIES or sum(x.file_size for x in infos)>self.MAX_BYTES:raise OperationsError('BACKUP_SIZE_LIMIT')
                for x in infos:
                    p=PurePosixPath(x.filename)
                    if p.is_absolute() or '..' in p.parts or '\\' in x.filename or x.is_dir() or stat.S_ISLNK(x.external_attr>>16) or x.flag_bits&1:raise OperationsError('BACKUP_PATH_INVALID')
                files={x.filename:z.read(x) for x in infos};manifest=json.loads(files.pop('manifest.json'))
            if manifest['format']!='ALMRAG_RAW_BACKUP' or manifest['version']!=1 or manifest['state']!='RAW_ONLY_REBUILD_REQUIRED' or set(files)!=set(manifest['entries']) or 'database.sqlite' not in files:raise OperationsError('BACKUP_MANIFEST_INVALID')
            import re
            app=manifest.get('app_version')
            if not isinstance(app,str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[a-zA-Z0-9.+-]*)',app) or app.split('.')[0]!=_app_version().split('.')[0]:raise OperationsError('BACKUP_APP_VERSION_UNSUPPORTED')
            for name,data in files.items():
                if name!='database.sqlite' and not name.startswith('attachments/'):raise OperationsError('BACKUP_PATH_INVALID')
                if manifest['entries'][name]!={'sha256':_hash(data),'size':len(data)}:raise OperationsError('BACKUP_CHECKSUM_MISMATCH')
            return manifest,files
        except OperationsError:raise
        except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile):raise OperationsError('BACKUP_INVALID') from None
    def prepare_restore(self,backup,actor):
        if not actor:raise OperationsError('RESTORE_ACTOR_REQUIRED')
        manifest,_=self._backup(backup);digest=_hash(_json(manifest).encode());nonce=str(uuid.uuid4())
        with self.db.transaction() as c:c.execute('INSERT INTO operation_nonces VALUES(?,?,?,?,?,0)',(_hash(nonce.encode()),backup,digest,actor,self.clock()+300))
        return {'manifest_hash':digest,'confirmation_nonce':nonce,'expires_at':self.clock()+300,'state':'RAW_ONLY_REBUILD_REQUIRED'}
    def restore(self,backup,manifest_hash,confirmation_nonce,actor):
        manifest,files=self._backup(backup)
        if _hash(_json(manifest).encode())!=manifest_hash:raise OperationsError('RESTORE_MANIFEST_MISMATCH')
        with self.db.transaction() as c:
            row=c.execute('SELECT * FROM operation_nonces WHERE nonce_hash=?',(_hash(confirmation_nonce.encode()),)).fetchone()
            if row is None or row['artifact_ref']!=backup or row['manifest_hash']!=manifest_hash or row['actor']!=actor or row['used'] or row['expires_at']<=self.clock():raise OperationsError('RESTORE_CONFIRMATION_INVALID',409)
            c.execute('UPDATE operation_nonces SET used=1 WHERE nonce_hash=?',(row['nonce_hash'],))
        ref=str(uuid.uuid4());root=self.recovery_root/ref;root.mkdir(mode=0o700,parents=True)
        for name,data in files.items():
            dest=root/name;dest.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(data)
        recovered=Database(root/'database.sqlite')
        with recovered.transaction() as c:
            if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or c.execute('PRAGMA foreign_key_check').fetchone():raise OperationsError('RESTORE_DATABASE_INVALID')
            for r in c.execute('SELECT attachment_uid,disk_path,checksum FROM attachments WHERE disk_path IS NOT NULL').fetchall():
                path=root/'attachments'/(r['attachment_uid']+'-'+r['checksum'])
                if not path.is_file() or _hash(path.read_bytes())!=r['checksum']:raise OperationsError('RESTORE_ATTACHMENT_INVALID')
                c.execute('UPDATE attachments SET disk_path=? WHERE attachment_uid=?',(str(path),r['attachment_uid']))
        # API deliberately exposes only opaque recovery identity; no promotion to the live DB.
        (root/'database.sqlite').rename(root/'recovery.sqlite')
        return {'recovery_ref':ref,'state':'RAW_ONLY_REBUILD_REQUIRED','auth_state':'REREGISTRATION_REQUIRED'}
    def configure_backup_schedule(self,interval_seconds,retention):
        if type(interval_seconds) is not int or interval_seconds<10 or type(retention) is not int or not 1<=retention<=1000:raise OperationsError('BACKUP_SCHEDULE_INVALID')
        with self.db.transaction() as c:c.execute('INSERT INTO operation_backup_schedule VALUES(1,?,?,?) ON CONFLICT(singleton) DO UPDATE SET interval_seconds=excluded.interval_seconds,retention=excluded.retention,next_due=excluded.next_due',(interval_seconds,retention,self.clock()+interval_seconds))
        return {'interval_seconds':interval_seconds,'retention':retention}
    def maintenance(self):
        with self.db.transaction() as c:
            row=c.execute('SELECT * FROM operation_backup_schedule WHERE singleton=1').fetchone()
            if row is None or row['next_due']>self.clock():return {'created':False}
            c.execute('UPDATE operation_backup_schedule SET next_due=? WHERE singleton=1',(self.clock()+row['interval_seconds'],))
        meta=self.create_backup()
        # Only registered backups owned by this service are subject to configured retention.
        for old in self.list_backups()[row['retention']:]:
            with self.db.transaction() as c:
                if c.execute('SELECT 1 FROM operation_nonces WHERE artifact_ref=? AND used=0 AND expires_at>?',(old['artifact_ref'],self.clock())).fetchone():continue
                c.execute('DELETE FROM operation_nonces WHERE artifact_ref=?',(old['artifact_ref'],));c.execute('DELETE FROM operation_artifacts WHERE artifact_ref=?',(old['artifact_ref'],))
            self._path(old['artifact_ref']).unlink(missing_ok=True)
        return {'created':True,'artifact_ref':meta['artifact_ref']}
