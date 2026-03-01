# DogFootRuler v0.2 텔레그램 수동 검증 시나리오

- 작성일: 2026-03-02
- 대상 기준: `master` / `fa834b5`
- 범위: 현재 자동 반영(auto-apply) 워크플로우 기준 Telegram 봇 수동 검증

## 1. 사전 조건
- `config/telegram.yaml` 이 존재하고 유효한 bot token이 설정되어 있어야 함
- `config/allowed_users.yaml` 에 검증자의 Telegram user id가 포함되어 있어야 함
- `config/system.yaml` 이 존재해야 함
- 로컬 머신에서 Codex CLI 로그인이 이미 유효해야 함
- 최신 코드 반영 후 봇을 재시작해야 함
- 권장 실행 명령:
  - `.venv/bin/python bot/main.py`

## 2. 검증 목표
- 현재 `v0.2` 설계 기준으로 Telegram 명령이 정상 동작하는지 확인
- 자연어 작업이 active project 기준으로 실행되는지 확인
- 성공한 변경이 `/apply` 없이 자동 반영되는지 확인
- active project 유실 복구와 session 정책이 의도대로 동작하는지 확인

## 3. 시나리오 1: 기동 및 기본 명령
1. 봇을 실행한다.
2. `/ping` 전송
3. `/help` 전송
4. `/status` 전송

### 기대 결과
- 봇 프로세스가 polling 상태로 유지됨
- `/ping` 에 `pong` 응답
- `/help` 에 현재 명령 목록 출력
- `/status` 에 아래 정보가 출력됨
  - `ACTIVE_PROJECT`
  - active project가 있으면 `PROJECT_ROOT`
  - `LATEST_SESSION`

### 실패 신호
- 봇이 즉시 종료됨
- `/status` 에 traceback 성격의 에러 문구가 보임
- help 출력에 `/diff` 가 아직 남아 있음

## 4. 시나리오 2: 프로젝트 생성 및 선택
1. `/project_create tg_manual python`
2. `/project_use tg_manual`
3. `/project_list`
4. `/status`

### 기대 결과
- 생성 응답에 project root 경로가 포함됨
- 선택 응답에 `active_project` 변경 메시지가 출력됨
- `/project_list` 에 `tg_manual *` 표시
- `/status` 에 `ACTIVE_PROJECT: tg_manual` 출력

### 로컬 확인
- `projects/tg_manual/` 존재
- `projects/tg_manual/.git/` 존재
- `projects/tg_manual/config/project.yaml` 존재
- `projects/tg_manual/runs/` 존재

## 5. 시나리오 3: 자동 반영 작업
1. `tg_manual` 이 active project 인지 확인
2. 아래 자연어 요청 전송
   - `src/main.py를 수정해서 실행하면 Hello Telegram을 출력하게 해줘`
3. 완료 메시지를 기다린다

### 기대 결과
- 작업 생성 직후 `queued: <task_id>` ACK가 먼저 도착함
- Telegram에 Codex output 본문이 직접 전송됨
- `/apply` 단계가 필요하지 않음
- 아래 파일이 즉시 변경되어 있어야 함
  - `projects/tg_manual/src/main.py`
- 파일 실행 시 요청한 값이 출력되어야 함

### 로컬 확인
- `python3 projects/tg_manual/src/main.py`
- 출력값이 요청한 내용과 일치해야 함

### 실패 신호
- task_id를 알 수 있는 초기 ACK가 오지 않음
- Telegram에서는 작업 완료처럼 보이는데 파일 내용이 바뀌지 않음
- task가 계속 `RUNNING` 으로 남아 있음
- 봇이 `/apply` 를 요구함

## 6. 시나리오 4: Session Resume / New
1. 같은 active project에서 아래 요청 전송
   - `방금 만든 출력문을 소문자로 바꿔줘`
2. 완료 후 최신 task의 meta 파일 확인
   - `projects/tg_manual/runs/<task_id>/meta.json`
3. 아래 명령 전송
   - `/new src/main.py를 다시 대문자로 바꿔줘`
4. 새 task의 meta 파일 확인

### 기대 결과
- 일반 후속 자연어 작업은 아래 값 저장
  - `session_mode=resume`
- `/new` 작업은 아래 값 저장
  - `session_mode=new`
- 새 task meta 에 실제 `session_id` 가 기록됨

### 실패 신호
- 일반 후속 작업이 계속 `new` 로만 실행됨
- `/new` 가 이전 세션을 이어받음

## 7. 시나리오 5: 로그 아카이브
1. 완료된 task에 대해 아래 명령 전송
   - `/logs <task_id>`

### 기대 결과
- bot이 zip 아카이브를 전송함
- zip 내부에 아래 파일이 포함됨
  - `meta.json`
  - `stdout.log`
  - `stderr.log`
  - `summary.md`
  - `request.txt`

### 실패 신호
- 존재하는 task인데 `/logs` 가 찾지 못함
- zip 파일이 비어 있음

## 8. 시나리오 6: 커밋
1. 자동 반영이 끝난 성공 task에 대해 아래 명령 전송
   - `/commit <task_id> test commit from telegram`

### 기대 결과
- bot이 commit hash를 응답함
- task meta 상태가 `COMMITTED` 로 변경됨
- 프로젝트에서 `git log --oneline -1` 확인 시 commit message가 일치함

### 실패 신호
- bot이 `/apply` 를 요구함
- `main` 이 아닌 다른 branch에서 커밋하려고 시도함

## 9. 시나리오 7: Active Project 유실 복구
1. `tg_manual` 같은 active project를 준비
2. bot 실행 상태에서 로컬에서 해당 프로젝트 디렉터리를 삭제
3. `/status`
4. 자연어 작업 1건 전송
5. `/project_list`

### 기대 결과
- `/status` 에 active project가 해제되었다는 메시지가 출력됨
- 자연어 작업은 실행되지 않음
- 복구 안내가 출력됨
  - `/project_list`
  - `/project_use <name>`
- `/project_list` 에 삭제된 프로젝트가 active 로 표시되지 않음

### 실패 신호
- bot 프로세스가 죽음
- stale active project가 그대로 유지됨
- 없는 프로젝트 기준으로 task가 생성됨

## 10. 시나리오 8: 프로젝트 clone
1. `/project_clone tg_clone <repo_url>`
2. `/project_use tg_clone`
3. `현재 프로젝트 구조를 짧게 설명해줘`

### 기대 결과
- clone 성공
- cloned repo를 active project로 선택 가능
- 자연어 작업이 해당 repo에서 정상 수행됨

### 실패 신호
- clone 응답은 성공인데 `/project_use` 가 실패함
- clone 결과에 `config/project.yaml` 또는 `runs/` 가 없음

## 11. 시나리오 9: 프로젝트 제거
1. `/project_remove tg_clone`
2. `/project_list`
3. force 동작까지 볼 경우 실행 중 task를 만든 뒤 아래 명령 전송
   - `/project_remove tg_clone --force`

### 기대 결과
- 기본 제거는 `.trash` 로 이동
- 제거된 active project는 자동 해제
- `--force` 는 해당 프로젝트의 `QUEUED`/`RUNNING` task를 취소 후 제거

### 실패 신호
- 제거 후에도 active project가 유지됨
- 기본 제거가 trash 이동이 아니라 영구 삭제로 동작함

## 12. 시나리오 10: Project Root 명령
1. `/project_root show`
2. `/project_root set /tmp/dfr-projects`
3. `/project_root show`
4. 필요 시 아래 명령까지 확인
   - `/project_root set /tmp/dfr-projects-2 --migrate`

### 기대 결과
- `show` 가 현재 base root를 출력
- `set` 이 base root를 갱신
- `--migrate` 사용 시 이동된 프로젝트 이름을 같이 출력

### 실패 신호
- 잘못된 경로를 조용히 성공 처리함
- 프로젝트가 사라졌는데 active cleanup이 안 됨

## 13. 최종 통과 기준
- 모든 응답이 현재 자동 반영 설계와 일치해야 함
- 어느 응답에도 `/diff` 가 나오지 않아야 함
- 성공한 작업에서 `/apply` 가 필요하지 않아야 함
- active project 유실 복구가 bot crash 없이 동작해야 함
- 최소 1건 이상 작업이 자동 반영되고 `/commit` 까지 성공해야 함
