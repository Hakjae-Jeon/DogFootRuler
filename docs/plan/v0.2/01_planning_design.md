# 1. 기획/설계안 (Planning & Design) — DogFootRuler v0.2

## 1) 한 줄 정의
Telegram에서 자연어로 지시하면 집 PC(WSL2 Ubuntu)에서 Codex CLI를 실행하고, 현재 활성 프로젝트의 작업 트리에 결과를 자동 반영하는 원격 개발 봇이다. v0.2에서는 여러 프로젝트를 관리하고, 같은 프로젝트에서는 같은 Codex 세션을 이어 쓰는 정책을 추가한다.

## 2) 배경
- v0.1에서 기본 실행, 아카이브, 프로젝트/정책 계층을 만들었다.
- 현재 제품 방향은 SAFE 승인 플로우가 아니라 자동 반영이다.
- v0.2는 실제 사용성 강화를 위해 프로젝트 관리와 세션 연속성에 집중한다.

## 3) 목표
G1. Telegram 자연어 메시지로 작업을 실행할 수 있다.
G2. 결과는 Codex output 중심으로 전달하고, 상세 로그는 `/logs`로 확인할 수 있다.
G3. 성공한 변경은 현재 프로젝트 작업 트리에 자동 반영된다.
G4. 모든 실행은 `task_id`와 아카이브(`runs/<project>/<task_id>/`)로 추적 가능하다.
G5. 여러 프로젝트를 관리하고 active project 유실을 안전하게 복구할 수 있다.
G6. 동일 프로젝트에서 기본 resume, 필요 시 new session 실행을 지원한다.

## 4) 비목표
N1. task branch 기반 승인 플로우(`/diff`, `/apply`, `/merge`)는 v0.2 범위에 포함하지 않는다.
N2. 다중 사용자/팀 권한 모델은 최소 allowlist로 유지한다.
N3. Gateway restart 후 전체 자동 복구는 v0.2 범위에서 제외한다.

## 5) 전제/제약
- Windows + WSL2(Ubuntu)
- Codex CLI 설치 및 로그인 완료
- Git 설치 및 clone 시 네트워크 접근 가능
- 기본은 단일 워커 큐
- 프로젝트는 project base root 하위에서만 관리

## 6) 설계 원칙
P1. 라우팅
- `/...` = 시스템/운영 명령
- 그 외 = 자연어 작업 요청

P2. Project 컨텍스트
- 자연어 작업은 active project에서만 실행한다.
- active project가 없거나 유효하지 않으면 실행 대신 안내한다.

P3. 세션 정책
- 기본은 동일 프로젝트에서 resume
- `/new <prompt>`는 new session으로 실행

P4. 자동 반영
- Codex가 만든 변경은 정책 검사 후 현재 작업 트리에 바로 반영한다.
- 후속 수동 작업은 `/commit` 중심으로 한다.

P5. 관측성
- 입력/출력/메타/patch를 runs에 저장한다.
- 실패해도 아카이브가 남는다.

## 7) 아키텍처
Telegram User → Telegram Bot API → DogFootRuler Bot
- Router
- Project Registry
- Queue (single worker)
- Task Store (`runs/<project>/<task_id>/...`)
- Session Policy (`resume|new`)
- Codex Runner
- Git Ops (`clone`, `commit`)
- Reporter (`stdout.log` 중심 + `/logs`)

## 8) 상태 머신
- `QUEUED -> RUNNING -> APPLIED | FAILED | CANCELED`
- 선택 후속 상태:
  - `COMMITTED`

## 9) 핵심 산출물
- 프로젝트 관리:
  - git clone 기반 생성
  - 프로젝트 제거
  - project base root 변경
  - active project 유실 시 자동 해제 및 안내
- 세션:
  - 기본 resume
  - `/new` 실행
  - `session_mode` 기록

## 10) 성공 기준
- Telegram만으로 프로젝트 선택, 자연어 실행, 결과 확인이 가능하다.
- active project 유실 시 봇이 죽지 않고 복구 안내를 제공한다.
- clone/remove/root 변경 기능이 안전장치와 함께 동작한다.
- 동일 프로젝트 연속 실행에서 session policy가 메타에 기록된다.
