"""cell_depth.py -- the dispatcher's depth instrument (2026-09-07 spec).

ROUND-TRIPPED 2026-11-03 from rwsmythe/harness-template master a9d328c (PR #2, the union of
the swing and Clearwater lineages); the only edit is the loader below in place of the
template's tests/harness/_loader.py.

Covers the reader's per-record depth arithmetic (including the SAME-request
dedup a real transcript needs -- one API response is written as several
adjacent JSONL records sharing one message id), the CLI discovery/reporting
path, and -- the whole point of the script -- the positive control for the
trap it exists to close: a naive glob of a project directory that never looks
inside `subagents/` once undercounted a real arc's spend by 42.9% while
silently reporting "no cells" as if that were a clean result.
"""

from __future__ import annotations

import contextlib
import errno
import io
import itertools
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import importlib.util
import sys

_CD_PATH = Path(__file__).resolve().parents[2] / "scripts" / "cell_depth.py"


def load_cell_depth():
    """Load scripts/cell_depth.py by path (scripts/ is not a package); mirrors the
    template suite's tests/harness/_loader.py so the ported tests run unchanged."""
    spec = importlib.util.spec_from_file_location("cell_depth", _CD_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cell_depth"] = mod
    spec.loader.exec_module(mod)
    return mod


cd = load_cell_depth()

_id_counter = itertools.count()


def _write_transcript(path: Path, lines: list[object]) -> None:
    """Write `lines` as a JSONL transcript; a str line is written verbatim
    (so a test can plant a malformed / non-JSON line), anything else is
    json.dumps'd."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for line in lines:
            if isinstance(line, str):
                handle.write(line + "\n")
            else:
                handle.write(json.dumps(line) + "\n")


def _usage_record(input_tokens: int, cache_read: int, cache_creation: int,
                   message_id: object = None) -> dict:
    """A usage-bearing assistant record. `message_id` defaults to a FRESH,
    unique id per call (a real request) -- pass the SAME id across two calls
    to simulate two content blocks of ONE request (the dedup case)."""
    if message_id is None:
        message_id = f"msg_{next(_id_counter)}"
    return {
        "type": "assistant",
        "message": {
            "id": message_id,
            "usage": {
                "input_tokens": input_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_creation,
                "output_tokens": 5,
            },
        },
    }


class TmpDirMixin:
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)


class CellNameFromFilenameTest(unittest.TestCase):
    def test_extracts_name_between_prefix_and_hash(self) -> None:
        self.assertEqual(
            cd.cell_name_from_filename("agent-ahotp-viewer-e6ee2c7b0ff7de76.jsonl"),
            "hotp-viewer")

    def test_extracts_hyphenated_name(self) -> None:
        self.assertEqual(
            cd.cell_name_from_filename("agent-astdin-race-retry-fe19a7b996ed507d.jsonl"),
            "stdin-race-retry")

    def test_anonymous_cell_reports_under_its_hash(self) -> None:
        # THE REAL FORM: a cell dispatched with no distinguishing name writes
        # agent-a<hash>.jsonl (no separating hyphen before the hash) -- 12 of
        # 73 real transcripts in this clone take exactly this shape. Missing
        # it silently drops those cells from every report.
        self.assertEqual(
            cd.cell_name_from_filename("agent-a133c183c57315ca9.jsonl"),
            "133c183c57315ca9")

    def test_non_matching_filename_returns_none(self) -> None:
        self.assertIsNone(cd.cell_name_from_filename("not-a-transcript.jsonl"))
        self.assertIsNone(cd.cell_name_from_filename("agent-abad-shorthash.jsonl"))
        self.assertIsNone(cd.cell_name_from_filename("agent-a0123456789abcde.jsonl"))  # 15 hex


class ReadTranscriptTest(unittest.TestCase, TmpDirMixin):
    """Test 1 (spec Sec 3.1): three usage records -> current/peak/turns, plus
    the PAST-CAP exit-2 assertion driven end to end through main()."""

    setUp = TmpDirMixin.setUp

    def test_three_records_give_current_peak_turns(self) -> None:
        path = self.tmp / "sess" / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        _write_transcript(path, [
            _usage_record(input_tokens=2, cache_read=100, cache_creation=50),   # depth 152
            _usage_record(input_tokens=2, cache_read=300, cache_creation=10),   # depth 312
            _usage_record(input_tokens=2, cache_read=200, cache_creation=8),    # depth 210 (last)
        ])
        stats = cd.read_transcript(path)
        self.assertEqual(stats.current, 210, "current is the LAST record's depth")
        self.assertEqual(stats.peak, 312, "peak is the max over the file")
        self.assertEqual(stats.turns, 3)
        self.assertEqual(stats.malformed, 0)

    def test_adjacent_same_id_records_fold_into_one_turn(self) -> None:
        # THE REAL SHAPE: Claude Code writes one API response as several
        # adjacent records (thinking / text / tool-use blocks) sharing ONE
        # message.id and identical usage. A transcript sampled from this
        # clone had 98 usage-bearing records but only 51 distinct requests
        # (47 adjacent duplicates) -- turns must count REQUESTS, not blocks.
        path = self.tmp / "sess" / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        _write_transcript(path, [
            _usage_record(2, 10, 0, message_id="msg_A"),
            _usage_record(2, 10, 0, message_id="msg_A"),  # same request, 2nd block
            _usage_record(2, 10, 0, message_id="msg_A"),  # same request, 3rd block
            _usage_record(2, 500, 0, message_id="msg_B"),  # a genuinely new request
        ])
        stats = cd.read_transcript(path)
        self.assertEqual(stats.turns, 2, "3 blocks of msg_A fold into 1 turn; "
                          "msg_B is a 2nd, distinct turn")
        self.assertEqual(stats.current, 502)
        self.assertEqual(stats.peak, 502)

    def test_fold_tolerates_an_interleaved_non_usage_record(self) -> None:
        # THE REAL SHAPE (round 2): a non-usage-bearing line (a tool_use /
        # tool_result / user echo) can sit BETWEEN two usage-bearing blocks of
        # the SAME request -- 418 such interleavings were observed across
        # this clone's 73 real transcripts. The fold must survive it (the
        # interleaved record never touches last_id, since it is `continue`d
        # before the id is read).
        path = self.tmp / "sess" / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        non_usage = {"type": "user", "message": {"role": "user", "content": "tool result"}}
        _write_transcript(path, [
            _usage_record(2, 10, 0, message_id="msg_A"),
            non_usage,
            _usage_record(2, 10, 0, message_id="msg_A"),  # same request, after the interleaving
        ])
        stats = cd.read_transcript(path)
        self.assertEqual(stats.turns, 1, "the interleaved non-usage record "
                          "must not break the same-id fold")

    def test_malformed_usage_on_a_duplicate_id_is_still_counted_malformed(self) -> None:
        # Malformed-shape detection must run BEFORE the duplicate-id fold
        # check -- a duplicate whose OWN usage is unusable must not be
        # silently absorbed by "it's just another block of a request we
        # already counted".
        path = self.tmp / "sess" / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        bad_duplicate = {"type": "assistant",
                          "message": {"id": "msg_A",
                                      "usage": {"input_tokens": [],
                                                 "cache_read_input_tokens": 0,
                                                 "cache_creation_input_tokens": 0}}}
        _write_transcript(path, [
            _usage_record(2, 10, 0, message_id="msg_A"),
            bad_duplicate,
        ])
        stats = cd.read_transcript(path)
        self.assertEqual(stats.malformed, 1, "the malformed duplicate must "
                          "still be counted, not silently folded away")
        self.assertEqual(stats.turns, 1)

    def test_records_without_a_message_id_are_never_folded(self) -> None:
        path = self.tmp / "sess" / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        no_id_record = {"type": "assistant",
                         "message": {"usage": {"input_tokens": 2,
                                                "cache_read_input_tokens": 10,
                                                "cache_creation_input_tokens": 0}}}
        _write_transcript(path, [no_id_record, no_id_record])
        stats = cd.read_transcript(path)
        self.assertEqual(stats.turns, 2, "no id => always a distinct request")

    def test_malformed_lines_are_skipped_and_counted(self) -> None:
        path = self.tmp / "sess" / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        _write_transcript(path, [
            _usage_record(input_tokens=2, cache_read=10, cache_creation=0),
            "{not valid json",
            "",  # blank lines are skipped silently, not counted as malformed
            _usage_record(input_tokens=2, cache_read=20, cache_creation=0),
            "also not json}",
        ])
        stats = cd.read_transcript(path)
        self.assertEqual(stats.turns, 2, "malformed lines never count as turns")
        self.assertEqual(stats.malformed, 2, "both bad lines are counted")
        self.assertEqual(stats.current, 22)

    def test_non_finite_and_wrong_type_usage_values_are_malformed_not_fatal(self) -> None:
        # A JSON number can decode to a Python float that overflows int() --
        # e.g. 1e309 decodes to `inf`, and int(inf) raises OverflowError. And a
        # usage field can carry the wrong JSON type (a list, say). Neither may
        # crash the whole read; both must count as malformed, like a syntax
        # error does.
        overflow_line = ('{"type": "assistant", "message": {"id": "m1", '
                          '"usage": {"input_tokens": 1e309, '
                          '"cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}}')
        wrong_type_record = {"type": "assistant",
                              "message": {"id": "m2",
                                          "usage": {"input_tokens": [],
                                                     "cache_read_input_tokens": 0,
                                                     "cache_creation_input_tokens": 0}}}
        path = self.tmp / "sess" / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        _write_transcript(path, [
            overflow_line,
            wrong_type_record,
            _usage_record(2, 30, 0),
        ])
        stats = cd.read_transcript(path)
        self.assertEqual(stats.malformed, 2, "the overflow line and the "
                          "wrong-type record are both counted malformed, "
                          "and neither aborts the read")
        self.assertEqual(stats.turns, 1)
        self.assertEqual(stats.current, 32)

    def test_non_usage_records_are_ignored_not_malformed(self) -> None:
        path = self.tmp / "sess" / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        _write_transcript(path, [
            {"type": "user", "message": {"role": "user", "content": "hi"}},
            _usage_record(input_tokens=2, cache_read=5, cache_creation=0),
        ])
        stats = cd.read_transcript(path)
        self.assertEqual(stats.turns, 1)
        self.assertEqual(stats.malformed, 0)

    def test_present_but_wrong_typed_usage_is_malformed_not_silently_ignored(self) -> None:
        # ADVISORY (round 3): a MISSING `usage` key is a normal non-usage
        # record (skipped, not malformed -- the test above). But a PRESENT,
        # wrong-shaped `usage` (e.g. a list instead of an object) is a
        # corrupted record, not an ordinary absence, and must be counted
        # malformed like any other unusable shape.
        path = self.tmp / "sess" / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        wrong_shaped = {"type": "assistant", "message": {"id": "m1", "usage": []}}
        _write_transcript(path, [wrong_shaped, _usage_record(2, 10, 0)])
        stats = cd.read_transcript(path)
        self.assertEqual(stats.malformed, 1)
        self.assertEqual(stats.turns, 1)

    def test_present_null_usage_is_malformed_missing_key_is_not(self) -> None:
        # CRITICAL (Reviewer B round 2): a GENUINELY MISSING "usage" key
        # (the test above's non-usage record) is an ordinary non-usage
        # record. But `"usage": null` is PRESENT and explicitly null -- an
        # ordinary API shape whose silent omission would report a LATER
        # request's absence as though the PREVIOUS request's depth were
        # still a clean, complete reading of the newest data. Must be
        # malformed, and distinguished from the missing-key case by
        # `_NO_USAGE_KEY`, never conflated via a bare `.get()` default.
        path = self.tmp / "sess" / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        present_null = {"type": "assistant", "message": {"id": "m2", "usage": None}}
        _write_transcript(path, [_usage_record(2, 100, 0), present_null])
        stats = cd.read_transcript(path)
        self.assertEqual(stats.malformed, 1, "a present-but-null usage is "
                          "malformed, not silently treated as absent")
        self.assertEqual(stats.turns, 1)
        self.assertEqual(stats.current, 102, "the null record contributes "
                          "nothing new -- the malformed count is what flags "
                          "the sweep incomplete, not a wrong current figure")

    def test_fractional_usage_value_is_malformed(self) -> None:
        # CRITICAL (Reviewer B round 2): a token count is a whole quantity.
        # A fractional float (400000.9) truncating via int() would silently
        # shave a supplied depth down -- in the worst case from just over
        # --cap to exactly the cap, hiding a PAST-CAP condition.
        path = self.tmp / "sess" / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        fractional = {"type": "assistant",
                       "message": {"id": "m1",
                                   "usage": {"input_tokens": 400000.9,
                                              "cache_read_input_tokens": 0,
                                              "cache_creation_input_tokens": 0}}}
        _write_transcript(path, [fractional])
        stats = cd.read_transcript(path)
        self.assertEqual(stats.malformed, 1)
        self.assertEqual(stats.turns, 0)

    def test_negative_usage_value_is_malformed(self) -> None:
        # CRITICAL (Reviewer B round 2): a negative count can never be a
        # real token measurement, and summing one UNDER-reports a genuine
        # positive component -- e.g. -200000 alongside a real 500001 reads
        # as 300001, hiding both the true magnitude and the corruption.
        path = self.tmp / "sess" / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        negative = {"type": "assistant",
                    "message": {"id": "m1",
                                "usage": {"input_tokens": -200000,
                                           "cache_read_input_tokens": 500001,
                                           "cache_creation_input_tokens": 0}}}
        _write_transcript(path, [negative])
        stats = cd.read_transcript(path)
        self.assertEqual(stats.malformed, 1)
        self.assertEqual(stats.current, 0, "the malformed record must never "
                          "contribute a partial, hidden-corruption depth")

    def test_reading_never_mutates_the_transcript(self) -> None:
        # The script is a READER of someone else's records; it must never
        # write to, truncate, or otherwise change the file it inspects.
        path = self.tmp / "sess" / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        _write_transcript(path, [_usage_record(2, 10, 0), _usage_record(2, 20, 0)])
        before_bytes = path.read_bytes()
        before_mtime = path.stat().st_mtime_ns
        cd.read_transcript(path)
        self.assertEqual(path.read_bytes(), before_bytes)
        self.assertEqual(path.stat().st_mtime_ns, before_mtime)


class MainCliTest(unittest.TestCase, TmpDirMixin):
    setUp = TmpDirMixin.setUp

    def test_past_cap_exits_2_end_to_end(self) -> None:
        # Three usage records, the last one over the default 400,000 cap --
        # drives the whole CLI path (discovery + main()), not just the reader.
        session_dir = self.tmp / "session-aaaaaaaa"
        path = session_dir / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        _write_transcript(path, [
            _usage_record(input_tokens=2, cache_read=100, cache_creation=50),
            _usage_record(input_tokens=2, cache_read=300, cache_creation=10),
            _usage_record(input_tokens=2, cache_read=450_000, cache_creation=0),
        ])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cd.main(["--project", str(self.tmp)])
        self.assertEqual(rc, 2, "a cell whose current depth exceeds --cap exits 2")
        printed = out.getvalue()
        self.assertRegex(
            printed,
            # rung-a item (d): the row now carries the CLI VERSION SET between the
            # session and the marker. These fixture records carry no `version` key,
            # so it reads `none-recorded` -- an explicit absence, never a blank.
            r"^fixture-cell {2}current=450002 {2}peak=450002 {2}turns=3 {2}"
            r"session=session- {2}cli=none-recorded {2}PAST-CAP {2}age=\d+\.\dh {2}flag=OVER\s*$",
            "the exact one-line output format, pinned end to end")

    def test_compacted_cell_trips_past_cap_on_peak_not_current(self) -> None:
        # THE COMPACTION CASE (Reviewer B CRITICAL, corpus-confirmed): a
        # cell's context can be compacted mid-run, so CURRENT drops back
        # under the cap while PEAK stays over it -- and the binding rule
        # requires a past-cap cell be re-dispatched from a FRESH context, not
        # treated as cheap again because its current reading looks small.
        # This fixture forces current and peak APART on purpose (peak first,
        # then a much smaller current) so the two code paths are actually
        # distinguishable -- a script that used `current` for the predicate
        # would silently miss this.
        session_dir = self.tmp / "session-iiiiiiii"
        path = session_dir / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        _write_transcript(path, [
            _usage_record(input_tokens=2, cache_read=900_000, cache_creation=0),  # peak, over cap
            _usage_record(input_tokens=2, cache_read=1_000, cache_creation=0),    # current, under cap
        ])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cd.main(["--project", str(self.tmp)])
        self.assertEqual(rc, 2, "PAST-CAP must fire on peak even though "
                          "current is comfortably under the cap")
        printed = out.getvalue()
        self.assertIn("current=1002", printed)
        self.assertIn("peak=900002", printed)
        self.assertIn("PAST-CAP", printed)

    def test_under_cap_exits_0_and_carries_no_marker(self) -> None:
        session_dir = self.tmp / "session-bbbbbbbb"
        path = session_dir / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        _write_transcript(path, [_usage_record(input_tokens=2, cache_read=10, cache_creation=0)])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cd.main(["--project", str(self.tmp)])
        self.assertEqual(rc, 0)
        self.assertNotIn("PAST-CAP", out.getvalue())

    def test_custom_cap_is_honored(self) -> None:
        # The SAME depth that is under the default 400,000 cap trips a custom,
        # lower cap -- pins that --cap is actually read, not just accepted.
        session_dir = self.tmp / "session-eeeeeeee"
        path = session_dir / "subagents" / "agent-afixture-cell-0123456789abcdef.jsonl"
        _write_transcript(path, [_usage_record(input_tokens=2, cache_read=100, cache_creation=0)])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cd.main(["--project", str(self.tmp), "--cap", "50"])
        self.assertEqual(rc, 2)
        self.assertIn("PAST-CAP", out.getvalue())

    def test_session_flag_restricts_to_one_session_literally(self) -> None:
        # Two sessions exist with DIFFERENT depths, so a discriminating
        # assertion can prove the REQUESTED session was the one selected (an
        # implementation that always picked the other session, or both, would
        # fail this -- same cell name + label prefix alone cannot tell them
        # apart). A session id is matched LITERALLY (never as a glob
        # pattern), so a value containing glob metacharacters selects nothing
        # rather than an unintended sibling directory.
        first_path = (self.tmp / "session-first11" / "subagents"
                      / "agent-afixture-cell-0123456789abcdef.jsonl")
        second_path = (self.tmp / "session-second2" / "subagents"
                       / "agent-afixture-cell-0123456789abcdef.jsonl")
        _write_transcript(first_path, [_usage_record(2, 100, 0)])   # depth 102
        _write_transcript(second_path, [_usage_record(2, 900, 0)])  # depth 902

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cd.main(["--project", str(self.tmp), "--session", "session-first11"])
        self.assertEqual(rc, 0)
        printed = out.getvalue()
        self.assertIn("current=102", printed, "the FIRST session's depth, "
                       "proving that session (not the second) was selected")
        self.assertNotIn("current=902", printed)
        self.assertEqual(printed.count("fixture-cell"), 1,
                          "--session must restrict discovery to ONE session")

        out2 = io.StringIO()
        with contextlib.redirect_stdout(out2):
            rc2 = cd.main(["--project", str(self.tmp), "--session", "session-*"])
        self.assertEqual(rc2, 1, "a literal '*' session id matches no real "
                          "directory named 'session-*' -- it is NOT a glob")

    def test_session_with_path_separator_is_rejected(self) -> None:
        # --session must be a single directory segment -- a stray separator
        # (or "..") can never walk it outside --project to a sibling
        # directory; this is a defensive validation, not a security boundary
        # (the tool's own declared envelope is a trusted-caller CLI), but it
        # turns a confusing silent misread into a clear, immediate error.
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cd.main(["--project", str(self.tmp), "--session", "../sibling"])
        self.assertEqual(rc, 4, "a configuration error, distinct from "
                          "PAST-CAP's 2 -- the measurement never ran")
        self.assertEqual(out.getvalue(), "")
        self.assertIn("BAD --session", err.getvalue())

        with self.assertRaises(cd.BadSession):
            list(cd.discover_cells(self.tmp, ".."))

    def test_empty_session_is_rejected(self) -> None:
        # Round 3 MINOR: Path(x) / "" is Path(x) UNCHANGED in pathlib, so an
        # unrejected "" would silently skip the whole session-directory layer
        # and search <project>/subagents/ directly -- the same sibling-escape
        # hazard ".." is rejected for, via omission instead of traversal.
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cd.main(["--project", str(self.tmp), "--session", ""])
        self.assertEqual(rc, 4)
        self.assertIn("BAD --session", err.getvalue())

        with self.assertRaises(cd.BadSession):
            list(cd.discover_cells(self.tmp, ""))

    def test_drive_qualified_session_is_rejected(self) -> None:
        # MAJOR (Reviewer B round 2): "D:foo" has NO separator at all, so
        # the "/"/"\\"/".."-only check let it through -- but Windows
        # resolves a drive-qualified relative segment against drive D's own
        # remembered current directory, not as a child of --project. Reject
        # any colon rather than trying to enumerate every escaping shape.
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cd.main(["--project", str(self.tmp), "--session", "D:foo"])
        self.assertEqual(rc, 4, "a configuration error, never a silent "
                          "no-cells (1) or an escaped read")
        self.assertIn("BAD --session", err.getvalue())

        with self.assertRaises(cd.BadSession):
            list(cd.discover_cells(self.tmp, "D:foo"))

    def test_invalid_cap_argument_exits_4_not_2(self) -> None:
        # Round 3 MINOR: argparse's own usage-error path used to call
        # sys.exit(2) directly, colliding with PAST-CAP's 2 -- the exact
        # ambiguity the exit-4 configuration-error code exists to remove.
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cd.main(["--project", str(self.tmp), "--cap", "not-an-int"])
        self.assertEqual(rc, 4)
        self.assertIn("USAGE ERROR", err.getvalue())

    def test_unknown_argument_exits_4_not_2(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cd.main(["--project", str(self.tmp), "--not-a-real-flag"])
        self.assertEqual(rc, 4)
        self.assertIn("USAGE ERROR", err.getvalue())

    def test_zero_turn_cell_is_incomplete_not_silently_clean(self) -> None:
        # Round 3 MAJOR: a discovered transcript with no usage-bearing
        # request yet (the normal shape right after dispatch, before the
        # first response lands) reads as current=0/peak=0 -- accurate as far
        # as it goes, but must not look like a clean, COMPLETE measurement.
        path = (self.tmp / "session-oooooooo" / "subagents"
                / "agent-afixture-cell-0123456789abcdef.jsonl")
        _write_transcript(path, [
            {"type": "user", "message": {"role": "user", "content": "hi"}},
        ])
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cd.main(["--project", str(self.tmp)])
        self.assertEqual(rc, 3)
        self.assertIn("current=0  peak=0  turns=0", out.getvalue())
        self.assertIn("0 turns recorded", err.getvalue())

    def test_cell_positional_filters_by_substring(self) -> None:
        for name in ("alpha-cell", "beta-cell"):
            path = self.tmp / "session-dddddddd" / "subagents" / f"agent-a{name}-0123456789abcdef.jsonl"
            _write_transcript(path, [_usage_record(2, 10, 0)])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cd.main(["--project", str(self.tmp), "alpha"])
        self.assertEqual(rc, 0)
        printed = out.getvalue()
        self.assertIn("alpha-cell", printed)
        self.assertNotIn("beta-cell", printed)

    def test_anonymous_cell_is_discovered_and_reported(self) -> None:
        path = (self.tmp / "session-ffffffff" / "subagents"
                / "agent-a0123456789abcdef.jsonl")
        _write_transcript(path, [_usage_record(2, 10, 0)])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cd.main(["--project", str(self.tmp)])
        self.assertEqual(rc, 0)
        self.assertIn("0123456789abcdef  current=12", out.getvalue())

    def test_malformed_count_is_reported_on_stderr(self) -> None:
        path = (self.tmp / "session-gggggggg" / "subagents"
                / "agent-afixture-cell-0123456789abcdef.jsonl")
        _write_transcript(path, [_usage_record(2, 10, 0), "{bad json"])
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cd.main(["--project", str(self.tmp)])
        # A truncated/malformed final line (the NORMAL shape of a transcript
        # being appended to while this script reads it) must not advertise a
        # clean, complete measurement -- exit 3, not 0 (Reviewer B MAJOR).
        self.assertEqual(rc, 3)
        self.assertIn("1 malformed line(s)", err.getvalue())

    def test_project_directory_is_always_named_on_stderr(self) -> None:
        # MAJOR 5: the resolved project directory must be VISIBLE on every
        # run, explicit or guessed -- a guessed-but-existing wrong directory
        # is otherwise silent (the missing-directory guard never fires for
        # it). Labeled distinctly so a guess is never mistaken for the same
        # authority as an explicit --project.
        path = (self.tmp / "session-jjjjjjjj" / "subagents"
                / "agent-afixture-cell-0123456789abcdef.jsonl")
        _write_transcript(path, [_usage_record(2, 10, 0)])

        err_explicit = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err_explicit):
            cd.main(["--project", str(self.tmp)])
        self.assertIn(f"project (explicit --project): {self.tmp}", err_explicit.getvalue())

        err_guessed = io.StringIO()
        with mock.patch.object(cd, "default_project_dir", return_value=self.tmp):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err_guessed):
                cd.main([])
        self.assertIn("project (guessed default", err_guessed.getvalue())
        self.assertIn(str(self.tmp), err_guessed.getvalue())

    def test_missing_project_directory_is_a_configuration_error(self) -> None:
        # MINOR 6: distinct from PAST-CAP's 2 -- a caller reading exit status
        # alone must be able to tell "the measurement never ran" apart from
        # "it ran and found a cell over the cap".
        out, err = io.StringIO(), io.StringIO()
        missing = self.tmp / "does-not-exist"
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cd.main(["--project", str(missing)])
        self.assertEqual(rc, 4)
        self.assertIn("NO PROJECT DIRECTORY", err.getvalue())

    def test_unparseable_filename_is_reported_not_silently_dropped(self) -> None:
        # MAJOR 4: a file matching the agent-a*.jsonl discovery glob but that
        # neither filename pattern can parse (e.g. a future format revision)
        # must be LOUD, exactly like the subagents/-less-directory trap --
        # never silently absorbed while other, parseable cells still report.
        good_path = (self.tmp / "session-kkkkkkkk" / "subagents"
                     / "agent-agood-cell-0123456789abcdef.jsonl")
        weird_path = (self.tmp / "session-kkkkkkkk" / "subagents"
                      / "agent-aWEIRD-FORMAT-not-16-hex.jsonl")
        _write_transcript(good_path, [_usage_record(2, 10, 0)])
        _write_transcript(weird_path, [_usage_record(2, 20, 0)])

        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cd.main(["--project", str(self.tmp)])
        self.assertEqual(rc, 3, "an unparsed filename makes the sweep "
                          "INCOMPLETE, not silently clean")
        self.assertIn("good-cell", out.getvalue())
        self.assertIn("DISCOVERY ERROR", err.getvalue())
        self.assertIn("WEIRD-FORMAT-not-16-hex.jsonl", err.getvalue())

        # Direct discovery-level assertion (belt): the strict (no `errors`
        # list) call path raises rather than silently continuing.
        with self.assertRaises(cd.DiscoveryError):
            list(cd.discover_cells(self.tmp, "session-kkkkkkkk"))

    def test_session_listing_error_is_isolated_not_a_silent_blind_spot(self) -> None:
        # CRITICAL 2: a directory that cannot be LISTED (permissions,
        # transient FS error) must not vanish from the sweep with no sign
        # anything went wrong -- and one bad directory must not blind
        # discovery of every OTHER, healthy session.
        good_path = (self.tmp / "session-llllllll" / "subagents"
                     / "agent-agood-cell-0123456789abcdef.jsonl")
        bad_session_dir = self.tmp / "session-mmmmmmmm"
        bad_session_dir.mkdir(parents=True)
        _write_transcript(good_path, [_usage_record(2, 10, 0)])

        real_scan = cd._scan_dir_entries

        def _flaky_scan(path: Path):
            if path == bad_session_dir / "subagents":
                raise PermissionError(f"simulated permission error: {path}")
            return real_scan(path)

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(cd, "_scan_dir_entries", side_effect=_flaky_scan):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = cd.main(["--project", str(self.tmp)])
        self.assertEqual(rc, 3, "a directory-listing error makes the sweep "
                          "INCOMPLETE, never a silent clean 0")
        self.assertIn("good-cell", out.getvalue())
        self.assertIn("DISCOVERY ERROR", err.getvalue())
        self.assertIn("session-mmmmmmmm", err.getvalue())

    def test_top_level_listing_error_is_reported_not_swallowed(self) -> None:
        # The other half of CRITICAL 2: a failure listing the PROJECT
        # directory itself (not one session's subagents/) must also be
        # reported, never silently absorbed into "no cells found".
        (self.tmp / "session-nnnnnnnn").mkdir(parents=True)
        with mock.patch.object(cd, "_scan_dir_entries",
                                side_effect=PermissionError("simulated")):
            errors: list = []
            found = list(cd.discover_cells(self.tmp, None, errors=errors))
        self.assertEqual(found, [])
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], cd.DiscoveryError)

        with mock.patch.object(cd, "_scan_dir_entries",
                                side_effect=PermissionError("simulated")):
            with self.assertRaises(cd.DiscoveryError):
                list(cd.discover_cells(self.tmp, None))

    def test_one_unreadable_transcript_does_not_abort_the_whole_report(self) -> None:
        # One corrupt/unreadable transcript must not take down the report for
        # every OTHER cell discovered in the same sweep.
        good_path = (self.tmp / "session-hhhhhhhh" / "subagents"
                     / "agent-agood-cell-0123456789abcdef.jsonl")
        bad_path = (self.tmp / "session-hhhhhhhh" / "subagents"
                    / "agent-abad-cell-fedcba9876543210.jsonl")
        _write_transcript(good_path, [_usage_record(2, 10, 0)])
        _write_transcript(bad_path, [_usage_record(2, 20, 0)])

        real_read = cd.read_transcript

        def _flaky_read(path: Path):
            if path == bad_path:
                raise OSError("simulated unreadable transcript")
            return real_read(path)

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(cd, "read_transcript", side_effect=_flaky_read):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = cd.main(["--project", str(self.tmp)])
        # A cell whose depth is UNKNOWN must never look like a clean (0)
        # sweep -- exit 3 is the distinct "incomplete sweep" signal, separate
        # from PAST-CAP (2, unaffected here) and NO-CELLS-FOUND (1, wrong --
        # cells WERE found, one just could not be read).
        self.assertEqual(rc, 3)
        self.assertIn("good-cell", out.getvalue())
        self.assertNotIn("bad-cell  current", out.getvalue())
        self.assertIn("UNREADABLE", err.getvalue())
        self.assertIn("bad-cell", err.getvalue())


class NoSubagentsDirTest(unittest.TestCase):
    """Test 2 (spec Sec 3.2) -- THE POSITIVE CONTROL. A project directory that
    has a session but NO subagents/ subdirectory must make the empty result
    LOUD, not silently report a clean-looking nothing."""

    def test_missing_subagents_dir_is_reported_loudly(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        # A session directory exists, and even a same-named jsonl file sits at
        # the WRONG depth (no subagents/ in the path) -- so a naive
        # `<project>/*/agent-a*.jsonl` glob (skipping the subagents/ segment)
        # would find it and wrongly "pass". The pinned discovery pattern is
        # `<project>/*/subagents/agent-a*.jsonl`; this directory has no such
        # path at all.
        session_dir = tmp / "session-cccccccc"
        session_dir.mkdir(parents=True)
        decoy = session_dir / "agent-adecoy-cell-0123456789abcdef.jsonl"
        decoy.write_text(json.dumps(_usage_record(2, 10, 0)) + "\n", encoding="utf-8")

        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cd.main(["--project", str(tmp)])

        self.assertEqual(rc, 1, "no cells found is reported as a distinct "
                          "non-zero exit, never a silent clean 0")
        self.assertEqual(out.getvalue(), "", "nothing is printed on stdout "
                          "when discovery finds nothing")
        message = err.getvalue()
        self.assertIn("NO CELLS FOUND", message)
        self.assertIn("subagents", message,
                       "the message names the subagents/ path it looked "
                       "for, so a reader can see WHY nothing was found")

        # Direct discovery-level assertion (belt): the generator truly yields
        # nothing over this tree.
        found = list(cd.discover_cells(tmp, None))
        self.assertEqual(found, [], "the decoy file sits outside subagents/ "
                          "and must not be discovered")


class DefaultProjectDirTest(unittest.TestCase):
    def test_replaces_path_separators_and_colon(self) -> None:
        with mock.patch.object(cd.Path, "cwd", return_value=cd.Path("C:/Users/example/some-repo")):
            result = cd.default_project_dir(claude_home=cd.Path("/home/x/.claude"))
        self.assertEqual(
            result,
            cd.Path("/home/x/.claude/projects/C--Users-example-some-repo"))


class CliVersionSetTest(unittest.TestCase, TmpDirMixin):
    """rung-a item (d), harness half: **the per-cell CLI VERSION SET, and a set of
    size > 1 IS a span.**

    The harness stamps each transcript record with the CLI version that wrote it (the
    top-level ``version`` key -- confirmed across this clone's own agent transcripts,
    e.g. 2.1.243 and 2.1.263 cells). A cell whose transcript carries two of them ran
    ACROSS a binary change, which is the same class of unrecorded regime variable that
    v17's seed 8 attempt 2 paid for on the game side.

    Driven through ``cd.main`` -- **the CLI's own entry point over a transcript
    fixture containing two versions** -- never by inspecting ``TranscriptStats``
    alone, which is exactly what passes while the printed row shows nothing."""

    setUp = TmpDirMixin.setUp

    @staticmethod
    def _versioned(record: dict, version: object) -> dict:
        out = dict(record)
        out["version"] = version
        return out

    def _run(self, lines: list[object]) -> str:
        path = (self.tmp / "session-aaaaaaaa" / "subagents"
                / "agent-afixture-cell-0123456789abcdef.jsonl")
        _write_transcript(path, lines)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with contextlib.redirect_stderr(io.StringIO()):
                cd.main(["--project", str(self.tmp)])
        return out.getvalue()

    def test_two_versions_in_one_transcript_report_as_a_SPAN(self) -> None:
        printed = self._run([
            self._versioned(_usage_record(1, 10, 0), "2.1.265"),
            self._versioned(_usage_record(1, 20, 0), "2.1.266"),
        ])
        self.assertIn("cli=SPAN[2.1.265,2.1.266]", printed)
        # ...and the NEGATIVE control on the identical fixture minus the second
        # version: the reader must NOT call a single-version cell a span.
        printed_single = self._run([
            self._versioned(_usage_record(1, 10, 0), "2.1.266"),
            self._versioned(_usage_record(1, 20, 0), "2.1.266"),
        ])
        self.assertIn("cli=2.1.266", printed_single)
        self.assertNotIn("SPAN", printed_single)

    def test_the_span_is_sorted_so_the_row_is_stable(self) -> None:
        # the SAME two versions planted in the opposite order print identically --
        # a set has no order, and an unsorted render would make the row unstable.
        forward = self._run([
            self._versioned(_usage_record(1, 10, 0), "2.1.265"),
            self._versioned(_usage_record(1, 20, 0), "2.1.266"),
        ])
        reverse = self._run([
            self._versioned(_usage_record(1, 10, 0), "2.1.266"),
            self._versioned(_usage_record(1, 20, 0), "2.1.265"),
        ])
        self.assertIn("cli=SPAN[2.1.265,2.1.266]", forward)
        self.assertIn("cli=SPAN[2.1.265,2.1.266]", reverse)

    def test_versions_are_collected_from_NON_usage_records_too(self) -> None:
        """Most transcript records carry no ``usage`` at all, and a span is a fact
        about the WHOLE transcript. Collecting only off usage-bearing records would
        miss a binary change that happened between two model turns."""
        printed = self._run([
            self._versioned(_usage_record(1, 10, 0), "2.1.265"),
            {"type": "user", "version": "2.1.266", "message": {"role": "user"}},
        ])
        self.assertIn("cli=SPAN[2.1.265,2.1.266]", printed)

    def test_no_version_key_reads_as_an_explicit_absence(self) -> None:
        printed = self._run([_usage_record(1, 10, 0)])
        self.assertIn("cli=none-recorded", printed)
        self.assertNotIn("SPAN", printed)

    def test_a_non_string_version_is_ignored_not_counted_as_a_span(self) -> None:
        # a malformed record must not MANUFACTURE a span out of nothing.
        printed = self._run([
            self._versioned(_usage_record(1, 10, 0), "2.1.266"),
            self._versioned(_usage_record(1, 20, 0), 2166),
            self._versioned(_usage_record(1, 30, 0), ""),
            self._versioned(_usage_record(1, 40, 0), None),
        ])
        self.assertIn("cli=2.1.266", printed)
        self.assertNotIn("SPAN", printed)

    def test_a_non_version_shaped_string_cannot_forge_a_span_or_inject_lines(self) -> None:
        """**Reviewer A r1 (MINOR), reproduced.** "Any nonempty string" let a record
        carrying `"2.1.266\\nFORGED"` do two things at once: MANUFACTURE a span (two
        distinct strings where the binary never moved) and inject its own line into a
        report rendered verbatim to whoever reads a cell's depth. `$` would not have
        caught it either -- Python's `$` matches before a trailing newline, so the
        pattern is anchored with `\\Z`."""
        printed = self._run([
            self._versioned(_usage_record(1, 10, 0), "2.1.266"),
            self._versioned(_usage_record(1, 20, 0), "2.1.266\nFORGED"),
            self._versioned(_usage_record(1, 30, 0), "2.1.266\n"),
            self._versioned(_usage_record(1, 40, 0), "not-a-version"),
        ])
        self.assertIn("cli=2.1.266", printed)
        self.assertNotIn("SPAN", printed)
        self.assertNotIn("FORGED", printed)
        # the report is ONE line for this cell -- nothing was injected into it.
        self.assertEqual(len([ln for ln in printed.splitlines() if ln.strip()]), 1)

    def test_a_suffixed_version_is_still_a_version(self) -> None:
        # the pattern must not refuse a legitimate future format and silently turn
        # every reading into a gap.
        printed = self._run([
            self._versioned(_usage_record(1, 10, 0), "2.1.266-beta.1"),
        ])
        self.assertIn("cli=2.1.266-beta.1", printed)

    def test_the_reader_exposes_the_set_itself(self) -> None:
        path = (self.tmp / "session-aaaaaaaa" / "subagents"
                / "agent-afixture-cell-0123456789abcdef.jsonl")
        _write_transcript(path, [
            self._versioned(_usage_record(1, 10, 0), "2.1.265"),
            self._versioned(_usage_record(1, 20, 0), "2.1.266"),
            self._versioned(_usage_record(1, 30, 0), "2.1.265"),
        ])
        stats = cd.read_transcript(path)
        self.assertEqual(stats.cli_versions, {"2.1.265", "2.1.266"})
        self.assertEqual(stats.turns, 3)          # unchanged by the new collection


class SelectorCliTest(unittest.TestCase, TmpDirMixin):
    """Selector tests: --live / --sessions / --agent with strict discovery."""

    def setUp(self) -> None:
        TmpDirMixin.setUp(self)
        self.now = time.time()

    def _cell(self, name: str | None, depth: int, *, age: float = 0,
              session: str = "sess-1", identity: str = "0123456789abcdef") -> Path:
        filename = (f"agent-a{name}-{identity}.jsonl" if name is not None
                    else f"agent-a{identity}.jsonl")
        path = self.tmp / session / "subagents" / filename
        _write_transcript(path, [_usage_record(0, depth, 0)])
        self._age(path, age)
        return path

    def _session(self, depth: int = 0, *, age: float = 0,
                 session: str = "sess-1") -> Path:
        path = self.tmp / f"{session}.jsonl"
        _write_transcript(path, [_usage_record(0, depth, 0)])
        self._age(path, age)
        return path

    def _age(self, path: Path, hours: float) -> None:
        stamp = self.now - hours * 3600
        os.utime(path, (stamp, stamp))

    def _run(self, *extra: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.object(cd.time, "time", return_value=self.now):
            rc = cd.main(["--project", str(self.tmp), *extra])
        return rc, out.getvalue(), err.getvalue()

    def test_live_filter_selects_by_transcript_age(self) -> None:
        self._cell("old", 900_000, age=48)
        self._cell(None, 100_000, age=1 / 60)
        rc, out, _ = self._run("--live", "6")
        self.assertEqual(rc, 0)
        self.assertIn("0123456789abcdef  current=100000", out)
        self.assertNotIn("old  current", out)
        self.assertRegex(out, r"age=0\.0h {2}flag=ok\s*$")

    def test_sessions_mode_reads_main_transcripts_and_excludes_cells(self) -> None:
        self._cell("cell", 700_000)
        main = self._session(396_000)
        # Main-session mode must retain request folding and PEAK/current semantics.
        _write_transcript(main, [
            _usage_record(1000, 390_000, 5000, message_id="first"),
            {"type": "user"},
            _usage_record(1000, 390_000, 5000, message_id="first"),
            _usage_record(0, 10, 0, message_id="second"),
        ])
        rc, out, _ = self._run("--sessions")
        self.assertEqual(rc, 0)
        self.assertIn("sess-1  current=10  peak=396000  turns=2", out)
        self.assertNotIn("cell  current", out)
        rc, out, _ = self._run()
        self.assertEqual(rc, 2)
        self.assertIn("cell  current=700000", out)
        self.assertNotIn("sess-1  current", out)
        # A main transcript can exist without its session directory.
        self._session(25, session="sess-2")
        rc, out, _ = self._run("--sessions", "--session", "sess-2", "sess-2")
        self.assertEqual(rc, 0)
        self.assertIn("sess-2  current=25", out)
        self.assertNotIn("sess-1  current", out)

    def test_agent_reads_a_parked_cell_older_than_the_live_window(self) -> None:
        self._cell("parked", 350_000, age=3)
        self._cell(None, 50_000, age=1 / 60)
        rc, out, _ = self._run("--live", "1")
        self.assertEqual(rc, 0)
        self.assertIn("0123456789abcdef  current", out)
        self.assertNotIn("parked  current", out)
        rc, out, _ = self._run("--agent", "parked")
        self.assertEqual(rc, 0)
        self.assertIn("parked  current=350000", out)
        self.assertNotIn("0123456789abcdef  current", out)
        self.assertIn("flag=ok", out)
        out.encode("ascii")

    def test_agent_is_repeatable_and_applies_the_cap(self) -> None:
        self._cell("one", 450_000)
        self._cell(None, 100_000)
        self._cell("three", 200_000)
        rc, out, _ = self._run("--agent", "one", "--agent", "0123456789abcdef")
        self.assertEqual(rc, 2)
        self.assertIn("one  current=450000", out)
        self.assertIn("0123456789abcdef  current=100000", out)
        self.assertNotIn("three  current", out)

    def test_agent_unknown_id_exits_4_naming_the_searched_glob(self) -> None:
        self._cell("present", 100_000)
        rc, out, err = self._run("--agent", "missing")
        self.assertEqual(rc, 4)
        self.assertIn("subagents", err)
        self.assertIn("agent-amissing.jsonl", err)
        self.assertEqual(out, "")
        err.encode("ascii")

    def test_agent_with_live_is_a_usage_error(self) -> None:
        self._cell("x", 100_000)
        rc, out, err = self._run("--agent", "x", "--live", "1")
        self.assertEqual(rc, 4)
        self.assertEqual(out, "")
        self.assertIn("USAGE ERROR", err)

    def test_r3_a_old_cell_with_a_fresh_parent_is_listed_and_flagged_parked(self) -> None:
        self._cell(None, 50_000, age=5)
        self._session(age=1 / 60)
        rc, out, _ = self._run("--live", "1")
        self.assertEqual(rc, 0)
        self.assertIn("0123456789abcdef  current=50000", out)
        self.assertRegex(out, r"age=5\.0h {2}flag=parked\s*$")

    def test_r3_b_old_cell_with_an_old_parent_is_not_listed(self) -> None:
        self._cell("gone", 50_000, age=5)
        self._session(age=5)
        rc, out, _ = self._run("--live", "1")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "no cells written in the last 1h (cap 400,000); nothing to check\n")

    def test_r3_c_a_fresh_cell_is_listed_not_flagged_parked(self) -> None:
        self._cell("fresh", 50_000, age=1 / 60)
        self._session(age=1 / 60)
        rc, out, _ = self._run("--live", "1")
        self.assertEqual(rc, 0)
        self.assertIn("fresh  current=50000", out)
        self.assertIn("flag=ok", out)
        self.assertNotIn("parked", out)

    def test_r3_d_a_parked_cell_over_the_cap_exits_2(self) -> None:
        self._cell("deep", 500_000, age=5)
        self._session(age=1 / 60)
        rc, out, _ = self._run("--live", "1", "--cap", "400000")
        self.assertEqual(rc, 2)
        self.assertIn("PAST-CAP", out)
        self.assertIn("flag=OVER,parked", out)

    def test_r3_a_missing_parent_transcript_does_not_crash(self) -> None:
        self._cell("orphan", 50_000, age=5)
        rc, out, _ = self._run("--live", "1")
        self.assertEqual(rc, 0)
        self.assertNotIn("orphan  current", out)
        self.assertIn("nothing to check", out)

    def test_r3_toctou_deletion_between_check_and_stat_does_not_crash(self) -> None:
        cell = self._cell("raced", 50_000, age=5)
        session = self._session(age=1 / 60)
        real_stat = Path.stat

        def _stat_raises_for_session(path: Path, *args, **kwargs):
            if path == session:
                raise FileNotFoundError(path)
            return real_stat(path, *args, **kwargs)

        with mock.patch.object(Path, "stat", _stat_raises_for_session):
            self.assertIsNone(cd.session_transcript_age_hours(cell, now=self.now))

    def test_r3_session_transcript_path_never_crosses_project_dirs(self) -> None:
        path = self.tmp / "projects" / "some-slug" / "sess-9" / "subagents" / "agent-ax.jsonl"
        self.assertEqual(cd.session_transcript_path(path),
                         self.tmp / "projects" / "some-slug" / "sess-9.jsonl")

    def test_r3_sessions_mode_with_live_is_unaffected_by_parked_logic(self) -> None:
        project = self.tmp / "projects" / "some-slug"
        main = project / "sess-1.jsonl"
        _write_transcript(main, [_usage_record(0, 100_000, 0)])
        self._age(main, 5)
        # This would be the parent if the cell-only path derivation were misapplied.
        _write_transcript(self.tmp / "projects.jsonl", [_usage_record(0, 1, 0)])
        rc, out, _ = self._run("--project", str(project), "--sessions", "--live", "1")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "no sessions written in the last 1h (cap 400,000); nothing to check\n")

    def test_r3_over_cap_and_parked_flag_form_is_OVER_comma_parked(self) -> None:
        self._cell("deep", 500_000, age=5)
        self._session(age=1 / 60)
        rc, out, _ = self._run("--live", "1", "--cap", "400000")
        self.assertEqual(rc, 2)
        self.assertRegex(out, r"PAST-CAP {2}age=5\.0h {2}flag=OVER,parked\s*$")
        out.encode("ascii")

    def test_exit_map_over_cap_exits_2(self) -> None:
        cell = self._cell("deep", 1)
        _write_transcript(cell, [_usage_record(0, 500_000, 0), _usage_record(0, 10, 0)])
        rc, out, _ = self._run("--all")
        self.assertEqual(rc, 2)
        self.assertIn("current=10  peak=500000", out)
        self.assertIn("flag=OVER", out)
        # The cap is strict: equality is clean, and the positional filter composes.
        rc, out, _ = self._run("deep", "--agent", "deep", "--cap", "500000")
        self.assertEqual(rc, 0)
        self.assertIn("flag=ok", out)

    def test_exit_map_no_transcripts_exits_1_loud(self) -> None:
        for extra in (("--live", "1"), ("--sessions", "--live", "1")):
            with self.subTest(extra=extra):
                rc, out, err = self._run(*extra)
                self.assertEqual(rc, 1)
                self.assertEqual(out, "")
                self.assertIn("NO CELLS FOUND", err)
        # With no discovered transcript, a listing failure is incomplete, not absent.
        with mock.patch.object(cd, "_scan_dir_entries", side_effect=PermissionError("simulated")):
            rc, _, err = self._run("--sessions", "--live", "1")
        self.assertEqual(rc, 3)
        self.assertIn("DISCOVERY ERROR", err)

    def test_exit_map_unknown_agent_exits_4(self) -> None:
        self._cell("present", 100_000, session="sess-1")
        self._cell("elsewhere", 100_000, session="sess-2")
        for extra, pattern in (
            (("--agent", "present", "--agent", "missing"), "agent-amissing.jsonl"),
            (("--session", "sess-1", "--agent", "elsewhere"), "agent-aelsewhere.jsonl"),
        ):
            with self.subTest(extra=extra):
                rc, out, err = self._run(*extra)
                self.assertEqual(rc, 4)
                self.assertEqual(out, "")
                self.assertIn(pattern, err)

    def test_exit_map_argparse_usage_exits_4(self) -> None:
        for extra in (
            ("--agent", "x", "--sessions"),
            ("--agent", "x", "--live", "1"),
            ("--all", "--live", "1"),
            ("--all", "--agent", "x"),
            ("--live", "not-a-number"),
            ("--agent",),
        ):
            with self.subTest(extra=extra):
                rc, out, err = self._run(*extra)
                self.assertEqual(rc, 4)
                self.assertEqual(out, "")
                self.assertIn("USAGE ERROR", err)
        for session in ("", "..", "../other", "D:foo"):
            with self.subTest(session=session):
                rc, _, err = self._run("--sessions", "--session", session)
                self.assertEqual(rc, 4)
                self.assertIn("BAD --session", err)

    def test_exit_map_empty_live_window_exits_0(self) -> None:
        cell = self._cell("old", 900_000, age=48, session="sess-1")
        self._session(900_000, age=48)
        self._cell("fresh", 100_000, session="sess-2")
        self._session(100_000, session="sess-2")
        for mode, kind in (((), "cells"), (("--sessions",), "sessions")):
            with self.subTest(mode=mode):
                # The excluded old transcript must not even be read.
                real_read = cd.read_transcript

                def _read(path: Path):
                    if path in (cell, self.tmp / "sess-1.jsonl"):
                        raise OSError("old transcript should not be read")
                    return real_read(path)

                with mock.patch.object(cd, "read_transcript", side_effect=_read):
                    rc, out, err = self._run(*mode, "--session", "sess-1", "--live", "6")
                self.assertEqual(rc, 0)
                self.assertNotIn("UNREADABLE", err)
                self.assertEqual(out, f"no {kind} written in the last 6h (cap 400,000); nothing to check\n")


    def test_live_unreadable_cell_is_incomplete(self) -> None:
        self._cell("unreadable", 100_000)
        with mock.patch.object(cd, "read_transcript",
                               side_effect=PermissionError(errno.EACCES, "simulated")):
            rc, out, err = self._run("--live", "1")
        self.assertEqual(rc, 3)
        self.assertIn("UNREADABLE", err)
        self.assertNotIn("nothing to check", out)

    def test_live_cell_age_stat_failure_is_incomplete(self) -> None:
        cell = self._cell("unstatable", 100_000)
        real_stat = Path.stat

        def _stat(path: Path, *args, **kwargs):
            if path == cell:
                raise PermissionError(errno.EACCES, "simulated")
            return real_stat(path, *args, **kwargs)

        with mock.patch.object(Path, "stat", _stat):
            rc, out, err = self._run("--live", "1")
        self.assertEqual(rc, 3)
        self.assertIn("UNREADABLE", err)
        self.assertNotIn("nothing to check", out)

    def test_live_parent_stat_failure_is_incomplete(self) -> None:
        self._cell("old", 100_000, age=5)
        parent = self._session()
        real_stat = Path.stat

        def _stat(path: Path, *args, **kwargs):
            if path == parent:
                raise PermissionError(errno.EACCES, "simulated")
            return real_stat(path, *args, **kwargs)

        with mock.patch.object(Path, "stat", _stat):
            rc, out, err = self._run("--live", "1")
        self.assertEqual(rc, 3)
        self.assertIn("DISCOVERY ERROR", err)
        self.assertNotIn("nothing to check", out)

    def test_sessions_live_unreadable_or_unstatable_is_incomplete(self) -> None:
        session = self._session(100_000)
        real_stat = Path.stat

        def _stat(path: Path, *args, **kwargs):
            if path == session:
                raise PermissionError(errno.EACCES, "simulated")
            return real_stat(path, *args, **kwargs)

        for failure in (mock.patch.object(cd, "read_transcript",
                                          side_effect=PermissionError(errno.EACCES, "simulated")),
                        mock.patch.object(Path, "stat", _stat)):
            with self.subTest(failure=failure.attribute), failure:
                rc, out, err = self._run("--sessions", "--live", "1")
            self.assertEqual(rc, 3)
            self.assertIn("UNREADABLE", err)
            self.assertNotIn("nothing to check", out)

    def test_live_invalid_window_is_usage_error(self) -> None:
        self._cell("old", 100_000, age=5)
        for window in ("-1", "nan", "-inf"):
            with self.subTest(window=window):
                rc, out, err = self._run(f"--live={window}")
                self.assertEqual(rc, 4)
                self.assertIn("USAGE ERROR", err)
                self.assertEqual(out, "")

    def test_live_zero_and_infinity_are_valid(self) -> None:
        self._cell("old", 100_000, age=5)
        rc, out, _ = self._run("--live", "0")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "no cells written in the last 0h (cap 400,000); nothing to check\n")
        self.assertEqual(self._run("--live", "-0")[1], out)
        rc, out, _ = self._run("--live", "inf")
        self.assertEqual(rc, 0)
        self.assertIn("old  current=100000", out)

    def test_agent_exact_name_excludes_longer_sibling(self) -> None:
        self._cell("fixture-cell", 100_000)
        self._cell("fixture-cell9", 900_000)
        rc, out, _ = self._run("--agent", "fixture-cell")
        self.assertEqual(rc, 0)
        self.assertIn("fixture-cell  current=100000", out)
        self.assertNotIn("fixture-cell9", out)

    def test_agent_missing_exact_name_with_prefix_sibling_exits_4(self) -> None:
        self._cell("fixture-cell9", 100_000)
        rc, out, err = self._run("--agent", "fixture-cell")
        self.assertEqual(rc, 4)
        self.assertEqual(out, "")
        self.assertIn("searched:", err)
        self.assertIn("agent-afixture-cell.jsonl", err)
        self.assertIn("agent-afixture-cell-<16hex>.jsonl", err)

    def test_agent_full_name_hash_selects_one_transcript(self) -> None:
        self._cell("same-name", 100_000, identity="0123456789abcdef")
        self._cell("same-name", 900_000, identity="fedcba9876543210")
        rc, out, _ = self._run("--agent", "same-name-0123456789abcdef")
        self.assertEqual(rc, 0)
        self.assertIn("current=100000", out)
        self.assertNotIn("current=900000", out)
        self.assertEqual(len(out.splitlines()), 1)

    def test_agent_empty_id_is_usage_error(self) -> None:
        self._cell("present", 100_000)
        rc, out, err = self._run("--agent", "")
        self.assertEqual(rc, 4)
        self.assertEqual(out, "")
        self.assertIn("USAGE ERROR", err)

    def test_agent_listing_failure_is_incomplete_not_unknown(self) -> None:
        self._cell("hidden", 100_000)
        real_scan = cd._scan_dir_entries

        def _scan(path: Path):
            if path == self.tmp / "sess-1" / "subagents":
                raise PermissionError(errno.EACCES, "simulated")
            return real_scan(path)

        with mock.patch.object(cd, "_scan_dir_entries", side_effect=_scan):
            rc, out, err = self._run("--agent", "hidden")
        self.assertEqual(rc, 3)
        self.assertEqual(out, "")
        self.assertIn("DISCOVERY ERROR", err)
        self.assertNotIn("USAGE ERROR", err)

    def test_future_mtime_is_clamped_to_zero_age(self) -> None:
        self._cell("future", 100_000, age=-1)
        with mock.patch.object(cd.time, "time", return_value=self.now):
            rc, out, _ = self._run("--live", "0")
        self.assertEqual(rc, 0)
        self.assertRegex(out, r"age=0\.0h {2}flag=ok\s*$")

    def test_cell_exactly_at_live_boundary_is_listed(self) -> None:
        self.now = 1_800_000_000.0
        self._cell("boundary", 100_000, age=6)
        with mock.patch.object(cd.time, "time", return_value=self.now):
            rc, out, _ = self._run("--live", "6")
        self.assertEqual(rc, 0)
        self.assertIn("boundary  current=100000", out)
        self.assertRegex(out, r"age=6\.0h {2}flag=ok\s*$")


    def test_agent_reused_name_warns_once_per_session(self) -> None:
        self._cell("reused", 500_000, age=5, identity="0123456789abcdef")
        self._cell("reused", 100_000, identity="fedcba9876543210")
        self._cell("reused", 100_000, session="sess-2")
        for extra, rows in ((("--session", "sess-1", "--agent", "reused"), 2),
                            (("--agent", "reused", "--agent", "reused"), 3)):
            with self.subTest(extra=extra):
                rc, out, err = self._run(*extra)
                self.assertEqual(rc, 2)
                self.assertEqual(len(out.splitlines()), rows)
                notes = [line for line in err.splitlines() if line.startswith("NOTE:")]
                expected = [
                    "NOTE: --agent reused matched 2 transcripts in session sess-1; "
                    "use the full name-hash stem to read one",
                ]
                if rows == 3:
                    expected.append(
                        "NOTE: --agent reused matched transcripts in 2 sessions; "
                        "pass --session=<session-id> to read one")
                self.assertEqual(notes, expected)
        rc, out, err = self._run("--session", "sess-1", "--agent", "reused-fedcba9876543210")
        self.assertEqual(rc, 0)
        self.assertEqual(len(out.splitlines()), 1)
        self.assertNotIn("NOTE:", err)

    def test_agent_empty_id_with_discovery_error_is_usage_error(self) -> None:
        self._cell("present", 100_000)
        with mock.patch.object(cd, "_scan_dir_entries",
                               side_effect=PermissionError(errno.EACCES, "simulated")):
            rc, out, err = self._run("--agent=")
        self.assertEqual(rc, 4)
        self.assertEqual(out, "")
        self.assertIn("USAGE ERROR", err)

    def test_session_exactly_at_live_boundary_is_listed(self) -> None:
        self.now = 1_800_000_000.0
        self._session(100_000, age=6)
        with mock.patch.object(cd.time, "time", return_value=self.now):
            rc, out, _ = self._run("--sessions", "--live", "6")
        self.assertEqual(rc, 0)
        self.assertIn("sess-1  current=100000", out)
        self.assertRegex(out, r"age=6\.0h {2}flag=ok\s*$")

    def test_parent_exactly_at_live_boundary_retains_parked_cell(self) -> None:
        self.now = 1_800_000_000.0
        self._cell("parked", 100_000, age=7)
        self._session(age=6)
        with mock.patch.object(cd.time, "time", return_value=self.now):
            rc, out, _ = self._run("--live", "6")
        self.assertEqual(rc, 0)
        self.assertIn("parked  current=100000", out)
        self.assertRegex(out, r"age=7\.0h {2}flag=parked\s*$")

    def test_agent_listing_failure_reports_each_unmatched_id(self) -> None:
        self._cell("hidden", 100_000)
        real_scan = cd._scan_dir_entries

        def _scan(path: Path):
            if path == self.tmp / "sess-1" / "subagents":
                raise PermissionError(errno.EACCES, "simulated")
            return real_scan(path)

        with mock.patch.object(cd, "_scan_dir_entries", side_effect=_scan):
            rc, out, err = self._run("--agent", "hidden", "--agent", "missing")
        self.assertEqual(rc, 3)
        self.assertEqual(out, "")
        self.assertIn("DISCOVERY ERROR", err)
        self.assertEqual(err.count("searched:"), 2)
        self.assertIn("agent-ahidden.jsonl", err)
        self.assertIn("agent-amissing.jsonl", err)
        self.assertNotIn("USAGE ERROR", err)

    def test_agent_cross_session_note_preserves_rows_and_status(self) -> None:
        self._cell("shared", 450_000, age=30, session="sess-a")
        self._cell("shared", 100_000, session="sess-b")
        rc, out, err = self._run("--agent", "shared", "--agent", "shared")
        self.assertEqual(rc, 2)
        self.assertEqual(len(out.splitlines()), 2)
        self.assertIn("session=sess-a", out)
        self.assertIn("session=sess-b", out)
        self.assertEqual([line for line in err.splitlines() if line.startswith("NOTE:")], [
            "NOTE: --agent shared matched transcripts in 2 sessions; "
            "pass --session=<session-id> to read one",
        ])
        rc, out, err = self._run("--session", "sess-b", "--agent", "shared")
        self.assertEqual(rc, 0)
        self.assertEqual(len(out.splitlines()), 1)
        self.assertIn("session=sess-b", out)
        self.assertNotIn("NOTE:", err)

    def test_sessions_is_file_failure_is_incomplete_or_strict_error(self) -> None:
        entry = mock.Mock()
        entry.name = "blocked.jsonl"
        entry.path = str(self.tmp / entry.name)
        entry.is_file.side_effect = PermissionError(errno.EACCES, "simulated")
        with mock.patch.object(cd, "_scan_dir_entries", return_value=[entry]):
            with self.assertRaisesRegex(cd.DiscoveryError, "cannot stat"):
                list(cd.discover_sessions(self.tmp, None))
            errors: list[Exception] = []
            self.assertEqual(list(cd.discover_sessions(self.tmp, None, errors=errors)), [])
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], cd.DiscoveryError)
            rc, out, err = self._run("--sessions")
        self.assertEqual(rc, 3)
        self.assertEqual(out, "")
        self.assertIn("DISCOVERY ERROR", err)
        self.assertIn("cannot stat", err)

    def test_positional_miss_names_filter_in_no_cells_message(self) -> None:
        self._cell("present", 100_000)
        self._session(100_000)
        for extra in (("absent",), ("--live", "6", "absent"),
                      ("--sessions", "absent")):
            with self.subTest(extra=extra):
                rc, out, err = self._run(*extra)
                self.assertEqual(rc, 1)
                self.assertEqual(out, "")
                self.assertIn("NO CELLS FOUND", err)
                self.assertIn("(positional filter 'absent' matched none)", err)


if __name__ == "__main__":
    unittest.main()
