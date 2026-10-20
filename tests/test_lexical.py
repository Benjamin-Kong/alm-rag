"""SRS-018/019 scoped keyword channel, using synthetic fixtures only."""
import sqlite3
import pytest
from almrag.lexical import LexicalIndex, LexicalError, LEXICAL_VERSION, terms
from almrag.storage import Database

@pytest.fixture
def db(tmp_path):
    db=Database(tmp_path/'keyword.sqlite')
    with db.transaction() as c:
        c.execute('CREATE TABLE items(item_uid TEXT PRIMARY KEY,project_uid TEXT,source_item_id TEXT)')
        c.execute('CREATE TABLE keyword_documents(point_uuid TEXT PRIMARY KEY,project_uid TEXT,generation_uid TEXT,item_uid TEXT,revision_uid TEXT,chunk_uid TEXT,terms TEXT)')
        c.execute("CREATE VIRTUAL TABLE keyword_fts USING fts5(point_uuid UNINDEXED,project_uid UNINDEXED,generation_uid UNINDEXED,terms,tokenize='unicode61')")
    return db

def point(uid,text,project='p',generation='g'):
    return {'id':uid,'input_text':text,'payload':dict(project_uid=project,generation_uid=generation,item_uid='i'+uid,revision_uid='r'+uid,chunk_uid='c'+uid,secret='never returned')}

def put(db,*points):
    with db.transaction() as c:
        for p in points:
            c.execute('INSERT OR IGNORE INTO items VALUES(?,?,?)',(p['payload']['item_uid'],p['payload']['project_uid'],'source-'+p['id']))
            LexicalIndex(db).put(c,p)

def test_nfkc_automotive_and_korean_terms():
    value=terms('ＳＯＭＥ/IP-SD 30490 0xAB12 차량속도감지')
    assert {'some/ip-sd','some','ip','sd','30490','0xab12','차량속도감지','차량','속도','감지','차량속'} <= set(value)
    assert LEXICAL_VERSION
    assert len(value)==len(set(value))

def test_scoped_before_limit_and_stable_pagination(db):
    put(db,point('a','차량 SOME/IP-SD'),point('b','차량 SOME/IP-SD'),point('foreign','차량 SOME/IP-SD','other'),point('old','차량 SOME/IP-SD',generation='old'))
    index=LexicalIndex(db)
    assert [r['id'] for r in index.search('p','g','차량',1)]==['a']
    result=index.search('p','g','차량',1,1)
    assert result[0]['id']=='b'
    assert set(result[0]['payload'])=={'project_uid','generation_uid','item_uid','revision_uid','chunk_uid'}
    assert isinstance(result[0]['score'],float)

def test_atomic_idempotent_replace(db):
    index=LexicalIndex(db); put(db,point('a','oldword'))
    put(db,point('a','newword'),point('a','newword'))
    assert not index.search('p','g','oldword',5)
    assert len(index.search('p','g','newword',5))==1
    with pytest.raises(RuntimeError),db.transaction() as c:
        index.put(c,point('a','rollbackword'))
        raise RuntimeError('rollback')
    assert index.search('p','g','newword',5)
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM keyword_fts').fetchone()[0]==1

def test_safe_query_syntax_and_empty(db):
    index=LexicalIndex(db); put(db,point('a','safety brake'))
    assert index.search('p','g','" OR * NOT ( ) : safety',5)[0]['id']=='a'
    assert index.search('p','g','" * : ( )',5)==[]
    assert index.search('p','g','',5)==[]
    assert index.search("p' OR 1=1 --",'g','safety',5)==[]

@pytest.mark.parametrize('query,limit,offset',[(' '.join('word'+str(i) for i in range(1025)),1,0),('x',0,0),('x',1001,0),('x',1,-1),('x',True,0),('x',1,True)])
def test_explicit_complexity_or_page_rejection(db,query,limit,offset):
    with pytest.raises(LexicalError): LexicalIndex(db).search('p','g',query,limit,offset)

def test_caller_snapshot_and_delete_generation(db):
    index=LexicalIndex(db); put(db,point('a','brake'),point('b','brake',generation='other'))
    with db.transaction() as c:
        index.delete_generation(c,'g')
        assert not index.search('p','g','brake',2,c=c)
    assert index.search('p','other','brake',2)
    with db.connect() as c: assert c.execute('SELECT count(*) FROM keyword_fts').fetchone()[0]==1

def test_synthetic_comparison_with_bare_unicode61(db):
    put(db,point('a','차량속도감지 SOME/IP-SD 30490 0xAB12'))
    with db.transaction() as c:
        c.execute("CREATE VIRTUAL TABLE bare USING fts5(body,tokenize='unicode61')")
        c.execute('INSERT INTO bare VALUES(?)',('차량속도감지 SOME/IP-SD 30490 0xAB12',))
        assert c.execute('SELECT count(*) FROM bare WHERE bare MATCH ?',('속도',)).fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM bare WHERE bare MATCH ?',('30490',)).fetchone()[0]==1
    assert LexicalIndex(db).search('p','g','속도',2)[0]['id']=='a'
    for query in ['SOME/IP-SD','30490','0xab12']:
        assert LexicalIndex(db).search('p','g',query,2)[0]['id']=='a'

def test_put_requires_caller_transaction(db):
    with db.connect() as c,pytest.raises(LexicalError): LexicalIndex(db).put(c,point('a','text'))

def test_failed_replace_is_atomic_even_when_caller_catches(db):
    index=LexicalIndex(db); put(db,point('a','original'))
    with db.transaction() as c:
        c.execute("CREATE TRIGGER reject_new BEFORE INSERT ON keyword_documents WHEN NEW.terms!='' BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with pytest.raises(sqlite3.IntegrityError): index.put(c,point('a','replacement'))
        assert index.search('p','g','original',5,c=c)[0]['id']=='a'
    assert index.search('p','g','original',5)

def test_bm25_prefers_shorter_exact_match_and_nfkc_identifiers(db):
    put(db,point('a','brake extra unrelated words'),point('z','brake'),point('identifier','ＳＯＭＥ/IP-SD ０ｘＡＢ１２'))
    result=LexicalIndex(db).search('p','g','brake',5)
    assert [row['id'] for row in result]==['z','a']
    assert result[0]['score']>result[1]['score']
    assert LexicalIndex(db).search('p','g','some/ip-sd',5)[0]['id']=='identifier'
    assert LexicalIndex(db).search('p','g','0xab12',5)[0]['id']=='identifier'

def test_maximum_query_terms_are_accepted_without_truncation(db):
    put(db,point('last','word1023'))
    query=' '.join('word'+str(i) for i in range(1024))
    assert LexicalIndex(db).search('p','g',query,1)[0]['id']=='last'


def test_item_allowlist_is_applied_before_limit(db):
    put(db,point('a','brake'),point('z','brake'))
    index=LexicalIndex(db)
    assert [row['id'] for row in index.search('p','g','brake',1,item_uids=['iz'])]==['z']
    assert index.search('p','g','brake',1,item_uids=[])==[]
