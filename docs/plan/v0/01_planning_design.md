# 1. 기획/설계안 (Planning & Design) — DogFootRuler v0.1

## 1) 한 줄 정의
Telegram에서 자연어로 지시 → 집 PC(WSL2 Ubuntu)에서 Codex CLI 실행 → 결과(요약/로그/diff) 회신 → 승인 시 커밋/머지까지 가능한 **원격 개발 리모컨**.

## 2) 배경
- Yulmu 본 프로젝트를 진행하기 전에, “원격에서 Codex에게 명령 → 결과 수신” 파이프라인을 먼저 안정화하기 위한 미니 프로젝트.
- 실제 코딩 산출물보다 **운영 안정성/보안/승인 플로우/로그 아카이브** 검증이 목적.

## 3) 목표 (Goals)
G1. Telegram에서 **자연어** 메시지로 작업을 실행할 수 있다.  
G2. 결과를 **짧은 요약 + 첨부(로그/patch)** 형태로 받는다.  
G3. 기본 정책은 안전하게(SAFE): 변경은 승인(Apply/Commit/Merge)이 있어야 진행.  
G4. 모든 실행은 **Task ID + 브랜치 + 아카이브**로 추적 가능.  
G5. 집 밖에서도 운영 가능: 봇 프로세스 상시 실행, 상태/취소/로그 회수 가능.

## 4) 비목표 (Non-goals)
N1. “완전 자율 코딩 에이전트(스스로 반복 개선/머지까지 자동)”는 v0에서 만들지 않는다.  
N2. 모델/비용 최적화는 깊게 하지 않는다(구독 기반 Codex CLI 고정).  
N3. 다수 사용자/팀 협업 권한 모델은 최소(allowlist)로 시작한다.

## 5) 전제/제약
- Windows + WSL2(Ubuntu)에서 실행
- Codex CLI 설치 및 **구독(OAuth) 로그인 완료**
- Telegram BotFather 토큰 보유
- Telegram 메시지 길이 제한 → 긴 결과는 파일 전송 필요
- 초기에는 단일 워커(동시 실행 X)로 안정성 우선

## 6) 설계 원칙
P1. 메시지 라우팅:  
- 슬래시(`/...`) = 시스템/운영 명령  
- 그 외 = 자연어 작업 요청(자동 Task 생성)

P2. 안전(기본 SAFE):  
- 변경/머지/외부 명령은 “명시 승인” 기반  
- 브랜치 분리(항상 새 브랜치)

P3. 재현성:  
- 실행 입력/출력/메타를 runs에 영구 저장  
- 실패해도 아카이브 남김

## 7) 아키텍처
### 7.1 구성도
Telegram User → Telegram Bot API → DogFootRuler Bot(WSL)  
- Router (slash vs natural)  
- Queue (single worker)  
- Task Store (runs/<task_id>/...)  
- Git Ops (branch/diff/commit/merge)  
- Codex Runner (subprocess: codex exec)  
→ Telegram으로 결과 리포트

### 7.2 런타임 컴포넌트
- bot server: Python(권장)로 polling 방식(MVP)
- codex runner: `subprocess`로 `codex exec ...` 호출
- git ops: `git` CLI 사용
- reporter: 메시지 + 파일 첨부

## 8) 상태 머신 (Task Lifecycle)
- QUEUED → RUNNING → DONE | FAILED | CANCELED
- SAFE 모드 기본:
  - 결과가 “READY_TO_APPLY” 상태가 될 수 있음(변경 제안만)
- APPLY 후:
  - APPLIED → (선택) COMMITTED → (선택) MERGED

## 9) 핵심 산출물
- Telegram에서 자연어 1건 → Task 생성 → Codex 실행 → summary + logs 반환
- diff/patch 제공
- 승인 명령(/apply, /commit, /merge) 플로우

## 10) 성공 기준(Exit Criteria)
- 집 밖에서 Telegram만으로 “자연어→Codex 실행→결과 수신” 성공
- Task 아카이브가 남고, /diff, /logs가 동작
- allowlist/승인 게이트로 안전성 확보
