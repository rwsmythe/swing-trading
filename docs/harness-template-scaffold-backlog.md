# Harness-template scaffold — germination backlog

**Owner:** CHARC (swing), as the scaffold architect retaining the design record (the scaffold itself is accepted + static at harness-template `master @ d8ad5c9`; there is no active scaffold orchestrator).
**Purpose:** findings surfaced AFTER accept — chiefly during the **first real germination (coa-chess, started 2026-06-16)** — that improve the SCAFFOLD so future germinations don't repeat them. **Deferred-correction:** the operator reviews + sequences a fix pass later; coa-chess's own CHARC may apply the fixes to its copy in the meantime.
**How fixes land:** a future swing-commissioned scaffold-revision pass edits harness-template (the template); coa-chess pulls or re-applies as its CHARC sees fit. Append items as germination surfaces them.

---

| # | Item | Detail / fix | Where (in the scaffold) | Status |
|---|---|---|---|---|
| **B-1** | README CHARC-launch is abstract while the orchestrator command is concrete | The instantiate section spells out a copy-pasteable `launch_role.ps1 -Role orchestrator` (step 5) but states the FIRST step ("launch CHARC", step 3) abstractly with no concrete command → a human grabs the concrete command and launches the orchestrator **prematurely** (into an undefined app — no `APPLICATION.md`, no cells, no review-gate, no commissioned arc). **Fix:** put the concrete copy-paste command on the step you do FIRST (CHARC launch); de-emphasize the orchestrator command to step 5 where it belongs. | `README.md` (§How to instantiate) | OPEN |
| **B-2** | Docs print `launch_role.ps1 ...` without the PowerShell `.\scripts\` form | PowerShell won't run a current-dir script by bare name, and the launcher is in `scripts/` → `The term 'launch_role.ps1' is not recognized`. Every doc showing the invocation should use `.\scripts\launch_role.ps1 ...` (the working PS form). | `README.md`, `docs/charc-bootstrap.md`, any launcher-invocation doc | OPEN |
| **B-3** | CHARC launches at effort `xhigh`; operator wants `max` | The seam-4 launcher default (`$LaunchArgs`) starts the CHARC role at reasoning effort `xhigh`; the operator wants CHARC to start at **`max`**. **Fix:** in `scripts/launch_role.ps1` `$LaunchArgs`, set the CHARC effort `xhigh` → `max` (verify the exact current flag + the preflight `--help` check at fix time). Confirm whether orchestrator/other roles' effort defaults change too (operator's call). | `scripts/launch_role.ps1` (`$LaunchArgs`, seam 4) | OPEN |

---

*Provenance: coa-chess germination, 2026-06-16 (B-1/B-2 from the orchestrator-before-CHARC launch + the `.\scripts\` PATH error; B-3 operator-observed). This list is append-as-found.*
