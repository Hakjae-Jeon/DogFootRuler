
# 보안 / 가드레일
작성일: 2026-03-01 14:00:16

## 1. 경계 정책
1) Project Root 외부 차단
2) forbidden_subpaths 차단
3) allowed_subpaths 잠금 모드 적용

## 2. Hard Deny 강제
- .git/
- secrets/
- .env

- hard deny 목록은 시스템 공통 기본값으로 항상 적용한다.
- 프로젝트 설정은 hard deny를 완화할 수 없고, 추가만 가능하다.
- 경로가 project root 내부에 있어도 hard deny와 충돌하면 항상 차단한다.

## 3. Secret Masking
- token, key, secret 패턴 마스킹
