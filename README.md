# DogFootRuler (Mini Project for Yulmu) — Docs Pack v0.1

- Date: 2026-02-28 (Asia/Seoul)
- Purpose: Telegram을 통해 Codex CLI(구독 기반 로그인)를 원격으로 실행하고, 결과(요약/로그/diff)를 받는 **운영 파이프라인**을 검증하는 미니 프로젝트.
- Scope: “원격 명령 채널 + 안전한 실행/승인/아카이브”가 핵심. 본 프로젝트(Yulmu) 이전에 위험/운영 이슈를 최대한 미리 잡는다.

## 문서 구성
1. `docs/01_planning_design.md` — 기획/설계안 (목표/비목표/아키텍처/흐름)
2. `docs/02_functional_requirements.md` — 기능 요구사항서 (FRD)
3. `docs/03_development_plan.md` — 개발순서/마일스톤/PR 단위 DoD
4. `docs/04_command_spec.md` — Telegram 명령(슬래시) + 자연어 처리 스펙
5. `docs/05_task_model_and_artifacts.md` — Task 상태/아카이브 구조/파일 포맷
6. `docs/06_security_guardrails.md` — allowlist/승인게이트/금지행위/비밀 마스킹
7. `docs/07_test_plan.md` — 스모크/통합/회귀 테스트 시나리오
8. `docs/08_ops_runbook.md` — 운영/장애 대응/로그/백업/상시 실행
9. `docs/09_codex_prompt_pack.md` — Codex에 “문서 기반으로 단계별 구현” 시킬 프롬프트 묶음

> 사용법: 이 문서팩을 Codex에게 읽히고, **PR 단위로 구현**하도록 지시하세요.
