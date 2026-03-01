# 4. Command Spec — Telegram Interface

## 라우팅 규칙
- `/`로 시작: 시스템 명령
- 그 외: 자연어 작업 요청(= Task 생성 + 실행)

---

## 시스템 명령(슬래시)

### /help
- 사용 가능한 명령 요약 + 자연어 사용법 예시

### /ping
- 응답: `pong`

### /status
- 출력:
  - RUNNING task_id(있다면)
  - QUEUED 개수 및 상위 N개 task_id
  - 최근 완료 task_id

### /logs <task_id>
- runs/<task_id>/stdout.log, stderr.log 전송
- 파일이 없으면 안내

### /diff <task_id>
- git diff를 `diff.patch`로 전송
- diff가 비어있으면 “변경 없음” 안내

### /apply <task_id>
- SAFE 모드에서 “변경 제안만” 있던 경우 실제 변경 수행
- 또는 apply 모드로 재실행(설계 선택)

### /commit <task_id> "<msg>"
- 현재 task 브랜치에 커밋 생성
- 성공 시 커밋 해시 반환

### /merge <task_id>
- main으로 머지 시도
- 충돌 시 안내 + 중단
- 성공 시 머지 커밋 해시 반환

### /cancel <task_id>
- RUNNING이면 취소 시도(프로세스 kill)
- QUEUED이면 큐에서 제거

---

## 자연어 요청 예시
- “이 레포 구조 요약해줘”
- “bot/main.py에 /ping 명령 추가해줘”
- “실행 로그에서 에러 원인만 요약해줘”
