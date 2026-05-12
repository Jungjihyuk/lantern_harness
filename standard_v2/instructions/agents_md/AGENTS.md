<!--
================================================================
AGENTS.md — Standard 표준 md (Prefix 주입)

이 파일은 작업 시작 시 system prompt prefix로 자동 주입됩니다.
프로젝트는 know-how/AGENTS.md를 만들어 이 파일을 통째 override 가능.

규약:
1. 4 블록 구조 유지: Required / On-Demand / Trigger → Read / Hard Rules
2. Required는 1~3개로 절제
3. Hard Rules는 본문에 직접 명시 (참조 X — prefix 영구 유지)
4. 구조 위반 시 stop hook이 거부

표준 md 자격 (prefix 들어갈 자격 — 새 md 추가 시 가이드):
- 항상 적용되어야 하는가
- 압축되면 손해가 큰가
- 짧게 표현 가능한가 (또는 요약만으로 효과)
- 프로젝트 무관 보편적인가

압축 정책:
- 이 파일에 직접 적힌 텍스트 = system prefix = 압축 안 됨
- 참조(- path/to/file.md)로 가리킨 문서 본문 = 도구 결과 = 압축 가능
================================================================
-->

# AGENTS.md

> 작업 시작 전 Required Context를 모두 읽으세요.
> Required를 읽지 않은 채 코드 변경 금지 (hook이 강제).

## Required Context
<!-- 시작 시 반드시. 1~3개로 절제. 자기 path 직접 적기. -->
- 프로젝트 정의: docs/.../프로젝트 정의서.md
- 강제 컨벤션:  docs/.../강제 컨벤션.md

## On-Demand Context
<!-- 필요할 때 lazy. -->
- 시스템 설계: docs/.../시스템 설계서.md
- 데이터 명세: docs/.../데이터 명세서.md
- 학습 노트:   docs/.../12. 기술 문서/

## Trigger → Read
<!-- 특정 작업을 하기 전 강제로 참고 해야할 문서 매핑. -->
<!-- PreToolUse  -->
- DB/스키마 변경 → 데이터 명세 먼저
- API 인터페이스 → 인터페이스 명세 먼저
- 권한·서명 변경 → 권한 명세 먼저

## Hard Rules
<!-- 직접 명시. 참조 X. 강제력 본체. prefix 영구 유지. -->
1. Required Context를 읽지 않은 채 코드 변경 금지
2. Trigger 매칭 시 해당 문서를 먼저 읽고 작업
3. <know-how 추가 룰>
