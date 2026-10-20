"""SRS-002/023 identity and publication invariants."""
import sqlite3
import pytest
from almrag.storage import Database, canonical_uid
@pytest.fixture
def db(tmp_path):
    d=Database(tmp_path/'db'); d.migrate(); return d
def project(d,n='1'):
    return d.add_project(d.add_instance('codebeamer','https://example.invalid','name','ref'),n,'same')
def test_identity(db):
    assert canonical_uid('a:b','c') != canonical_uid('a','b:c')
    assert project(db)==project(db)
    assert project(db)!=project(db,'2')
    db.migrate()
    with db.connect() as c:
        assert c.execute('PRAGMA foreign_keys').fetchone()[0]==1
        assert c.execute('PRAGMA journal_mode').fetchone()[0]=='wal'
def test_revision(db):
    p=project(db)
    with db.transaction() as c:
        for i in ['i','j']: c.execute('INSERT INTO items(item_uid,project_uid,source_item_id) VALUES(?,?,?)',(i,p,i))
        c.execute("INSERT INTO item_revisions(revision_uid,item_uid,source_revision,raw_payload,hash) VALUES('r','i','1','{}','hash')")
        c.execute("UPDATE items SET active_revision_uid='r' WHERE item_uid='i'")
    for sql in ["UPDATE items SET active_revision_uid='r' WHERE item_uid='j'","UPDATE item_revisions SET raw_payload='bad'","DELETE FROM item_revisions"]:
        with pytest.raises(sqlite3.IntegrityError), db.transaction() as c: c.execute(sql)
def test_generation(db):
    p=project(db); p2=project(db,'2')
    with db.transaction() as c: c.execute("INSERT INTO index_generations(generation_uid,project_uid,model_config) VALUES('g',?,'{}')",(p,))
    with pytest.raises(sqlite3.IntegrityError),db.transaction() as c: c.execute("UPDATE projects SET active_generation_uid='g' WHERE project_uid=?",(p,))
    with db.transaction() as c:
        c.execute("UPDATE index_generations SET state='VALIDATED',validation_evidence='test' WHERE generation_uid='g'")
        c.execute("UPDATE projects SET active_generation_uid='g' WHERE project_uid=?",(p,))
    with pytest.raises(sqlite3.IntegrityError),db.transaction() as c: c.execute("UPDATE projects SET active_generation_uid='g' WHERE project_uid=?",(p2,))
    with pytest.raises(sqlite3.IntegrityError),db.transaction() as c: c.execute("UPDATE index_generations SET state='PREPARED'")

def test_validated_generation_requires_evidence(db):
    p=project(db)
    with pytest.raises(sqlite3.IntegrityError),db.transaction() as c:
        c.execute("INSERT INTO index_generations(generation_uid,project_uid,model_config,state) VALUES('g',?,'{}','VALIDATED')",(p,))

def test_transaction_rolls_back(db):
    with pytest.raises(RuntimeError),db.transaction() as c:
        c.execute("INSERT INTO instances VALUES('x','polarion','https://invalid','x','r',NULL,NULL,0,NULL)")
        raise RuntimeError('synthetic')
    with db.connect() as c: assert c.execute("SELECT 1 FROM instances WHERE instance_uid='x'").fetchone() is None

def test_chunk_uniqueness_and_token_bound(db):
    p=project(db)
    with db.transaction() as c:
        c.execute("INSERT INTO items(item_uid,project_uid,source_item_id) VALUES('i',?,'1')",(p,))
        c.execute("INSERT INTO item_revisions(revision_uid,item_uid,source_revision,raw_payload,hash) VALUES('r','i','1','full original','h')")
        sql="INSERT INTO chunks(chunk_uid,revision_uid,chunk_key,input_text,content_hash,model_fingerprint,input_tokens,embedding_input_digest,tokenizer_id,effective_max_input_tokens) VALUES(?,'r','key','text','hash','fingerprint',?,'digest','tokenizer',10)"
        c.execute(sql,('c',5))
    for uid,tokens in [('duplicate',5),('oversize',11)]:
        with pytest.raises(sqlite3.IntegrityError),db.transaction() as c: c.execute(sql,(uid,tokens))

def test_revision_replace_cannot_mutate_source(db):
    p=project(db)
    with db.transaction() as c:
        c.execute("INSERT INTO items(item_uid,project_uid,source_item_id) VALUES('i',?,'1')",(p,))
        c.execute("INSERT INTO item_revisions(revision_uid,item_uid,source_revision,raw_payload,hash) VALUES('r','i','1','original','h')")
    with pytest.raises(sqlite3.IntegrityError),db.transaction() as c:
        c.execute("INSERT OR REPLACE INTO item_revisions(revision_uid,item_uid,source_revision,raw_payload,hash) VALUES('r','i','1','changed','h')")


def test_migration_creates_private_parent(tmp_path):
    d=Database(tmp_path/'nested'/'alm.sqlite')
    d.migrate()
    assert d.path.exists()


def test_instance_uid_is_not_derived_from_mutable_url(db):
    instance=db.add_instance('codebeamer','https://old.example.invalid','name','ref')
    assert instance!=canonical_uid('instance','codebeamer','https://old.example.invalid')
    p=db.add_project(instance,'42','project')
    with db.transaction() as c:
        c.execute('UPDATE instances SET base_url=? WHERE instance_uid=?',('https://new.example.invalid',instance))
    assert db.add_project(instance,'42','renamed')==p


def test_failed_item_cannot_reference_other_project(db):
    from almrag.queue import Queue
    p1=project(db,'1');p2=project(db,'2')
    job=Queue(db).enqueue(p1,'COLLECT')
    with db.transaction() as c:
        c.execute("INSERT INTO items(item_uid,project_uid,source_item_id) VALUES('foreign',?,'1')",(p2,))
        c.execute("INSERT INTO item_revisions(revision_uid,item_uid,source_revision,raw_payload,hash) VALUES('foreign-rev','foreign','1','{}','h')")
    with pytest.raises(sqlite3.IntegrityError),db.transaction() as c:
        c.execute("INSERT INTO failed_items(failed_item_uid,job_id,project_uid,item_uid,revision_uid,failed_stage,error_class,retryable) VALUES('failure',?,?,'foreign','foreign-rev','COLLECT','PARSE',1)",(job['job_id'],p1))
