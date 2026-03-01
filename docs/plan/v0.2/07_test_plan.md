# 7. Test Plan — v0.2

## Smoke
- `/ping`
- allowlist 외 사용자 거부

## Project
- `/project_list`
- `/project_use <name>`
- `/project_clone <name> <url>` 성공/실패
- `/project_remove <name>` 후 목록 반영
- `/project_root show|set` 경로 검증

## Session
- 동일 프로젝트 자연어 2회 실행 → `session_mode=resume`
- `/new <prompt>` → `session_mode=new`

## Active Project 유실
- active project 폴더 수동 삭제/이동
- 자연어 실행 시 크래시 없이 안내
- `/project_list -> /project_use` 복구

## Task Flow
- 변경 유도 프롬프트로 파일 수정
- 작업 결과가 자동 `APPLIED`
- `/commit`으로 커밋 생성
- non-zero / timeout / error → `FAILED`

## Negative
- 비 git dir / clone 실패 / 잘못된 root 경로
- 긴 출력 분할 전송
- 단일 워커 동시 실행 방지
