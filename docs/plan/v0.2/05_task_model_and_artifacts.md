# 5. Task Model & Artifacts — v0.2

## Task ID
- 형식: `YYYYMMDD-HHMMSS-<6hex>`

## Status
- 기본:
  - `QUEUED`
  - `RUNNING`
  - `APPLIED`
  - `FAILED`
  - `CANCELED`
- 선택 후속:
  - `COMMITTED`

## runs 디렉토리 구조
runs/
  <project_name>/
    <task_id>/
      request.txt
      meta.json
      stdout.log
      stderr.log
      summary.md
      diff.patch (optional, internal archive)
      artifacts.zip (optional)

## meta.json 예시 필드
- `task_id`
- `project_name`
- `project_root`
- `created_at`, `started_at`, `finished_at`
- `status`
- `session_mode: resume | new`
- `return_code`
- `changed_files`
- `diff_exists`
- `notes`

## summary.md 원칙
- 짧은 실행 결과 요약
- 무엇을 했는지 / 실패 원인 / 후속 액션
- `project_name`, `session_mode`, `status` 명시 권장
