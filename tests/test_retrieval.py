"""SRS-018/019/020/021/022/024/049: scoped ranks and one active SQLite view."""
import copy,json
from uuid import uuid4
import pytest
from almrag.embedding import fingerprint
from almrag.lexical import LexicalIndex,LEXICAL_VERSION
from almrag.retrieval import SearchService,SearchRequest,SearchError
from almrag.storage import canonical_uid
from test_processing import setup,add_item,execute,reprofile


class Dense:
    def __init__(self):self.points={};self.calls=[];self.hook=None
    def query(self,collection,vector,*,project_uid,generation_uid,limit,offset=0,item_uids=None):
        self.calls.append((project_uid,generation_uid,limit,offset))
        if self.hook:self.hook()
        result=[{'id':p['id'],'payload':p['payload'],'score':1.0} for p in self.points.values() if p['payload']['project_uid']==project_uid and p['payload']['generation_uid']==generation_uid and (item_uids is None or p['payload']['item_uid'] in item_uids)]
        return sorted(result,key=lambda p:p['id'])[offset:offset+limit]


def publish(setup,store,generation=None):
    db,_,project,runtime,processing=setup
    generation=generation or str(uuid4());lexical=LexicalIndex(db)
    with db.transaction() as c:
        c.execute("INSERT INTO index_generations VALUES(?,?,?,'VALIDATED','synthetic',NULL)",(generation,project,json.dumps(runtime.profile)))
        c.execute('INSERT INTO generation_configs VALUES(?,?,?,?,?,?,?,?)',(generation,'synthetic',json.dumps(runtime.profile),'{}',LEXICAL_VERSION,'almrag_'+generation.replace('-',''),'ACTIVE','[]'))
        for row in c.execute('SELECT * FROM processing_results WHERE project_uid=?',(project,)).fetchall():
            points=[]
            for chunk in c.execute('SELECT c.* FROM chunks c JOIN processing_membership m USING(chunk_uid) WHERE result_uid=?',(row['result_uid'],)).fetchall():
                pid=canonical_uid('point',generation,chunk['chunk_uid'])
                payload=dict(project_uid=project,generation_uid=generation,item_uid=row['item_uid'],revision_uid=row['revision_uid'],chunk_uid=chunk['chunk_uid'],result_uid=row['result_uid'],content_hash=chunk['content_hash'],model_fingerprint=chunk['model_fingerprint'],vector_digest=fingerprint([1.0,0.0]))
                point={'id':pid,'vector':[1.0,0.0],'payload':payload}
                c.execute('INSERT INTO index_points VALUES(?,?,?,?,?)',(pid,generation,chunk['chunk_uid'],'READY',chunk['content_hash']))
                lexical.put(c,{**point,'input_text':chunk['input_text']});store.points[pid]=point;points.append(point)
            c.execute('INSERT INTO index_publications VALUES(?,?,?,?,?,?,?,?)',(generation,row['item_uid'],row['result_uid'],row['revision_uid'],fingerprint(points),len(points),json.dumps(points),'synthetic'))
            c.execute('UPDATE items SET active_revision_uid=? WHERE item_uid=?',(row['revision_uid'],row['item_uid']))
        c.execute('UPDATE projects SET active_generation_uid=? WHERE project_uid=?',(generation,project))
    return generation


def service(setup,**options):
    db,_,p,r,_=setup;dense=Dense()
    return SearchService(db,lambda _:r,dense,allow_fixture=True,**options),dense


def test_explicit_scope_denial_happens_before_any_backend_or_model_call(setup):
    db,_,p,r,_=setup;s,d=service(setup)
    with pytest.raises(SearchError,match='FORBIDDEN'):s.search(SearchRequest(query='secret',project_uids=[p]),allowed_projects=[])
    assert not d.calls and not r.calls
    for invalid in [[],[p,p]]:
        with pytest.raises(ValueError):SearchRequest(query='x',project_uids=invalid)


def test_hybrid_unique_items_compact_full_and_raw_source_restoration(setup):
    db,_,p,r,_=setup
    revision=add_item(setup,description='word '*3000,fields=[{'source_field_id':'private','raw_value':'complete not embedded'}])
    execute(setup);execute(setup,'EMBED');s,d=service(setup);publish(setup,d)
    compact=s.search(SearchRequest(query='word',project_uids=[p],top_k=10),allowed_projects=[p])
    assert compact['total']==1 and len(compact['results'])==1
    hit=compact['results'][0]
    assert hit['revision_uid']==revision and 'item' not in hit
    assert all('input_text' not in chunk for chunk in hit['matched_chunks'])
    full=s.search(SearchRequest(query='word',project_uids=[p],response={'include_full_item':True,'include_chunk_text':True,'include_scores':False}),allowed_projects=[p])
    hit=full['results'][0]
    assert hit['item']['description']['raw']=='word '*3000
    assert hit['item']['fields'][0]['raw_value']=='complete not embedded'
    assert 'score' not in hit and all('input_text' in chunk for chunk in hit['matched_chunks'])
    detail=s.item_detail(p,hit['item_uid'],allowed_projects=[p])
    assert detail['revision_uid']==revision and detail['item']==hit['item']


def test_different_project_generation_pairs_and_model_binding(setup):
    db,i,p,r,processing=setup;s,d=service(setup)
    add_item(setup);execute(setup);execute(setup,'EMBED');g1=publish(setup,d)
    p2=db.add_project(i,'other','Other');second=(db,i,p2,r,processing)
    add_item(second);execute(second);execute(second,'EMBED');g2=publish(second,d)
    result=s.search(SearchRequest(query='Title',project_uids=[p,p2],top_k=2),allowed_projects=[p,p2])
    assert {hit['project_uid'] for hit in result['results']}=={p,p2}
    assert {(call[0],call[1]) for call in d.calls}=={(p,g1),(p2,g2)}
    reprofile(r,expected_digest='sha256:'+'b'*64)
    with pytest.raises(SearchError,match='MODEL_RUNTIME_MISMATCH'):s.search(SearchRequest(query='word',project_uids=[p]),allowed_projects=[p])


def test_staged_and_wrong_revision_points_never_hide_unique_items_on_backfill(setup):
    db,_,p,r,_=setup
    add_item(setup,title='One');add_item(setup,item='2',title='Two');execute(setup);execute(setup,'EMBED')
    s,d=service(setup,page_size=2,max_rounds=6);publish(setup,d)
    first=next(iter(d.points.values()))
    for number in range(4):
        fake=copy.deepcopy(first);fake['id']='00000000-0000-0000-0000-'+str(number).zfill(12)
        d.points[fake['id']]=fake  # Foreign ID has no READY SQLite point; cannot be accepted.
    result=s.search(SearchRequest(query='no lexical match',project_uids=[p],top_k=2),allowed_projects=[p])
    assert len(result['results'])==2 and len({hit['item_uid'] for hit in result['results']})==2
    assert any(call[3]>0 for call in d.calls)


def test_read_snapshot_never_mixes_new_revision_during_foreign_query(setup):
    db,_,p,r,_=setup;old=add_item(setup,title='OLD');execute(setup);execute(setup,'EMBED')
    s,d=service(setup);publish(setup,d)
    new=add_item(setup,revision='2',title='NEW')
    def switch():
        d.hook=None
        with db.transaction() as c:c.execute('UPDATE items SET active_revision_uid=? WHERE project_uid=?',(new,p))
    d.hook=switch
    response=s.search(SearchRequest(query='OLD',project_uids=[p],response={'include_full_item':True}),allowed_projects=[p])
    assert len(response['results'])==1
    assert response['results'][0]['revision_uid']==old and response['results'][0]['item']['title']=='OLD'
    assert s.search(SearchRequest(query='OLD',project_uids=[p]),allowed_projects=[p])['results']==[]


def test_deleted_and_unauthorized_items_excluded_without_source_deletion(setup):
    db,_,p,r,_=setup;add_item(setup);execute(setup);execute(setup,'EMBED');s,d=service(setup);publish(setup,d)
    with db.transaction() as c:c.execute("UPDATE collection_memberships SET state='UNAUTHORIZED'")
    assert not s.search(SearchRequest(query='Title',project_uids=[p]),allowed_projects=[p])['results']
    with db.transaction() as c:c.execute("UPDATE collection_memberships SET state='MISSING'")
    assert s.search(SearchRequest(query='Title',project_uids=[p]),allowed_projects=[p])['total']==1
    with db.transaction() as c:c.execute("UPDATE items SET deleted_state='deleted'")
    assert not s.search(SearchRequest(query='Title',project_uids=[p]),allowed_projects=[p])['results']
    with db.connect() as c:assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==1


def test_current_selection_filters_search_and_detail_before_next_collection(setup):
    db,_,p,r,_=setup;add_item(setup);execute(setup);execute(setup,'EMBED');s,d=service(setup);publish(setup,d)
    item=next(iter(d.points.values()))['payload']['item_uid']
    with db.transaction() as c:c.execute("UPDATE project_selections SET selection_mode='SELECTED',scope_ids='[\"t2\"]' WHERE project_uid=?",(p,))
    assert s.search(SearchRequest(query='Title',project_uids=[p]),allowed_projects=[p])['results']==[]
    with pytest.raises(SearchError,match='NOT_FOUND'):s.item_detail(p,item,allowed_projects=[p])
