
# 운영 가이드 (Runbook)
작성일: 2026-03-01 14:00:16

## 시작 전 체크리스트
- system.yaml 존재
- active_project 유효
- runs 디렉토리 생성 확인
- task 실행 전 task meta의 project_root가 유효한지 확인

## CLI 빠른 검증
- 프로젝트 생성:
  - `.venv/bin/python dogfoot_cli.py --system-config config/system.yaml project create demo --template python`
- 활성 프로젝트 선택:
  - `.venv/bin/python dogfoot_cli.py --system-config config/system.yaml project use demo`
- 프로젝트 목록 확인:
  - `.venv/bin/python dogfoot_cli.py --system-config config/system.yaml project list`

## 정책 위반 대응
- FAILED 상태 확인
- 로그 분석 후 정책 수정 또는 코드 수정
- hard deny / root escape / allowed_subpaths 위반은 설정보다 차단이 우선

## 운영 모드 전환
- allowed_subpaths 설정 시 잠금 모드 활성화

## active_project 전환 규칙
- active_project 전환은 새 task부터 적용한다.
- 이미 생성된 task는 meta에 저장된 project_root 기준으로 계속 처리한다.

## 현재 검증 범위
- automated:
  - unit / integration / interface tests
- manual:
  - Telegram polling 실검증은 별도 수행 권장
