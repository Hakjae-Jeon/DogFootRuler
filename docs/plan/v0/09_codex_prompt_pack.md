# 9. Codex Prompt Pack — “문서 읽고 PR 단위로 구현”

> 아래 프롬프트들을 Codex에 그대로 붙여넣고 진행하세요.
> 원칙: 1 PR = 1 기능, 각 PR마다 DoD 체크리스트를 통과해야 다음 PR로 이동.

---

## Prompt 0 — 프로젝트 컨텍스트 주입(최초 1회)
너는 DogFootRuler 프로젝트를 구현한다.
- 목적: Telegram을 통해 자연어로 명령을 받으면 WSL에서 `codex exec`를 subprocess로 실행하고, 결과를 요약/로그/patch 형태로 Telegram으로 반환한다.
- 문서: docs/01~08을 기준으로 구현하라.
- 규칙:
  - 1 PR = 1 기능
  - 각 PR마다 DoD를 만족하는 실행 방법(명령)과 검증 체크리스트를 README에 업데이트하라.
  - 기본 SAFE 정책: 승인(/apply, /commit, /merge) 없이는 main을 변경하지 마라.

이제 PR1부터 진행하라.

---

## Prompt PR1 — Telegram Bot Skeleton
PR1 목표:
- python-telegram-bot 기반 polling 봇 구현
- allowlist(user_id) 적용
- /ping /help /status(더미)
- 자연어 메시지를 받으면 task_id를 만들어 “queued” 응답만 하고 runs/<id>/request.txt로 저장

DoD:
- 텔레그램에서 /ping → pong
- allowlist 외 사용자는 거부
- 자연어 메시지 1건 → runs 생성 확인

---

## Prompt PR2 — Queue & Task Store 강화
PR2 목표:
- 단일 워커 큐로 순차 처리
- task 상태 저장(meta.json)
- /status에서 RUNNING/QUEUED 표시
- 실패 시 FAILED 기록

DoD:
- 메시지 3건을 연속으로 보내도 순서대로 처리됨
- 각 task_dir에 meta.json이 생성됨

---

## Prompt PR3 — Codex Runner 연결
PR3 목표:
- 워커가 `codex exec "<prompt>"`를 subprocess로 실행
- stdout/stderr 캡처 후 runs에 저장
- summary.md 생성
- 텔레그램으로 요약 전송(길면 파일 첨부)

DoD:
- “say hi in one line” 자연어 → 결과가 텔레그램으로 옴
- stdout.log 저장됨

---

## Prompt PR4 — Git Ops: Branch + Diff
PR4 목표:
- task 시작 시 새 브랜치 생성(dfr/task/<task_id>)
- /diff <id>가 diff.patch를 전송
- 변경이 없으면 “변경 없음” 안내

DoD:
- 파일 변경 작업 후 /diff로 patch 확인 가능

---

## Prompt PR5 — Approval Flow
PR5 목표:
- /apply로 변경 수행(정책 구현)
- /commit /merge 구현
- merge는 항상 명시 승인

DoD:
- 승인 없이 main 변경 없음
- commit/merge 성공 또는 충돌 시 안전 중단
