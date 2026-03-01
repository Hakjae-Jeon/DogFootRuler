# 3. 개발순서 (Development Plan) — DogFootRuler v0.2

## 원칙
- 1 PR = 1 기능 단위
- 현재 제품 방향 유지: 자동 반영, branch 플로우 없음, `/diff` 없음, `/apply` 없음
- 매 PR마다 실행 방법과 DoD 포함

---

## PR1 — Session Policy 기본화
### 작업
- 기본 자연어 실행을 `resume`으로 명시
- `/new <prompt>` 추가
- task meta에 `session_mode` 기록

### DoD
- 동일 프로젝트 연속 실행 시 `resume`
- `/new` 실행 시 `session_mode=new`

---

## PR2 — Telegram/CLI Active Project UX 정리
### 작업
- `/status`에 active project와 session 관련 정보 보강
- active 미설정/유실 시 자연어 실행 가드 정리
- 필요 시 `/project_info` 추가 검토

### DoD
- active project 설정/조회 가능
- active 없으면 안내 후 종료

---

## PR3 — git clone 프로젝트 생성
### 작업
- `/project_clone <name> <repo_url> [branch]`
- clone 결과 리포팅
- name 충돌 처리

### DoD
- 공개 repo clone 성공
- clone 후 해당 repo에서 task 실행 가능

---

## PR4 — 프로젝트 제거
### 작업
- `/project_remove <name> [--force]`
- 기본은 안전 모드(trash 이동)
- active project 제거 시 active 해제
- 진행 중 task 존재 시 제거 정책 적용

### DoD
- 제거 후 목록에서 사라짐
- 제거된 active project는 자동 해제됨

---

## PR5 — 프로젝트 루트 변경
### 작업
- `/project_root show`
- `/project_root set <path> [--migrate]`
- 경로 유효성 검증
- migrate 시 registry 갱신

### DoD
- 잘못된 경로는 거부
- 루트 변경 후 기존 프로젝트 접근 가능

---

## PR6 — Active Project 유실 복구
### 작업
- startup 및 실행 시 active project 존재 재검증
- 유실 시 active 자동 해제
- 사용자 복구 안내 정리

### DoD
- active project 폴더 삭제 후에도 봇이 죽지 않음
- `/project_list -> /project_use`로 복구 가능

---

## PR7 — 테스트/문서 정리
### 작업
- v0.2 시나리오 통합 테스트 추가
- session/project 관련 문서 최신화

### DoD
- test plan 시나리오 재현 가능
