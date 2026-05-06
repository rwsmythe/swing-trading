"""Asserts _step_finviz_fetch is wired BEFORE _step_evaluate, AND that an API
failure does not break the pipeline (fallback to existing empty-inbox semantics).

Also pins the deferred Task 2.5 contract (plan §A.11): the `swing pipeline run`
CLI body calls `apply_overrides()` so [integrations.finviz] user-config values
propagate when the web layer spawns the CLI as a subprocess.
"""

import inspect
import re

from swing.pipeline.runner import run_pipeline_internal


def test_step_finviz_fetch_invoked_before_step_evaluate() -> None:
    """Source-text inspection: in run_pipeline_internal, the
    _step_finviz_fetch call site precedes the _step_evaluate call site.

    Source-text test (NOT runtime test) is intentional - it pins the wiring
    contract durably; a future refactor that accidentally reorders the steps
    will FAIL this test even if both steps still execute somewhere in the
    function.
    """
    src = inspect.getsource(run_pipeline_internal)
    fetch_idx = src.find("_step_finviz_fetch")
    eval_idx = src.find("_step_evaluate")
    assert fetch_idx > -1, "_step_finviz_fetch is not invoked in run_pipeline_internal"
    assert eval_idx > -1, "_step_evaluate is not invoked in run_pipeline_internal"
    assert fetch_idx < eval_idx, (
        f"Expected _step_finviz_fetch (offset {fetch_idx}) BEFORE "
        f"_step_evaluate (offset {eval_idx}); they appear reversed in source."
    )


def test_step_finviz_fetch_call_site_is_wrapped_in_try_except() -> None:
    """Source-text contract: the _step_finviz_fetch call site in
    run_pipeline_internal is enclosed in a try/except block whose handler
    LOGS rather than RAISES. A future refactor that removes the wrapper
    would let a programming error in the step abort the pipeline; this
    test catches that durably without needing the full pipeline-runner
    integration fixture.
    """
    src = inspect.getsource(run_pipeline_internal)
    fetch_idx = src.find("_step_finviz_fetch")
    assert fetch_idx > -1, "_step_finviz_fetch is not invoked in run_pipeline_internal"
    pre_window = src[max(0, fetch_idx - 1500):fetch_idx]
    post_window = src[fetch_idx:fetch_idx + 1500]
    assert "try:" in pre_window, (
        "_step_finviz_fetch is not inside a try-block; an unexpected exception "
        "would abort the pipeline."
    )
    except_match = re.search(r"except\s+(?:Exception|\w*Error)", post_window)
    assert except_match, (
        f"No `except Exception` follows _step_finviz_fetch; window: "
        f"{post_window[:300]}"
    )
    block_start = except_match.end()
    block = post_window[block_start: block_start + 400]
    assert "log.warning" in block or "log.error" in block, (
        f"Except block following _step_finviz_fetch does not log: {block[:300]}"
    )


def test_pipeline_run_cli_calls_apply_overrides_before_runner() -> None:
    """Plan §A.11 Task 2.5 - the `swing pipeline run` CLI body MUST call
    `apply_overrides()` on cfg before invoking the pipeline runner, so
    `[integrations.finviz]` user-config values (token, screen_query)
    propagate to the child process when the web layer spawns the CLI.

    Source-text inspection over runtime CliRunner: the runtime path requires
    a fully-provisioned DB, lease state, fetcher fixtures, etc. before
    `_step_finviz_fetch` is reachable, and any failure earlier in the
    pipeline (which is unrelated to the propagation contract being tested)
    would mask the discriminator. Source-text inspection pins the contract
    directly: `apply_overrides` is called in the command body, before the
    pipeline-runner call.

    Discriminating: if a future refactor removes `apply_overrides(...)` from
    the CLI body (or moves it after `run_pipeline(...)`), this test fails
    with a clear message.
    """
    from swing import cli as cli_module

    src = inspect.getsource(cli_module)
    # Locate the `swing pipeline run` Click command body. The function name
    # is `pipeline_run_cmd` per swing/cli.py.
    fn_match = re.search(r"def\s+pipeline_run_cmd\s*\(", src)
    assert fn_match, "pipeline_run_cmd function not found in swing.cli"
    body_start = fn_match.end()
    # Conservatively bound the body to the next top-level `@` decorator or
    # `def ` at column 0 (which marks the next function definition).
    next_fn = re.search(r"\n(?:@|def\s)", src[body_start:])
    body_end = body_start + (next_fn.start() if next_fn else len(src) - body_start)
    body = src[body_start:body_end]

    apply_idx = body.find("apply_overrides")
    runner_idx_a = body.find("run_pipeline(")
    runner_idx_b = body.find("run_pipeline_internal(")
    # Whichever runner symbol the CLI uses, take the first non-(-1) match.
    candidate_indices = [i for i in (runner_idx_a, runner_idx_b) if i > -1]
    assert candidate_indices, (
        f"Neither run_pipeline() nor run_pipeline_internal() found in "
        f"pipeline_run_cmd body: {body[:600]}"
    )
    runner_idx = min(candidate_indices)

    assert apply_idx > -1, (
        "apply_overrides() is not called in the `swing pipeline run` CLI body. "
        "User-config [integrations.finviz] values will NOT propagate when web "
        "spawns the CLI subprocess. See plan §A.11 Task 2.5."
    )
    assert apply_idx < runner_idx, (
        f"apply_overrides() (offset {apply_idx}) must precede the pipeline "
        f"runner call (offset {runner_idx}); otherwise overrides are applied "
        f"too late to take effect. Body excerpt: {body[:600]}"
    )
