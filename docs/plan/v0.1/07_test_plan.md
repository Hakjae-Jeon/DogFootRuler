
# 테스트 플랜 (TDD 기반)
작성일: 2026-03-01 14:00:16

## Unit Test
- 정책 판정 테스트 (allow/deny/root escape)
- ProjectManager 동작 테스트
- `../` 기반 root escape 차단 테스트
- 절대경로 입력 차단 테스트
- symlink를 통한 우회 차단 테스트
- 정규화 전/후 경로가 같은지 검증하는 테스트

## Integration Test
- 임시 git repo 생성
- diff → 정책 검증 → apply 흐름 테스트
- active_project 변경 후에도 기존 task가 생성 시점 project에서만 처리되는지 테스트
- hard deny 경로 변경 시 FAILED 되는지 테스트

## TDD 사이클
Red → Green → Refactor
