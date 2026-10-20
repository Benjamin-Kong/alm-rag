"""SRS-024/023/019: generation snapshot pins outlive TTL and process publication."""
from uuid import uuid4
import pytest
from almrag.readers import ReaderRegistry
from almrag.storage import Database


@pytest.fixture
def env(tmp_path):
    db=Database(tmp_path/'db');db.migrate();i=db.add_instance('codebeamer','https://fixture.invalid','f','env:F');p=db.add_project(i,'p','P')
    old,new=str(uuid4()),str(uuid4())
    with db.transaction() as c:
        for g in [old,new]:c.execute("INSERT INTO index_generations VALUES(?,?,?,'VALIDATED','synthetic',NULL)",(g,p,'{}'))
        c.execute('UPDATE projects SET active_generation_uid=? WHERE project_uid=?',(old,p))
    return db,p,old,new,ReaderRegistry(db)


def test_reader_keeps_single_snapshot_and_live_pin_despite_old_timestamp(env):
    db,p,old,new,r=env
    with r.snapshot([p]) as (c,pairs):
        assert pairs=={p:old}
        with db.transaction() as writer:
            writer.execute('UPDATE projects SET active_generation_uid=? WHERE project_uid=?',(new,p))
            writer.execute('UPDATE search_reader_pins SET created_at=0')
            assert r.has_readers(writer,old)
        assert c.execute('SELECT active_generation_uid FROM projects WHERE project_uid=?',(p,)).fetchone()[0]==old
    with db.transaction() as c:assert not r.has_readers(c,old)


def test_abandoned_pin_is_reaped_only_when_os_lock_is_free(env):
    db,p,old,new,r=env
    with db.transaction() as c:
        c.execute('INSERT INTO search_reader_pins VALUES(?,?,?,0)',(str(uuid4()),p,old))
        assert not r.has_readers(c,old)
        assert c.execute('SELECT count(*) FROM search_reader_pins').fetchone()[0]==0


def test_generation_switch_between_registration_and_read_snapshot_retries(env):
    db,p,old,new,r=env;calls=[]
    def switch():
        calls.append(True)
        if len(calls)==1:
            with db.transaction() as c:c.execute('UPDATE projects SET active_generation_uid=? WHERE project_uid=?',(new,p))
    with r.snapshot([p],on_pinned=switch) as (c,pairs):
        assert pairs=={p:new} and len(calls)==2
        with db.connect() as check:
            assert [row[0] for row in check.execute('SELECT generation_uid FROM search_reader_pins')]==[new]
    with db.connect() as c:assert c.execute('SELECT count(*) FROM search_reader_pins').fetchone()[0]==0


def test_unknown_project_never_silently_disappears(env):
    db,p,old,new,r=env
    with pytest.raises(ValueError,match='PROJECT_NOT_FOUND'):
        with r.snapshot([p,'foreign']):pytest.fail('must reject unknown project')


def _pin_in_child(path,project,ready):
    import time
    with ReaderRegistry(Database(path)).snapshot([project]):
        ready.set()
        time.sleep(30)


def test_process_death_releases_os_pin_and_cleanup_can_progress(env):
    import multiprocessing
    db,p,old,new,r=env
    context=multiprocessing.get_context('spawn');ready=context.Event()
    child=context.Process(target=_pin_in_child,args=(str(db.path),p,ready));child.start()
    try:
        assert ready.wait(10)
        with db.transaction() as c:assert r.has_readers(c,old)
        child.kill();child.join(10)
        assert not child.is_alive()
        with db.transaction() as c:
            assert not r.has_readers(c,old)
            assert c.execute('SELECT count(*) FROM search_reader_pins').fetchone()[0]==0
    finally:
        if child.is_alive():child.kill();child.join(10)
