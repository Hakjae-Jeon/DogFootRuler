# 2. 기능 요구사항서 (Functional Requirements) — DogFootRuler v0.1

## 1) 범위(Scope)
DogFootRuler는 Telegram 메시지를 입력으로 받아, WSL2 상에서 Codex CLI를 실행하고 결과를 Telegram으로 반환하는 자동화 봇이다.

## 2) 사용자 역할(Role)
- Owner(1인): 시스템을 사용하는 단일 사용자(본인). allowlist로 제한.

## 3) 입력/출력(I/O)
### 입력
- Telegram 메시지
  - 슬래시 명령: `/ping`, `/status`, `/diff <id>`, ...
  - 자연어: 작업 지시(“이 레포 구조 요약해줘” 등)

### 출력
- Telegram 텍스트 응답(짧은 요약)
- Telegram 파일 첨부(로그, patch, zip)
- 로컬 아카이브: `runs/<task_id>/...`

## 4) 기능 요구사항 (FR)

### FR-1. 인증/권한 (Allowlist)
- FR-1.1: `ALLOWED_USER_IDS`에 포함된 사용자만 실행 권한을 가진다.
- FR-1.2: allowlist에 없는 사용자의 메시지는 무시하거나 “권한 없음”을 반환한다.
- FR-1.3: 그룹 채팅 사용 시에도 동일하게 사용자 ID 기반으로 제한한다.

### FR-2. 메시지 라우팅
- FR-2.1: 메시지가 `/`로 시작하면 시스템 명령으로 처리한다.
- FR-2.2: 그 외 메시지는 “자연어 작업 요청”으로 간주해 Task를 생성한다.
- FR-2.3: 자연어 요청은 기본적으로 SAFE 모드로 실행한다.

### FR-3. Task 생성 및 식별자
- FR-3.1: 자연어 요청마다 고유한 `task_id`를 생성한다.
- FR-3.2: task_id는 시간+랜덤(예: `YYYYMMDD-HHMMSS-xxxxxx`) 형식을 권장한다.
- FR-3.3: task_dir = `runs/<task_id>/`에 모든 아티팩트를 저장한다.

### FR-4. 실행 큐 및 동시성
- FR-4.1: 기본은 단일 워커 큐(동시 실행 1개)로 구현한다.
- FR-4.2: 새 작업이 들어오면 QUEUED 상태로 쌓이고 순차 처리한다.
- FR-4.3: /status로 현재 RUNNING/QUEUED를 확인 가능해야 한다.

### FR-5. Codex 실행(구독 기반)
- FR-5.1: 봇은 subprocess로 `codex exec "<prompt>"`를 호출한다.
- FR-5.2: 실행 디렉토리는 레포 루트이며 Git repo 체크를 통과해야 한다.
- FR-5.3: Codex 출력(stdout/stderr)을 캡처하고 runs에 저장한다.
- FR-5.4: 기본 sandbox/read-only를 유지한다(변경은 /apply 승인 후).

### FR-6. Git 연동
- FR-6.1: 각 Task는 기본적으로 새 브랜치에서 실행된다(권장: `dfr/task/<task_id>`).
- FR-6.2: /diff 명령은 `git diff`를 patch로 만들어 반환한다.
- FR-6.3: /commit 명령은 커밋을 생성한다(커밋 메시지 입력 필수).
- FR-6.4: /merge 명령은 main으로 머지한다(항상 수동 승인).

### FR-7. 리포팅(요약/첨부)
- FR-7.1: 결과는 “짧은 요약”을 텔레그램 메시지로 보낸다.
- FR-7.2: 결과가 길면 파일(예: summary.md, stdout.log, diff.patch)을 첨부한다.
- FR-7.3: 응답에는 최소 다음을 포함한다:
  - task_id, 성공/실패, 작업 브랜치, 다음 액션 힌트(/diff, /logs 등)

### FR-8. 시스템 명령 세트
- FR-8.1: `/ping` → “pong”
- FR-8.2: `/help` → 사용법 출력
- FR-8.3: `/status` → 현재 상태(RUNNING/QUEUED/최근 task)
- FR-8.4: `/logs <task_id>` → stdout/stderr 파일 제공
- FR-8.5: `/diff <task_id>` → diff.patch 제공
- FR-8.6: `/apply <task_id>` → SAFE 결과 기반 변경 수행(또는 apply 모드 재실행)
- FR-8.7: `/commit <task_id> "<msg>"` → 커밋 생성
- FR-8.8: `/merge <task_id>` → main 머지(실패 시 롤백 전략 필요)
- FR-8.9: `/cancel <task_id>` → 실행 중 취소 시도(가능 범위)

### FR-9. 오류 처리
- FR-9.1: codex 실행 실패 시 FAILED로 기록, stderr 첨부 제공
- FR-9.2: git 에러(충돌/dirty) 시 사용자가 이해할 메시지 제공
- FR-9.3: Telegram 전송 실패 시 로컬에 결과를 남기고 재시도 옵션 제공(후속)

## 5) 비기능 요구사항 (NFR)
- NFR-1: 보안 — 토큰/키/개인정보는 텔레그램으로 노출하지 않는다(마스킹).
- NFR-2: 신뢰성 — 실패해도 아카이브가 남고 원인 파악 가능해야 한다.
- NFR-3: 재현성 — 동일 task_dir로 재실행 가능해야 한다.
- NFR-4: 관측성 — stdout/stderr/메타 저장, 상태 조회 지원.
- NFR-5: 유지보수성 — 모듈 분리(telegram, worker, git, codex, reporter).
