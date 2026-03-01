
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

## meta.json 필수 필드
- task_id
- status
- project_name
- project_root
- created_at
- request

## Task-Project 바인딩 규칙
- task는 생성 시점의 project_name / project_root를 스냅샷으로 저장한다.
- QUEUED / RUNNING / 완료 상태와 무관하게 후속 명령은 항상 이 바인딩을 따른다.
- active_project 변경은 기존 task의 실행 컨텍스트를 바꾸지 않는다.
