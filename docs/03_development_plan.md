# 3. 개발순서 (Development Plan) — DogFootRuler v0.1

## 원칙
- 1 PR = 1 기능 단위
- 매 PR마다 “실행 커맨드 + 검증 체크리스트(DoD)” 포함
- MVP 성공 후 안전성/승인 플로우 강화

---

## Milestone 0 — Repo Bootstrap (0.5 day)
### 작업
- git init / README / docs 폴더
- Python venv 세팅 스크립트(또는 Makefile)
- `.env.example` 추가

### DoD
- 로컬에서 `python -m venv` / `pip install -r requirements.txt`로 실행 가능

---

## PR1 — Telegram Bot Skeleton (0.5 day)
### 작업
- BotFather 토큰으로 polling 연결
- allowlist(user_id) 적용
- `/ping`, `/help`, `/status(더미)` 구현
- 자연어 메시지 수신 시 “task 생성(더미)” 응답

### DoD
- 텔레그램에서 `/ping` → pong
- allowlist 외 사용자는 실행 불가
- 자연어 메시지 1건 → “task_id 생성됨” 응답

---

## PR2 — Task Store & Queue (1 day)
### 작업
- task_id 생성
- `runs/<task_id>/request.txt` 저장
- 상태(QUEUED/RUNNING/...) 저장(meta.json)
- 단일 워커 큐 구현
- `/status`에 RUNNING/QUEUED 표시

### DoD
- 메시지 3건 연속 보내면 큐로 쌓이고 순차 처리
- runs에 task별 폴더 생성 및 메타 저장

---

## PR3 — Codex Runner 연결 (1 day)
### 작업
- subprocess로 `codex exec "<prompt>"` 실행
- stdout/stderr 캡처 → runs 저장
- summary.md 생성(짧게)
- 텔레그램 결과 전송(길면 파일 첨부)
- Git repo 체크 통과(작업 디렉토리 고정)

### DoD
- 자연어 “say hi” → codex 결과가 텔레그램으로 반환됨
- stdout.log 저장됨
- 실패 시 stderr.log 첨부됨

---

## PR4 — Git Ops: Branch + Diff (1 day)
### 작업
- task 시작 시 브랜치 생성/체크아웃: `dfr/task/<task_id>`
- `/diff <task_id>`: `git diff`를 `diff.patch`로 생성/전송
- 작업 완료 후 브랜치 유지(사용자 승인 전)

### DoD
- 코드 변경이 생기는 작업 후 `/diff`로 patch 확인 가능

---

## PR5 — 승인 플로우: Apply/Commit/Merge (1~2 days)
### 작업
- SAFE 기본: 변경 전 “계획/제안” 중심
- `/apply <task_id>`로 변경 허용 모드 실행(또는 수정 실행)
- `/commit <task_id> "msg"` 구현
- `/merge <task_id>` 구현(충돌 처리 정책 포함)
- /merge 전에는 반드시 /diff 확인 유도

### DoD
- 안전하게 “승인 없이는 main 변경 없음”
- commit/merge는 명시 명령으로만 수행

---

## PR6 — 안정화 (지속)
- 취소(cancel) 개선
- 로그 zip 묶음 전송
- 비밀 마스킹 강화
- 장시간 실행 timeout
- 서비스화(systemd/tmux) 및 재부팅 자동 시작

---

## 구현 우선순위(요약)
1) PR1~PR3: Telegram ↔ Codex 실행 왕복  
2) PR4~PR5: Git + 승인 플로우  
3) PR6: 운영 안정화
