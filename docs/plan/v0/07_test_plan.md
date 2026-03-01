# 7. Test Plan

## Smoke (PR1)
- /ping → pong
- allowlist 외 사용자 거부

## Integration (PR2~PR3)
- 자연어 “say hi” → task 생성 → codex 실행 → 결과 텔레그램 수신
- runs/<task_id>/request.txt, stdout.log 생성 확인

## Git Flow (PR4)
- 변경을 유도하는 프롬프트로 파일 수정
- /diff <task_id>로 patch 파일 수신

## Approval Flow (PR5)
- SAFE에서 변경 “제안만” 확인
- /apply 후 diff 생성
- /commit 후 커밋 해시 수신
- /merge 성공 또는 충돌 시 안전 중단

## Negative
- codex 실행 실패(비 git dir) → 친절한 에러 안내
- 긴 출력 → 파일 첨부로 처리
- 중복 실행/동시 실행 방지 확인
