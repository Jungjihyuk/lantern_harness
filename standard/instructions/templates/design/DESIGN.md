# 디자인 결정 (DESIGN.md)

> 이 프로젝트의 일관된 디자인·아키텍처 결정. **에이전트가 작업 시 일관성 유지를 위해 참조.**

## 1. 전체 아키텍처

- 컴포넌트 구성:
- 주요 기술 스택:
- 핵심 데이터 흐름:

## 2. 디자인 시스템 (UI 한정)

### 색

- Primary:
- Secondary:
- 의미별 (success/warning/error):

### 폰트

- 헤딩:
- 본문:
- 코드:

### 간격·레이아웃

- 기준 단위 (예: 4px grid):
- 컨테이너 max-width:

## 3. 코드 디자인 원칙

- (예: SRP — 한 모듈은 한 가지 이유로 변한다)
- (예: 의존성 주입 — 직접 import 대신 주입)
- (예: YAGNI — 지금 필요 없는 추상화 X)

## 4. 명명 규약

| 종류 | 규약 | 예시 |
|---|---|---|
| 파일 | kebab-case | `user-profile.ts` |
| 컴포넌트 | PascalCase | `UserProfile` |
| 함수·변수 | camelCase | `getUserName` |
| 상수 | UPPER_SNAKE | `MAX_RETRIES` |

## 5. 결정 이력 (ADR)

- (날짜) (결정) — (이유)
