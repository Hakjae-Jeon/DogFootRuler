# 5. Task Model & Artifacts

## Task ID
- 형식 권장: `YYYYMMDD-HHMMSS-<6hex>`
- 예: `20260228-154012-a1b2c3`

## Status
- QUEUED / RUNNING / DONE / FAILED / CANCELED
- 선택 확장: READY_TO_APPLY / APPLIED / COMMITTED / MERGED

## runs 디렉토리 구조
runs/
  <task_id>/
    request.txt
    meta.json
    stdout.log
    stderr.log
    summary.md
    diff.patch (optional)
    artifacts.zip (optional)

## meta.json 예시
- task_id
- created_at / started_at / finished_at
- status
- branch
- codex_cmd
- return_code
- notes(오류 등)

## summary.md 원칙
- 텔레그램 본문은 짧게
- 상세는 summary.md로 제공
- “무엇을 했는지 / 무엇이 바뀌었는지 / 다음 단계” 3요소 포함
