
# DogFootRuler v0.1 - 기획/설계안
작성일: 2026-03-01 14:00:16

## 1. 비전
DogFootRuler는 Project Base Root 하위에서 여러 프로젝트를 안전하게 관리하며,
Codex 기반 코드 생성을 승인형 파이프라인으로 운영하는 시스템이다.

## 2. 핵심 설계 원칙
- Safe by Default (기본은 안전)
- Deny 기본 + Allow 잠금 모드
- Project / ProjectManager Class 기반 구조
- 단일 책임 원칙(SRP)
- TDD 기반 개발

## 3. 아키텍처 개요
Telegram → Task 생성 → Codex 실행 → Diff 생성 → Policy 검증 → Git 반영
