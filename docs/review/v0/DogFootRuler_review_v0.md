# DogFootRuler Mini Project Review

Generated: 2026-03-01 05:14:35

------------------------------------------------------------------------

## 1. Current Implementation Status

### ✅ Documentation

-   docs/plan/v0/01_planning_design.md through docs/plan/v0/09_codex_prompt_pack.md
    cover planning/design, FRD, development sequencing, command spec, guardrails,
    testing, operations, and Codex prompt pack; all are structured and mostly complete.
-   README.md, requirements.txt, policy/01_logs.md exist.

### ✅ Telegram Bot (PR1\~PR2 + Partial PR5)

-   Allowlist-based access control (config/allowed_users.yaml)
-   Basic commands: /ping, /help, /status
-   Natural language → task creation
    -   runs/`<task_id>`{=html}/request.txt
    -   meta.json
-   TaskStore + single worker queue
-   Recovery of QUEUED tasks on startup

### ✅ Codex Execution (Partial Integration)

-   subprocess execution: codex exec "`<prompt>`{=html}"
-   stdout.log / stderr.log / summary.md saved
-   Timeout (180s) handling
-   /cancel support

### ✅ Git-related Commands (Structural Implementation)

-   /diff `<task_id>`{=html}
-   /logs `<task_id>`{=html}
-   /apply `<task_id>`{=html}
-   /commit `<task_id>`{=html} `<msg>`{=html}
-   /merge `<task_id>`{=html}

Overall: Structure is implemented up to PR1\~PR5 skeleton level.

------------------------------------------------------------------------

## 2. Critical Gaps & Risks

### ⚠️ A. Codex Not Running in Task Branch (Critical)

Issue: - Branch is created but not checked out before Codex execution. -
Codex may modify main branch directly.

Risks: - main branch pollution - diff may be empty - Approval-based flow
broken

Recommendation: - Before execution: 1) Check workspace clean 2) Checkout
task branch 3) Run Codex 4) Generate diff - Better: use git worktree per
task

------------------------------------------------------------------------

### ⚠️ B. No Automatic Completion Notification

Issue: - No Telegram push after task completion. - User must manually
check via /status and /logs.

Recommendation: - Store chat_id in task meta - Send summary
automatically after completion

------------------------------------------------------------------------

### ⚠️ C. runs/ Directory Path Not Anchored

Issue: - RUNS_DIR = Path("runs") - Location depends on execution
directory.

Recommendation: - Use REPO_ROOT / "runs"

------------------------------------------------------------------------

### ⚠️ D. Status Value Inconsistency

Issue: - Old states (DONE) vs new states (READY_TO_APPLY, etc.) -
Possible confusion in logs and analytics

Recommendation: - Define unified status enum - Add migration handling
for old meta files

------------------------------------------------------------------------

### ⚠️ E. Weak Secret Masking

Issue: - Regex only covers simple patterns like token/key/secret: - Does
not robustly cover YAML/JSON/env style secrets

Recommendation: - Add patterns for: - Bearer tokens - sk- prefixed
keys - ENV assignments - Optionally load known secrets and replace exact
matches

------------------------------------------------------------------------

## 3. Overall Assessment

Documentation: Strong\
Command Skeleton: Implemented\
Queue/Worker: Implemented\
Safety & Isolation: Incomplete

Current state: "Functionally working prototype, but not yet
production-safe approval pipeline."

------------------------------------------------------------------------

## 4. Minimum Required Fixes (Priority Order)

1.  Enforce task branch checkout before Codex execution\
2.  Add automatic Telegram completion push\
3.  Anchor runs directory to repo root\
4.  Standardize status states\
5.  Improve secret masking

After these fixes, the system can be considered v0.1 operationally safe.
