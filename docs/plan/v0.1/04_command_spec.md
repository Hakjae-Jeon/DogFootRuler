
# 명령 스펙 (v0.1)
작성일: 2026-03-01 14:00:16

## 프로젝트
/project_create <name>
/project_use <name>
/project_list

## 작업
/status
/diff <task_id>
/apply <task_id>
/commit <task_id> <msg>
/merge <task_id>

## 정책 동작 요약
- Root 외부 수정 금지
- forbidden_subpaths 항상 차단
- allowed_subpaths 설정 시 해당 경로만 수정 가능
