# DogFootRuler — Remote Codex Bot

- Date: 2026-02-28 (Asia/Seoul)
- Purpose: Telegram을 통해 Codex CLI를 원격으로 실행하고, 활성 프로젝트 작업 트리에 결과를 자동 반영하는 운영 봇.
- Scope: 다중 프로젝트 관리, Codex 세션 연속성, 로그 아카이브, Telegram/CLI 운영 인터페이스.

## Policy 준수
- 이 프로젝트에서 작업할 때는 항상 `policy/` 하위 문서에 정의된 정책을 우선적으로 확인하고 준수해야 합니다.

## 현재 구조
- `bot/` : 실행 엔트리포인트
- `src/dogfoot/interfaces/` : Telegram, CLI 등 인터페이스 어댑터
- `src/dogfoot/application/` : 작업 실행/시작 검증 유스케이스
- `src/dogfoot/project/`, `tasks/`, `integrations/`, `utils/` : 코어 로직

## 현재 동작
- 자연어 작업은 active project에서 실행
- 성공한 변경은 작업 트리에 자동 반영
- 기본 세션 정책은 `resume`, `/new <prompt>`는 새 세션 시작
- 프로젝트 관리는 Telegram과 CLI 모두 지원
- 로그 아카이브는 프로젝트별 `runs/`에 저장되며 Git ignore 대상

## 주요 명령
- Telegram: `/project_list`, `/project_use`, `/project_create`, `/project_clone`, `/project_remove`, `/project_root`, `/new`, `/logs`, `/commit`
- CLI: `dogfoot project create|clone|remove|use|list|root`

## 문서
- 현재 기준 문서: `docs/plan/v0.2/`
- 이전 단계 문서: `docs/plan/v0/`, `docs/plan/v0.1/`
