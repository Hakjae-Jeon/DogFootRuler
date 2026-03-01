
# 기능 요구사항서 (v0.1)
작성일: 2026-03-01 14:00:16

## 1. 프로젝트 관리
- project_base_root 설정 필수
- 프로젝트 생성(create)
- 프로젝트 선택(use)
- 프로젝트 목록 조회(list)
- active_project 변경은 이후 생성되는 새 task에만 적용

## 2. 정책
- Project Root 외부 접근 차단
- forbidden_subpaths 항상 차단
- allowed_subpaths 설정 시 잠금 모드 활성화

## 3. Task 관리
- task_id 기반 작업 추적
- runs/<task_id> 아카이브 구조 유지
- 각 task는 생성 시점의 project_name / project_root를 meta에 고정 저장
- QUEUED / RUNNING task는 active_project 변경의 영향을 받지 않음
- 후속 명령(/diff, /apply, /commit, /merge)은 task에 저장된 project 기준으로만 동작

## 4. Git 연동
- diff / apply / commit / merge 명령 지원
- 반영 전 정책 재검증 필수
- 정책 위반 시 git 반영은 중단되고 FAILED 처리
