# DogFootRuler v0.2 코드/문서/런 리뷰 (ZIP 기준)
- 리뷰일: 2026-03-02 (Asia/Seoul)
- 대상: `DogFootRuler_v0.2.zip` (root: `bot/`, `src/`, `config/`, `docs/`, `tests/`, `logs/`, `runs/`)

## 0) 한 줄 결론
v0.2는 **다중 프로젝트 관리 + active project 복구 + 세션 resume/new + 단일 워커 기반 Codex 실행/아카이빙**까지 핵심 골격이 잘 갖춰졌습니다. 다만 **(1) 시크릿 취급/배포물 관리, (2) 문서-코드 불일치, (3) Telegram UX(큐잉 ACK), (4) /logs 아카이브 누락(meta.json), (5) 무변경(task no-op) 처리 정책**은 바로 손보는 게 좋습니다.

---

## 1) v0.2에서 확인된 히스토리(증거)
### 1.1 작업 로그(`logs/`)
- 2/28: 초기 bot 구조, 큐 워커, Codex 실행, diff/승인 플로우 실험 후 마스킹/아카이브 강화
- 3/1: `src/` 중심 레이아웃 리팩터링, Project/Policy/TaskRunner 분리, 통합 테스트 확대, auto-apply 방향으로 전환
- 3/2: `/project_root show|set --migrate`, stale active 복구 중앙화, 문서/체크리스트 정리, `58 passed`

### 1.2 런 아카이브(`runs/`)
- Codex 실행 아카이브(요청/stdout/stderr/summary/meta)가 남아 있고, 일부는 과거 상태(`READY_TO_APPLY`)가 섞여 있음.
- 현재 코드에서는 `Status.DONE`을 `APPLIED`로 alias 처리하여 레거시도 읽을 수 있게 되어 있음.

---

## 2) 구조/설계 평가
### 2.1 레이어링
- `interfaces/`(Telegram/CLI) ↔ `application/`(startup/task_runner/artifacts) ↔ `project/`(manager/policy) ↔ `tasks/`(store/models) ↔ `integrations/`(codex/git)
- 의존 방향이 깔끔하고, 통합 테스트를 통한 회귀 방지 의도가 보임.

### 2.2 좋은 포인트(강점)
- **PathPolicy**: 루트 탈출/심볼릭 링크 우회 차단, 하드 금지(`.git`, `secrets`, `.env`) 기본값이 합리적.
- **active project 복구**: `ProjectManager.recover_active_project()`로 중앙화했고 `/status`·자연어 진입점에서 UX 안내가 있음.
- **task 아카이브**: request/stdout/stderr/summary/diff(옵션) 저장 구조가 운영 분석에 유리.
- **단일 워커 큐**: 동시성 이슈를 낮추고, cancel/timeout 처리를 단순화.

---

## 3) P0(즉시) — 보안/시크릿/배포물
### 3.1 `config/telegram.yaml`에 실제 토큰이 포함된 채로 ZIP에 포함됨
- `.gitignore`로 커밋은 막았지만, ZIP 공유/백업에서 노출됩니다.

**권장(즉시)**
1) 토큰 **Rotate** (BotFather에서 새 토큰 발급, 기존 토큰 폐기)
2) repo에는 `config/telegram.sample.yaml`만 유지
3) 공유용 아카이브 생성 시 `config/*.yaml` 실파일 제외(샘플만 포함)

### 3.2 마스킹 규칙 점검
- `mask_sensitive()`가 꽤 강하게 동작합니다(보안 측면은 좋음).
- 다만 운영 가독성이 필요하면, 키워드 기반 마스킹(…token/key/secret/password)만 남기고 범용 규칙은 완화하는 옵션도 고려.

---

## 4) P1(우선) — 기능/문서 불일치 & UX 버그
### 4.1 문서 vs 코드 불일치
- v0.2 문서에서는 `/diff`, `/apply`, `/merge`가 “없음”으로 적혀 있는데,
  - 실제 코드는 `/apply`, `/merge` 핸들러와 커맨드 등록이 남아 있습니다(현재는 안내 메시지로 동작).
- v0.2 문서(요구사항/Command Spec)에는 `/project_create`가 없는데 코드/수동검증 문서에는 존재합니다.
- runs 구조 문서가 `runs/<project>/<task_id>`로 되어 있는데, 구현은 **프로젝트 루트 내부** `project_root/runs/<task_id>`입니다.

**권장**
- “하위 호환 안내용 명령을 남길지(문서에 명시)” vs “완전 제거” 중 한 방향으로 정리
- runs 경로 표기는 구현과 일치하게 문서 수정

### 4.2 자연어 작업 요청 후 즉시 ACK가 없음(UX 단절)
- `natural_text_handler/_enqueue_prompt()`가 task를 만들고 끝나서, 사용자는 task_id를 바로 못 봅니다.

**권장(최소 변경)**
- task 생성 직후:
  - `queued: <task_id> (session_mode=..., project=...)` 출력
  - `/status`, `/logs <task_id>` 안내

### 4.3 `/logs` zip에 `meta.json`이 포함되지 않음
- 수동 검증 시나리오/문서에서는 zip에 `meta.json`이 있기를 기대합니다.

**권장**
- `create_artifacts_zip()`에 `meta.json` 포함
- 또는 zip 생성 시 meta를 읽어서 `archive.writestr('meta.json', json.dumps(...))` 형태로 포함

### 4.4 성공(APPLIED) 상태에서 `finished_at`이 기록되지 않음
- 실패/취소는 `finished_at`이 들어가는데 성공은 `ready_at/applied_at`만 기록됩니다.

**권장**
- `APPLIED`로 전환할 때 `finished_at`도 함께 기록(사후 분석/정렬/모니터링에 중요)

### 4.5 “무변경(no-op) task” 처리 정책
- 현재 정책은 변경 파일이 없으면 `PolicyViolation("No changed files were detected")`로 실패 처리됩니다.
- 하지만 문서/수동 검증 예시에는 “레포 구조 요약”처럼 무변경 요청이 존재합니다.

**권장(둘 중 택1)**
- A안(추천): no-op도 성공 처리 + 상태를 `DONE_NO_CHANGE`(또는 `APPLIED` + `changed_files=[]` + `notes=no-op`)로 기록
- B안: “이 봇은 변경 작업 전용”을 문서/UX에서 명확히 고지(예시 프롬프트도 변경 작업 위주로 수정)

---

## 5) P2(개선) — 운영 안정성/유지보수
### 5.1 Codex 실행 옵션 일관성
- resume에는 `--full-auto`가 들어가는데 new에는 없음.
- 실제 사용에서 “계속 물어보는” 문제가 있었다면, new에도 `--full-auto` 적용 또는 codex config(approval_policy) 강제 적용을 검토.

### 5.2 예외 시 사용자에게 실패 알림이 안 갈 수 있음
- `queue_worker()`에서 예외가 나면 meta만 FAILED로 찍고 notifier를 안 부릅니다.

**권장**
- 예외 시에도 summary.md 생성 + notifier 호출(운영에서 원인 파악이 빨라짐)

### 5.3 Git 작업 트리 상태 가드
- auto-apply 유지 시, task 실행 전에:
  - `git checkout main`
  - `workspace_is_clean()` 검사(더러우면 실패/정리 정책)
- 최소한 “어떤 브랜치에서 Codex가 돌았는지”를 meta에 기록하면 디버깅이 쉬움.

---

## 6) 추천 PR 우선순위(현실적인 순서)
### PR-SEC (최우선)
1) 토큰 rotate + `telegram.sample.yaml`만 유지
2) 공유 ZIP 생성 스크립트(불필요 파일 제외: `config/*.yaml`, `runs/`, `__pycache__/`, `*.pyc` 등)

### PR-UX
1) 자연어/`/new` 작업 생성 즉시 ACK
2) `/logs` zip에 `meta.json` 포함
3) 성공 시 `finished_at` 기록

### PR-BEHAVIOR
1) no-op task 정책 결정(A안/B안) 및 문서/테스트 업데이트
2) Codex 옵션 `--full-auto` 일관화 검토

### PR-OPS
1) 큐 워커 예외 시 사용자 알림
2) 실행 전 git 상태 가드(옵션)

---

## 7) 빠른 수동 검증 체크리스트(핵심만)
- `/project_create` → `/project_use` → 자연어 변경 작업 1건 → 파일 실제 변경 확인
- 일반 자연어 2회 → 2번째 meta에 `session_mode=resume`
- `/new` → meta에 `session_mode=new`
- `/logs <task_id>` → zip에 `meta.json` 포함 확인
- `/commit <task_id> msg` → main에서 커밋 생성 확인
- active project 폴더 삭제 후 `/status`와 자연어 요청 → 크래시 없이 active 해제 안내

