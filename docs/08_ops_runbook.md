# 8. Ops Runbook (운영 가이드)

## 1) 실행
- WSL에서 venv 활성화 후:
  - `python bot/main.py`

## 2) 상시 실행(권장)
- tmux 사용:
  - `tmux new -s dfr`
  - 봇 실행
  - `Ctrl+b` → `d`로 detach

## 3) 로그 확인
- runs/<task_id>/stdout.log, stderr.log
- 봇 프로세스 표준 로그는 별도 파일로 리다이렉트 권장

## 4) 장애/트러블슈팅
- 봇이 응답 안 함:
  - 토큰(.env) 확인
  - 네트워크/방화벽 확인
  - polling 충돌(동일 토큰 프로세스 2개 실행) 여부 확인

- codex 에러:
  - Git repo 체크: `git status`
  - trusted directory 에러: 레포 루트에서 실행/또는 옵션 검토
  - 로그인 만료: `codex` 실행 후 재로그인

## 5) 백업/정리
- runs/는 주기적으로 zip 백업 가능
- 보관 기간 정책으로 자동 삭제 옵션 도입
