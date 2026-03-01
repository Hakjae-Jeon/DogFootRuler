# 4. Command Spec — Telegram Interface (v0.2)

## 라우팅 규칙
- `/`로 시작: 시스템 명령
- 그 외: 자연어 작업 요청(기본 `resume`)

## 시스템 명령

### /help
- 사용 가능한 명령 출력

### /ping
- `pong`

### /status
- active project
- RUNNING task
- QUEUED 개수
- 최근 완료 task

### /logs <task_id>
- `runs/<project>/<task_id>/` 아카이브 전달

### /commit <task_id> "<msg>"
- 현재 프로젝트 작업 트리의 해당 task 변경을 커밋

### /cancel <task_id>
- RUNNING이면 취소 시도
- QUEUED이면 큐에서 제거

## Project 관리

### /project_list
- 프로젝트 목록 + active 표시

### /project_use <name>
- active project 설정

### /project_clone <name> <repo_url> [branch]
- git clone 기반 프로젝트 생성

### /project_remove <name> [--force]
- 프로젝트 제거

### /project_root show
- 현재 base root 표시

### /project_root set <path> [--migrate]
- base root 변경

## 세션 제어

### /new <prompt>
- new session으로 자연어 작업 실행
- 결과 메타에 `session_mode=new`

## 제외 명령
- `/diff` 없음
- `/apply` 없음
- task branch 기반 `/merge` 없음

## 자연어 예시
- `이 레포 구조 요약해줘`
- `방금 만든 함수에 테스트 추가해줘`
- `/new 처음부터 다시 구조 분석해줘`
