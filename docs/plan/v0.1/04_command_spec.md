
# 명령 스펙 (v0.1)
작성일: 2026-03-01 14:00:16

## 프로젝트
/project_create <name>
/project_use <name>
/project_list

- `/project_use`는 active_project만 변경하며, 이미 생성된 task의 project 바인딩은 변경하지 않는다.

## 작업
/status
/diff <task_id>
/apply <task_id>
/commit <task_id> <msg>
/merge <task_id>

- 모든 작업 명령은 task meta에 저장된 project_root를 기준으로 수행한다.
- active_project가 바뀌어도 기존 task의 후속 명령 대상은 바뀌지 않는다.

## 정책 동작 요약
- Root 외부 수정 금지
- forbidden_subpaths 항상 차단
- allowed_subpaths 설정 시 해당 경로만 수정 가능
