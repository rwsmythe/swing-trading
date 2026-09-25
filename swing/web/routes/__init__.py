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

    Closes; on failure logs ONE contained ERROR record and returns the
    one-line notice ``"<what> IS recorded; the database connection could not
    be closed cleanly (see the log)."``; returns None on a clean close.
    NEVER raises -- an interrupt at the close included, because the write it
    would misreport is already durable.
    """
    try:
        conn.close()
    except BaseException as exc:  # noqa: BLE001 -- the CLASS
        from swing.trades.entry import log_contained, safe_text
        log_contained(
            log,
            "22-F: %s IS recorded and CLOSING the database connection "
            "afterwards RAISED (%s); the write is unaffected.",
            what, safe_text(exc))
        return (f"{what} IS recorded; the database connection could not be "
                "closed cleanly (see the log).")
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
