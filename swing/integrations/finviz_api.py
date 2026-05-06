"""Finviz Elite API client.

V1 scope: fetch a saved-screen result via /export.ashx, normalize to the
canonical 13-column CSV schema, compute a deterministic signature hash for
drift detection. NO direct DB writes — caller (pipeline step OR CLI) owns
persistence. NO logging of token bytes, response URL, or response body.

See docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md §E
for endpoint reference + §F for the token-redaction discipline (incl.
defense-in-depth urllib3 DEBUG-log suppression per §A.12 / Codex R1 M2).
"""
from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import logging
import time
from collections.abc import Iterator
from typing import TYPE_CHECKING

import requests

from swing.pipeline.finviz_schema import REQUIRED_COLUMNS

if TYPE_CHECKING:
    from swing.config import Config

log = logging.getLogger(__name__)

_BASE_URL = "https://elite.finviz.com/export.ashx"
_MAX_DATA_ROWS = 5000  # safety bound; see plan §E.5
_RETRY_AFTER_MAX_SECONDS = 30  # wait at most this long on 429 + Retry-After

# Logger names that emit DEBUG-level lines including the full request URL
# (with `auth=<token>` query param). Suppressed during fetch_screen() per
# plan §A.12 (Codex R1 Major-2 fix).
_TRANSPORT_DEBUG_LOGGERS = (
    "urllib3.connectionpool",
    "requests.packages.urllib3.connectionpool",
)


@contextlib.contextmanager
def _suppress_transport_debug_logs() -> Iterator[None]:
    """Force urllib3 + requests-bundled-urllib3 loggers to WARNING for the
    duration; restore on exit. Defense-in-depth complement to the
    FinvizApiError.__str__ contract + cassette filter_query_parameters
    redaction. See plan §A.12."""
    prior = {n: logging.getLogger(n).level for n in _TRANSPORT_DEBUG_LOGGERS}
    try:
        for n in _TRANSPORT_DEBUG_LOGGERS:
            logging.getLogger(n).setLevel(logging.WARNING)
        yield
    finally:
        for n, lvl in prior.items():
            logging.getLogger(n).setLevel(lvl)


class FinvizConfigMissingError(RuntimeError):
    """Raised when token or screen_query is missing from cfg.integrations.finviz."""


class FinvizApiError(RuntimeError):
    """Generic Finviz API error (HTTP non-200 or network failure).

    `__str__` is engineered to never include the request URL (contains token
    in query string) or response body verbatim — only status code + body
    length. See plan §E.7."""

    def __init__(self, status_code: int, body_excerpt: str) -> None:
        self.status_code = status_code
        self.body_excerpt = body_excerpt
        super().__init__(
            f"FinvizApiError(status={status_code}, body=<{len(body_excerpt)} bytes>)"
        )


class FinvizRateLimitError(FinvizApiError):
    """Raised on HTTP 429 after one Retry-After-respecting retry."""


class FinvizSchemaParityError(RuntimeError):
    """Raised when the API response body cannot be normalized to the canonical
    13-column schema (missing column, excessive rows, etc.)."""


class FinvizPipelineActiveError(RuntimeError):
    """Raised by `_perform_finviz_fetch_no_lease` (CLI surface) when a pipeline
    run is currently in flight. Plan §A.14 cross-surface concurrency exclusion
    (Codex R2 Major-3 fix). NOT raised by `_step_finviz_fetch` (pipeline-internal)
    — that runs WHILE the lease is held by definition."""


class FinvizClient:
    """Client for the Finviz Elite saved-screen export endpoint.

    Stateless except for `last_rate_limit_remaining`, captured from the most
    recent successful HTTP response if Finviz emits an X-RateLimit-Remaining
    header (best-effort; Finviz does not document the header).
    """

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg.integrations.finviz
        self.last_rate_limit_remaining: int | None = None

    def fetch_screen(self) -> bytes:
        """Fetch the saved-screen result from Finviz Elite API.

        Returns the raw response body as bytes. Caller normalizes via
        normalize_to_canonical_csv. Raises typed exceptions for all failure
        modes; never logs or includes token in any error path.
        """
        if not self._cfg.token:
            raise FinvizConfigMissingError(
                "Finviz API token is missing. Set "
                "[integrations.finviz] token in user-config.toml."
            )
        if not self._cfg.screen_query:
            raise FinvizConfigMissingError(
                "Finviz screen_query is missing. Set "
                "[integrations.finviz] screen_query in user-config.toml."
            )

        url = f"{_BASE_URL}?{self._cfg.screen_query}&auth={self._cfg.token}"

        with _suppress_transport_debug_logs():
            try:
                response = requests.get(url, timeout=self._cfg.timeout_seconds)
            except requests.RequestException as exc:
                # str(exc) on requests.* exceptions can include the URL on some
                # versions. Wrap explicitly with empty body excerpt.
                raise FinvizApiError(0, "") from exc

        if response.status_code == 429:
            retry_after_str = response.headers.get("Retry-After", "")
            try:
                retry_after = int(retry_after_str)
            except ValueError:
                retry_after = -1
            if 0 < retry_after <= _RETRY_AFTER_MAX_SECONDS:
                log.warning(
                    "Finviz API 429 rate-limited; retrying after %ds", retry_after,
                )
                time.sleep(retry_after)
                with _suppress_transport_debug_logs():
                    try:
                        response = requests.get(url, timeout=self._cfg.timeout_seconds)
                    except requests.RequestException as exc:
                        raise FinvizApiError(0, "") from exc
                if response.status_code == 429:
                    raise FinvizRateLimitError(429, "")
            else:
                raise FinvizRateLimitError(429, "")

        if response.status_code != 200:
            raise FinvizApiError(response.status_code, "")

        # Best-effort rate-limit headroom capture.
        rl_str = response.headers.get("X-RateLimit-Remaining", "")
        try:
            self.last_rate_limit_remaining = int(rl_str) if rl_str else None
        except ValueError:
            self.last_rate_limit_remaining = None

        return response.content

    def normalize_to_canonical_csv(self, body: bytes) -> str:
        """Normalize API response body to the canonical 13-column CSV schema.

        Raises FinvizSchemaParityError on column missing OR row count exceeded.
        Sector + Industry preserved verbatim per Q7 lock.
        """
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FinvizSchemaParityError(
                f"Response body not UTF-8 decodable: {exc}"
            ) from exc

        reader = csv.reader(io.StringIO(text))
        try:
            header = next(reader)
        except StopIteration as exc:
            raise FinvizSchemaParityError("Response body has no header row") from exc

        header_cleaned = [h.strip() for h in header]
        header_set = set(header_cleaned)
        missing = [c for c in REQUIRED_COLUMNS if c not in header_set]
        if missing:
            raise FinvizSchemaParityError(
                f"Response body missing required columns: {missing}; "
                f"got: {header_cleaned}"
            )

        # Map response-column-index → canonical-column-index for projection.
        # The response MAY have extra columns; we drop them per Q4 lock
        # (canonical schema is unchanged).
        col_indices = [header_cleaned.index(c) for c in REQUIRED_COLUMNS]

        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(REQUIRED_COLUMNS)
        for row_count, row in enumerate(reader, start=1):
            if row_count > _MAX_DATA_ROWS:
                raise FinvizSchemaParityError(
                    f"Response row count exceeds safety bound ({_MAX_DATA_ROWS})"
                )
            # Pad short rows; truncate long rows to projected indices.
            extended = row + [""] * (max(col_indices) + 1 - len(row))
            writer.writerow([extended[i] for i in col_indices])

        return out.getvalue()

    def compute_signature_hash(self, body: bytes) -> str:
        """Deterministic SHA256 hash of canonicalized signature payload.

        Signature payload: JSON-encoded dict {column_set: sorted, first_row:
        [Ticker, Sector, Industry]} with sort_keys=True + UTF-8.

        Drift detection: same screen returns same hash; column-set change OR
        first-row-Ticker/Sector/Industry change → different hash.
        """
        text = body.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        try:
            header = next(reader)
        except StopIteration:
            return hashlib.sha256(b"<empty>").hexdigest()
        header_cleaned = sorted(h.strip() for h in header)
        first_row: list[str] = []
        for row in reader:
            if not row or all(not c.strip() for c in row):
                continue
            mapping = dict(zip([h.strip() for h in header], row, strict=False))
            first_row = [
                str(mapping.get("Ticker", "")),
                str(mapping.get("Sector", "")),
                str(mapping.get("Industry", "")),
            ]
            break
        payload = json.dumps(
            {"column_set": header_cleaned, "first_row": first_row},
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
