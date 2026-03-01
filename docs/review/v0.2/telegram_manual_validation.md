# DogFootRuler v0.2 Telegram Manual Validation

- Date: 2026-03-02
- Target: `master` after `2716548`
- Scope: Telegram bot manual validation for the current auto-apply workflow

## Prerequisites
- `config/telegram.yaml` exists and has a valid bot token
- `config/allowed_users.yaml` includes the tester's Telegram user id
- `config/system.yaml` exists
- Codex CLI login is already valid on the machine
- Bot is restarted after the latest code update
- Recommended start command:
  - `.venv/bin/python bot/main.py`

## Validation Goal
- Confirm that Telegram commands work against the current `v0.2` design
- Confirm that natural-language tasks run in the active project
- Confirm that successful changes are auto-applied without `/apply`
- Confirm that active project recovery and session policy behave as designed

## Scenario 1: Startup and Basic Commands
1. Start the bot.
2. Send `/ping`.
3. Send `/help`.
4. Send `/status`.

### Expected
- Bot process stays alive in polling mode
- `/ping` replies with `pong`
- `/help` lists current commands
- `/status` shows:
  - `ACTIVE_PROJECT`
  - `PROJECT_ROOT` when active project exists
  - `LATEST_SESSION`

### Failure Signals
- Bot exits immediately
- `/status` returns traceback-like text
- help output still mentions `/diff`

## Scenario 2: Project Create and Use
1. Send `/project_create tg_manual python`
2. Send `/project_use tg_manual`
3. Send `/project_list`
4. Send `/status`

### Expected
- Create response includes project root path
- Use response confirms `active_project` change
- `/project_list` shows `tg_manual *`
- `/status` shows `ACTIVE_PROJECT: tg_manual`

### Local Verification
- `projects/tg_manual/` exists
- `projects/tg_manual/.git/` exists
- `projects/tg_manual/config/project.yaml` exists
- `projects/tg_manual/runs/` exists

## Scenario 3: Auto-Apply Task
1. Ensure `tg_manual` is active.
2. Send:
   - `src/main.py를 수정해서 실행하면 Hello Telegram을 출력하게 해줘`
3. Wait for completion message.

### Expected
- Telegram sends Codex output text directly
- No `/apply` step is needed
- Local file is changed immediately:
  - `projects/tg_manual/src/main.py`
- Running the file prints the new value

### Local Verification
- `python3 projects/tg_manual/src/main.py`
- output should match the requested change

### Failure Signals
- Telegram says work is done but file content is unchanged
- task remains `RUNNING`
- bot asks for `/apply`

## Scenario 4: Session Resume and New
1. In the same active project, send:
   - `방금 만든 출력문을 소문자로 바꿔줘`
2. After completion, inspect the latest task meta in:
   - `projects/tg_manual/runs/<task_id>/meta.json`
3. Send:
   - `/new src/main.py를 다시 대문자로 바꿔줘`
4. Inspect the new task meta.

### Expected
- The normal follow-up task stores:
  - `session_mode=resume`
- The `/new` task stores:
  - `session_mode=new`
- New task meta should keep `session_id`

### Failure Signals
- Follow-up natural task always uses `new`
- `/new` still resumes previous session

## Scenario 5: Logs Command
1. After any completed task, send:
   - `/logs <task_id>`

### Expected
- Bot sends a zip archive
- Archive includes:
  - `meta.json`
  - `stdout.log`
  - `stderr.log`
  - `summary.md`
  - `request.txt`

### Failure Signals
- `/logs` cannot locate an existing task
- zip is empty

## Scenario 6: Commit Command
1. After a successful auto-applied task, send:
   - `/commit <task_id> test commit from telegram`

### Expected
- Bot replies with a commit hash
- Task meta becomes `COMMITTED`
- `git log --oneline -1` in the project shows the commit message

### Failure Signals
- Bot says `/apply` is required
- commit runs on a non-main branch

## Scenario 7: Active Project Recovery
1. Prepare an active project, for example `tg_manual`.
2. Delete the active project directory locally while the bot is still running.
3. Send `/status`
4. Send a natural-language task
5. Send `/project_list`

### Expected
- `/status` reports the active project was cleared
- Natural-language task does not run
- Recovery guidance is shown:
  - `/project_list`
  - `/project_use <name>`
- `/project_list` no longer marks the deleted project as active

### Failure Signals
- Bot crashes
- stale active project remains set
- task is still queued against the missing project

## Scenario 8: Project Clone
1. Send:
   - `/project_clone tg_clone <repo_url>`
2. Send:
   - `/project_use tg_clone`
3. Send:
   - `현재 프로젝트 구조를 짧게 설명해줘`

### Expected
- Clone succeeds
- Active project can switch to the cloned repo
- Natural-language task runs in that repo

### Failure Signals
- clone succeeds but project cannot be used
- clone result lacks `config/project.yaml` or `runs/`

## Scenario 9: Project Remove
1. Send `/project_remove tg_clone`
2. Send `/project_list`
3. If testing force mode, create a running task and send:
   - `/project_remove tg_clone --force`

### Expected
- Default remove moves the project to `.trash`
- Removed active project is cleared
- `--force` cancels queued/running tasks for that project before removal

### Failure Signals
- active project remains set after removal
- default remove permanently deletes instead of trashing

## Scenario 10: Project Root Commands
1. Send `/project_root show`
2. Send `/project_root set /tmp/dfr-projects`
3. Send `/project_root show`
4. Optionally send:
   - `/project_root set /tmp/dfr-projects-2 --migrate`

### Expected
- `show` returns the current base root
- `set` updates the base root
- `--migrate` reports migrated project names

### Failure Signals
- invalid path silently succeeds
- projects disappear without active project cleanup

## Pass Criteria
- All command responses match the current auto-apply design
- No response mentions `/diff`
- No successful task requires `/apply`
- Active project recovery works without crashing the bot
- At least one task is auto-applied and committed successfully
