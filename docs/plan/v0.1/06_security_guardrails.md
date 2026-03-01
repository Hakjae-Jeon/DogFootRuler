
# 보안 / 가드레일
작성일: 2026-03-01 14:00:16

## 1. 경계 정책
1) Project Root 외부 차단
2) forbidden_subpaths 차단
3) allowed_subpaths 잠금 모드 적용

## 2. Hard Deny 권장
- .git/
- secrets/
- .env

## 3. Secret Masking
- token, key, secret 패턴 마스킹
