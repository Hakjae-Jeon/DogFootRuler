
# 기능 요구사항서 (v0.1)
작성일: 2026-03-01 14:00:16

## 1. 프로젝트 관리
- project_base_root 설정 필수
- 프로젝트 생성(create)
- 프로젝트 선택(use)
- 프로젝트 목록 조회(list)

## 2. 정책
- Project Root 외부 접근 차단
- forbidden_subpaths 항상 차단
- allowed_subpaths 설정 시 잠금 모드 활성화

## 3. Task 관리
- task_id 기반 작업 추적
- runs/<task_id> 아카이브 구조 유지

## 4. Git 연동
- diff / apply / commit / merge 명령 지원
- 반영 전 정책 재검증 필수
