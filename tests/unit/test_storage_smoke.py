"""Smoke test: FileStore / RelationalStore 基本 round-trip。"""
from __future__ import annotations

from shared.models import BKTParamRow, User
from shared.storage import FileStore, RelationalStore


def test_filestore_round_trip(tmp_filestore: FileStore) -> None:
    p = tmp_filestore.write_text("a", "b.txt", content="hello")
    assert p.exists()
    assert tmp_filestore.read_text("a", "b.txt") == "hello"
    assert tmp_filestore.exists("a", "b.txt")


def test_relational_store_create_and_query(tmp_db: RelationalStore) -> None:
    with tmp_db.session() as s:
        s.add(User(id="yhn", display_name="Test"))
        s.commit()

    with tmp_db.session() as s:
        u = s.get(User, "yhn")
        assert u is not None
        assert u.display_name == "Test"


def test_bkt_param_composite_pk(tmp_db: RelationalStore) -> None:
    with tmp_db.session() as s:
        s.add(User(id="u1"))
        s.add(BKTParamRow(user_id="u1", concept_id="x:1.1:a", p_mastery=0.5))
        s.add(BKTParamRow(user_id="u1", concept_id="x:1.1:b", p_mastery=0.7))
        s.commit()

    with tmp_db.session() as s:
        row = s.get(BKTParamRow, ("u1", "x:1.1:a"))
        assert row is not None
        assert row.p_mastery == 0.5
