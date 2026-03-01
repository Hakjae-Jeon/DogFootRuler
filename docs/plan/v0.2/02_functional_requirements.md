# 2. 기능 요구사항서 (Functional Requirements) — DogFootRuler v0.2

## 1) 범위
v0.2는 다중 프로젝트 관리와 Codex 세션 연속성(`resume|new`)을 추가한다. 현재 제품 방향은 자동 반영이며 `/diff`, `/apply`, task branch 플로우는 범위에서 제외한다.

## 2) 역할
- Owner 1인. allowlist 기반.

## 3) 입력/출력
### 입력
- Telegram 슬래시 명령
- 자연어 작업 지시

### 출력
- Telegram 텍스트 응답
- `/logs`를 통한 아카이브 전달
- 로컬 아카이브: `runs/<project>/<task_id>/...`

## 4) 기능 요구사항

### FR-1. 인증/권한
- FR-1.1: allowlist 사용자만 실행 가능
- FR-1.2: 비허용 사용자는 거부 메시지

### FR-2. 메시지 라우팅
- FR-2.1: `/`로 시작하면 시스템 명령
- FR-2.2: 그 외는 자연어 작업 요청
- FR-2.3: 자연어 요청은 active project에서 실행

### FR-3. Project Registry / Active Project
- FR-3.1: 프로젝트 목록 저장/조회
- FR-3.2: `/project_use <name>`로 active project 설정
- FR-3.3: active project가 유효하지 않으면 실행 대신 복구 안내
- FR-3.4: 프로젝트는 base root 하위에서만 관리

### FR-4. 프로젝트 생성 — git clone
- FR-4.1: `/project_clone <name> <repo_url> [branch]`
- FR-4.2: clone 성공/실패 결과를 안내
- FR-4.3: 이름 충돌 시 거부
- FR-4.4: clone 후 선택 가능하게 안내

### FR-5. 프로젝트 제거
- FR-5.1: `/project_remove <name>`
- FR-5.2: 기본은 안전 모드(trash 이동 권장)
- FR-5.3: active project 제거 시 active 해제
- FR-5.4: 진행 중 task가 있는 프로젝트 제거 정책 정의

### FR-6. 프로젝트 루트 변경
- FR-6.1: `/project_root show|set <path> [--migrate]`
- FR-6.2: set 시 경로 유효성 검사
- FR-6.3: migrate 옵션 시 기존 프로젝트 이동 가능
- FR-6.4: 변경 후 registry/active 재검증

### FR-7. Task 생성 및 식별자
- FR-7.1: 자연어 요청마다 고유 `task_id` 생성
- FR-7.2: 형식은 `YYYYMMDD-HHMMSS-xxxxxx`
- FR-7.3: `runs/<project>/<task_id>/`에 아티팩트 저장

### FR-8. 실행 큐
- FR-8.1: 단일 워커 큐
- FR-8.2: 새 작업은 `QUEUED`
- FR-8.3: `/status`로 `RUNNING`, `QUEUED`, 최근 완료 표시

### FR-9. Codex 실행 — 세션 정책
- FR-9.1: 기본은 동일 프로젝트 resume
- FR-9.2: `/new <prompt>`는 new session 실행
- FR-9.3: stdout/stderr 캡처 후 runs 저장
- FR-9.4: 실행 디렉토리는 active project repo root
- FR-9.5: task meta에 `session_mode: resume|new` 저장

### FR-10. Git 연동
- FR-10.1: Codex 변경은 현재 프로젝트 작업 트리에 자동 반영
- FR-10.2: `diff.patch`는 내부 아카이브 용도로 생성할 수 있다
- FR-10.3: `/commit <task_id> "<msg>"`는 현재 작업 트리 변경을 커밋한다
- FR-10.4: task branch 생성/checkout은 기본 플로우에 포함하지 않는다

### FR-11. 리포팅
- FR-11.1: 기본 텔레그램 응답은 Codex output 중심
- FR-11.2: 긴 출력은 여러 메시지로 분할
- FR-11.3: 상세 로그는 `/logs <task_id>`
- FR-11.4: meta에는 최소 `task_id`, `project`, `session_mode`, `status`, `return_code` 기록

### FR-12. 시스템 명령
- FR-12.1: `/ping`
- FR-12.2: `/help`
- FR-12.3: `/status`
- FR-12.4: `/logs <task_id>`
- FR-12.5: `/commit <task_id> "<msg>"`
- FR-12.6: `/cancel <task_id>`
- FR-12.7: `/project_list`
- FR-12.8: `/project_use <name>`
- FR-12.9: `/project_clone <name> <repo_url> [branch]`
- FR-12.10: `/project_remove <name> [--force]`
- FR-12.11: `/project_root show|set <path> [--migrate]`
- FR-12.12: `/new <prompt>`

### FR-13. 오류 처리
- FR-13.1: Codex non-zero, timeout, error는 `FAILED`
- FR-13.2: active project 유실 시 복구 안내
- FR-13.3: clone/remove/root 변경 실패 시 원인 안내
- FR-13.4: request, stdout/stderr, summary는 마스킹 규칙 적용

## 5) 비기능 요구사항
- NFR-1: 민감정보 마스킹
- NFR-2: 실패해도 아카이브 유지
- NFR-3: task_dir만으로 사후 분석 가능
- NFR-4: 모듈 분리 유지
