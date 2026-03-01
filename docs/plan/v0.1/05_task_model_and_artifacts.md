
# Task / 아카이브 모델
작성일: 2026-03-01 14:00:16

## Task 상태 흐름
QUEUED → RUNNING → READY_TO_APPLY → APPLIED → COMMITTED → MERGED / FAILED

## runs/<task_id>/ 구조
- request.txt
- meta.json
- stdout.log
- stderr.log
- summary.md
- diff.patch
