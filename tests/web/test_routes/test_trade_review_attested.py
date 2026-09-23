"""Arc 22-B Task 7 -- N4 (R0.D): the review form for an ATTESTED trade.

The form renders the attested value READ-ONLY (no `<select name="entry_intent">`),
so the field is absent from the POST and the presence gate preserves it. A
handcrafted POST carrying `entry_intent=""` gets the typed refusal as a 4xx
fragment BEFORE the review commits (R2-02): the review fields and `state` are
byte-unchanged, read on a fresh connection. The attested trade is made by the
real writer on trade 20's live row shape.
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

from fastapi.testclient import TestClient

from swing.config import load
from swing.data.db import ensure_schema
from swing.data.models import UNINTENDED_EXECUTION, attested_message
from tests._22b_fixtures import attest_trade20

REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEW = {"entry_grade": "A", "management_grade": "A", "exit_grade": "A",
          "lesson_learned": "clean", "mistake_tags": ["none_observed"]}
COLUMNS = ("state", "reviewed_at", "entry_grade", "management_grade",
           "exit_grade", "process_grade", "lesson_learned", "mistake_tags",
           "entry_intent")


def _app(tmp_path: Path):
    from swing.web.app import create_app

    db = tmp_path / "attested.db"
    ensure_schema(db).close()
    att_id = attest_trade20(db)
    base = load(REPO_ROOT / "swing.config.toml")
    cfg = dc_replace(base, paths=dc_replace(base.paths, db_path=db))
    return create_app(cfg), db, att_id


def _row(db: Path) -> tuple:
    c = sqlite3.connect(db)
    try:
        return c.execute(f"SELECT {', '.join(COLUMNS)} FROM trades WHERE id = 20"
                         ).fetchone()
    finally:
        c.close()


def test_review_post_without_the_field_preserves_b22_120(tmp_path: Path) -> None:
    app, db, _ = _app(tmp_path)
    with TestClient(app) as client:
        r = client.post("/trades/20/review", data=REVIEW,
                        headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code == 204, r.text
    assert r.headers.get("HX-Redirect") == "/reviews/pending"
    row = _row(db)
    assert row[0] == "reviewed" and row[-1] == UNINTENDED_EXECUTION


def test_review_post_with_empty_refuses_4xx_preserved_b22_121(tmp_path: Path) -> None:
    app, db, att_id = _app(tmp_path)
    before = _row(db)
    with TestClient(app) as client:
        r = client.post("/trades/20/review", data={**REVIEW, "entry_intent": ""},
                        headers={"HX-Request": "true"}, follow_redirects=False)
    assert 400 <= r.status_code < 500, r.status_code
    assert attested_message(att_id) in r.text, r.text[-800:]
    assert _row(db) == before  # nothing written: not the review, not the intent
    assert before[0] == "closed" and before[-1] == UNINTENDED_EXECUTION


def test_review_form_renders_read_only_no_select_b22_122(tmp_path: Path) -> None:
    app, _, _ = _app(tmp_path)
    with TestClient(app) as client:
        r = client.get("/trades/20/review")
    assert r.status_code == 200
    assert "Unintended execution" in r.text
    assert 'name="entry_intent"' not in r.text
