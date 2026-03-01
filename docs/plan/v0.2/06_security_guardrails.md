# 6. Security & Guardrails — v0.2

## 1) Allowlist
- allowlist 사용자만 실행

## 2) 자동 반영 정책
- 변경은 정책 검사 후 현재 작업 트리에 자동 반영
- `/apply` 승인 게이트는 사용하지 않음
- 후속 수동 단계는 `/commit`

## 3) 경로 고정
- 프로젝트는 base root 하위에서만 관리
- active project는 registry에 등록된 경로만 허용
- path traversal 금지

## 4) 프로젝트 관리 안전장치
- `/project_remove`는 기본적으로 안전 모드(trash) 권장
- active project 제거 시 active 자동 해제
- 진행 중 task가 있는 프로젝트 제거 정책 필요

## 5) 금지 행위
- 시스템 파일/계정 변경
- 임의 비밀 업로드
- 파괴적 명령
- 환경변수/토큰 출력

## 6) 비밀 마스킹
- request, stdout, stderr, summary는 저장/전송 시 마스킹
- `.env`, `secrets/` 등은 기본 접근 금지 권장

## 7) 데이터 보관
- runs는 로컬 저장
- 보관 기간 정책은 선택 사항
