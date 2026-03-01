# 8. Ops Runbook (운영 가이드) — v0.2

## 1) 실행
- WSL에서:
  - `python bot/main.py`
  - 또는 `.venv/bin/python bot/main.py`

## 2) 디렉토리 개념
- project base root: 모든 프로젝트의 상위 폴더
- project root: 개별 git repo
- runs: 프로젝트별 task 아카이브

## 3) 기본 운영 흐름
1. `/project_clone` 또는 기존 프로젝트 준비
2. `/project_use <name>`
3. 자연어 작업 요청(기본 resume)
4. 필요 시 `/new <prompt>`
5. 결과는 Telegram의 Codex output으로 확인
6. 필요 시 `/logs`, `/commit`

## 3-1) CLI 운영
- `python dogfoot_cli.py --system-config config/system.yaml project list`
- `python dogfoot_cli.py --system-config config/system.yaml project clone <name> <repo_url>`
- `python dogfoot_cli.py --system-config config/system.yaml project root show`
- `python dogfoot_cli.py --system-config config/system.yaml project root set <path> --migrate`

## 4) 상시 실행
- `tmux new -s dfr`
- 봇 실행
- detach

## 5) 트러블슈팅
- 응답 없음:
  - 토큰 확인
  - polling 중복 확인
- 프로젝트 문제:
  - active project 유실 시 `/project_list`, `/project_use`
  - stale active project는 startup/status/task 진입 시 자동 해제될 수 있음
  - clone 실패 시 URL/네트워크 확인
- Codex 문제:
  - `git status`
  - 로그인 만료 시 재로그인

## 6) 백업/정리
- runs는 주기적 백업 가능
- 보관 기간 정책은 선택
