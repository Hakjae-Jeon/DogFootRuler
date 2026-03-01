# DogFootRuler (Mini Project for Yulmu) — Docs Pack v0.1

- Date: 2026-02-28 (Asia/Seoul)
- Purpose: Telegram을 통해 Codex CLI(구독 기반 로그인)를 원격으로 실행하고, 결과(요약/로그/diff)를 받는 **운영 파이프라인**을 검증하는 미니 프로젝트.
- Scope: “원격 명령 채널 + 안전한 실행/승인/아카이브”가 핵심. 본 프로젝트(Yulmu) 이전에 위험/운영 이슈를 최대한 미리 잡는다.

## Policy 준수
- 이 프로젝트에서 작업할 때는 항상 `policy/` 하위 문서에 정의된 정책을 우선적으로 확인하고 준수해야 합니다.

## 현재 구조
- `bot/` : 실행 엔트리포인트
- `src/dogfoot/interfaces/` : Telegram, CLI 등 인터페이스 어댑터
- `src/dogfoot/application/` : 작업 실행/시작 검증 유스케이스
- `src/dogfoot/project/`, `tasks/`, `integrations/`, `utils/` : 코어 로직

## v0 문서 구성
1. `docs/plan/v0/01_planning_design.md` — 기획/설계안 (목표/비목표/아키텍처/흐름)
2. `docs/plan/v0/02_functional_requirements.md` — 기능 요구사항서 (FRD)
3. `docs/plan/v0/03_development_plan.md` — 개발순서/마일스톤/PR 단위 DoD
4. `docs/plan/v0/04_command_spec.md` — Telegram 명령(슬래시) + 자연어 처리 스펙
5. `docs/plan/v0/05_task_model_and_artifacts.md` — Task 상태/아카이브 구조/파일 포맷
6. `docs/plan/v0/06_security_guardrails.md` — allowlist/승인게이트/금지행위/비밀 마스킹
7. `docs/plan/v0/07_test_plan.md` — 스모크/통합/회귀 테스트 시나리오
8. `docs/plan/v0/08_ops_runbook.md` — 운영/장애 대응/로그/백업/상시 실행
9. `docs/plan/v0/09_codex_prompt_pack.md` — Codex에 “문서 기반으로 단계별 구현” 시킬 프롬프트 묶음

> 사용법: 이 문서팩을 Codex에게 읽히고, **PR 단위로 구현**하도록 지시하세요.

python3 projects/hello_world/main.py
