"""Route modules.  22-F T-G0 adds the shared close helper here (and T-G2 the
notice carrier beside it), in an existing module (no new module under
``swing/``)."""
from __future__ import annotations

import logging


def close_after_commit(conn, log: logging.Logger, *, what: str) -> str | None:
    """22-F T-G0 (F4): close a web root's connection AFTER its write
    committed.  A close failure there never loses data (the commit is
    durable), so it must not become a 500 that tells the operator the write
    failed and invites a retry against a durable row (the D68 class).

    Closes; on an ``Exception`` from the close logs ONE contained ERROR
    record and returns the one-line notice ``"<what> IS recorded; the
    database connection could not be closed cleanly (see the log)."``;
    returns None on a clean close.  An INTERRUPT at the close (a
    BaseException that is not an Exception) is the operator's stop signal:
    it is logged with the same record, the interrupt named, and re-raised
    BARE -- the server's own interrupt handling owns it (STOP-6, CHARC).
    """
    try:
        conn.close()
    except Exception as exc:  # noqa: BLE001 -- the CLASS
        from swing.trades.entry import log_contained, safe_text
        log_contained(
            log,
            "22-F: %s IS recorded and CLOSING the database connection "
            "afterwards RAISED (%s); the write is unaffected.",
            what, safe_text(exc))
        return (f"{what} IS recorded; the database connection could not be "
                "closed cleanly (see the log).")
    except BaseException as interrupt:
        # 22-F STOP-6 (CHARC): contain Exception, re-raise the rest.  A sink
        # failure travels as a NOTE on the interrupt (`log_contained_note`).
        from swing.trades.entry import log_contained_note, safe_text
        log_contained_note(
            log, interrupt,
            "22-F: %s IS recorded and CLOSING the database connection "
            "afterwards RAISED (%s); the write is unaffected; the INTERRUPT "
            "is re-raised.",
            what, safe_text(interrupt))
        raise
    return None


def append_close_notice(response, notice: str | None):
    """22-F T-G2: carry ``close_after_commit``'s notice on a BODY-bearing
    HTML response (a 204/303 has no body -- the ERROR record carries it
    there).  ``None`` returns the response unchanged."""
    if notice is None:
        return response
    from html import escape

    from fastapi.responses import HTMLResponse
    body = bytes(response.body) + (
        '<div class="close-notice" role="alert">' + escape(notice)
        + '</div>').encode("utf-8")
    headers = {k: v for k, v in response.headers.items()
               if k.lower() not in ("content-length", "content-type")}
    return HTMLResponse(content=body, status_code=response.status_code,
                        headers=headers)
