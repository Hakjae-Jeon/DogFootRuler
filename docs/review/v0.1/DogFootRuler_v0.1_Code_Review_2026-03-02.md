# DogFootRuler v0.1 Code Review (현재 ZIP 기준)
작성일: 2026-03-02 (Asia/Seoul)

대상: `DogFootRuler_0.1.zip` (root: `bot/`, `src/`, `config/`, `docs/`, `tests/`, `runs/`)

---

## 0) 한 줄 결론
v0.1은 **(1) 프로젝트/정책(allow/deny) + (2) Task 큐/아카이브 + (3) Telegram/CLI 인터페이스 + (4) Codex 실행 래퍼**까지 “최소 운영 파이프라인”을 잘 쪼개서 갖췄습니다.  
다만 **보안(시크릿/요청문 저장)과 운영 안전성(main 직접 수정, 재시작 복구, 알림 UX)** 쪽은 v0.2에서 바로 손보는 게 좋습니다.

---

## 1) 아키텍처/구조 평가

### 1.1 레이어링 (장점)
- `interfaces/` (Telegram, CLI) ↔ `application/` (startup, task_runner, artifacts) ↔ `project/` (ProjectManager/Policy) ↔ `tasks/` (TaskStore/Status) ↔ `integrations/` (codex, git)
- 의존 방향이 비교적 깔끔하고, 테스트도 “통합 중심”으로 설계된 흔적이 있습니다.

### 1.2 책임 분리(좋은 포인트)
- **PathPolicy**로 “프로젝트 루트 탈출/하드 금지(.git, secrets, .env) / 시스템 금지(runs 등)”를 분리한 점이 특히 좋습니다.
- `TaskRunner`가 “Codex 실행 → diff/changed_files → 정책 검사 → meta 갱신 → notifier”로 한 흐름을 갖고 있어 추적이 쉽습니다.

---

## 2) P0 (즉시 조치 권장) — 보안/시크릿/데이터 취급

### 2.1 config/telegram.yaml에 토큰이 포함된 채로 공유됨 (최우선)
- ZIP에 실제 `config/telegram.yaml`이 들어있고 토큰이 노출됩니다.
- `.gitignore`로 커밋은 막았더라도, **파일 공유/백업/로그 아카이브**에서 그대로 새어 나갈 수 있습니다.

**권장**
- 토큰 **즉시 Rotate** (BotFather에서 새 토큰 발급) + 기존 토큰 폐기
- repo에는 `config/telegram.sample.yaml`만 두고, `config/telegram.yaml`은 로컬에서만 관리

### 2.2 request.txt / meta.json에 “요청 원문”을 그대로 저장
- `TaskStore.create_task()`가 request.txt에 원문 저장 + meta.json에도 `request` 필드로 저장합니다.
- 사용자가 실수로 키/토큰/비밀번호를 요청에 포함하면, 그대로 디스크에 남고 `/logs`로 zip 공유됩니다.
- 현재 `mask_sensitive()`는 stdout/stderr/summary에만 적용되고 **request.txt/meta.json에는 적용되지 않습니다.**

**권장(최소 변경)**
- `TaskStore.create_task()`에서 저장 전에 `mask_sensitive()` 적용(또는 “저장용 request_sanitized”를 별도 필드로 저장)
- `/logs` zip 생성 시에도 request.txt를 마스킹한 임시 파일을 넣거나, zip 생성 단계에서 마스킹 적용

### 2.3 mask_sensitive 규칙이 과도하게 넓음
- `([A-Za-z_][A-Za-z0-9_]*)=(... )` 규칙 때문에 `status=...` 같은 **일반 문자열까지 전부 *** 처리될 수 있습니다.
- 보안에는 유리하지만, 운영 시 로그 가독성이 급격히 떨어질 수 있습니다.

**권장**
- “모든 key=value” 마스킹은 제거/완화하고,
  - key 이름이 `*_TOKEN`, `*_KEY`, `*_SECRET`, `OPENAI_API_KEY` 등일 때만 마스킹
  - 또는 “known secrets 리스트(환경/설정에서 로드)”를 exact replace

---

## 3) P1 — 운영 안전성(워크스페이스/브랜치/복구)

### 3.1 Codex가 현재 체크아웃된 브랜치/워크스페이스를 직접 수정
- v0.1 현재 흐름은 `TaskRunner`가 Codex 실행 후 변경을 **바로 작업 트리에 반영**하고,
- `/commit`도 **main 브랜치에서만 허용**합니다.
- 단일 큐 워커라 충돌은 줄지만, “승인/리뷰” 없이 main이 오염될 수 있어 운영 리스크가 큽니다.

**권장(선택지)**
- A안(현 UX 유지):  
  - `process_task()` 시작 시 `git checkout main` + `workspace_is_clean()` 강제  
  - 더러운 경우 즉시 FAILED(또는 자동 tidy 정책)
- B안(승인 플로우 복구/추천):  
  - task별 브랜치(dfr/task/<id>)에서 Codex 실행 → diff 생성 → `/commit`/`/merge`로 승인을 통과해야 main 반영

### 3.2 재시작 복구: RUNNING 상태가 영구 RUNNING이 될 수 있음
- `TaskStore._load_existing_tasks()`는 **QUEUED만 재큐잉**합니다.
- 프로세스 크래시/재시작 시 RUNNING이 남으면, 운영상 “멈춘 작업”이 생깁니다.

**권장**
- startup 시 RUNNING을 `FAILED(크래시 복구)` 또는 `QUEUED(재시도)`로 전환하는 정책 추가

### 3.3 TaskStore가 “모든 프로젝트 runs”를 순회하며 로드 (예외 전파 가능)
- `_iter_known_task_dirs()`에서 `manager.get_project()`가 예외를 던지면 TaskStore init이 깨질 수 있습니다.

**권장**
- 각 프로젝트 로드 실패는 skip + warning 로그

---

## 4) P2 — Telegram UX/알림 품질

### 4.1 자연어 요청 후 즉시 응답이 없음
- `natural_text_handler()`는 task를 만들고 끝나며, 사용자에게 task_id를 알려주지 않습니다.
- 사용자는 `/logs <task_id>` 등을 사용할 수 없어서 UX가 끊깁니다.

**권장**
- task 생성 직후:
  - `reply_text(f"queued: {task_id}\n/status로 큐 확인, 완료 후 /logs {task_id}")`

### 4.2 완료 알림에서 summary가 생략될 수 있음
- `notify_task_completion()`은 `stdout.log`가 존재하면 stdout 전송 후 **return**합니다.
- 그래서 “성공/실패/다음 단계/ diff 여부” 같은 요약을 못 받을 수 있습니다.

**권장**
- summary(짧은 텍스트) → stdout/stderr(필요시 일부) → “/logs 안내” 순서로 항상 보내기
- stdout/stderr는 길이 제한/스팸 방지를 위해 “상위 N줄 + /logs 안내”로 절제

---

## 5) 테스트/패키징 이슈 (현재 ZIP 기준)

### 5.1 `from tests.test_manager import ...` import가 환경에 따라 깨질 수 있음
- 많은 파이썬 환경에 `tests`라는 site-packages 패키지가 존재합니다.
- 현재 `tests/` 폴더가 **패키지(__init__.py)로 선언되어 있지 않아서**, import가 외부 패키지로 해석될 위험이 큽니다.
- 이 ZIP을 “깨끗한 환경”에서 `pytest`로 돌리면 collection 단계에서 `ModuleNotFoundError: tests.test_manager`가 발생할 수 있습니다.

**권장(가장 간단)**
- `tests/__init__.py` 추가(빈 파일)
- 또는 import를 `from .test_manager import ...`로 바꾸고 tests를 패키지화

### 5.2 배포물에 __pycache__/ .pytest_cache / runs 샘플이 포함됨
- 공유 ZIP에서는 불필요하고, 용량/노이즈/시크릿 리스크만 올립니다.

**권장**
- 배포/공유용 아카이브 생성 시 제외:
  - `__pycache__/`, `.pytest_cache/`, `runs/`, `config/*.yaml`(실파일), `*.pyc`

---

## 6) 작은 코드 개선(유지보수성)

- `GitClient.generate_diff/changed_files`의 `branch` 인자는 현재 사용되지 않으므로 제거하거나 실제로 활용하도록 정리
- `TaskStore.update_meta()`가 task 미존재 시 조용히 return → 운영에서 문제를 숨길 수 있어, 최소 warning 로그 권장
- `TaskRunner.process_task()`의 `finally: pass`는 제거 가능(또는 정리 작업 넣기)

---

## 7) 우선순위 액션 아이템 (추천 PR 순서)

### PR-SEC (즉시)
1) Telegram token rotate + `telegram.sample.yaml`만 repo에 포함
2) request/meta 저장 시 마스킹 또는 민감정보 저장 금지 정책 적용
3) 공유/배포 zip에서 config 실파일 제거

### PR-OPS
1) startup 복구: RUNNING → FAILED/QUEUED 정책
2) task 실행 전 `checkout main` + `workspace_is_clean` 보장(또는 task 브랜치 플로우 복원)

### PR-UX
1) natural_text_handler가 task_id를 즉시 응답
2) 완료 알림에서 summary 먼저, stdout/stderr는 요약 + /logs 유도

### PR-TEST
1) `tests/__init__.py` + import 정리로 어디서든 pytest 동작 보장
2) Telegram handler(특히 natural_text_handler) 테스트 추가

---
