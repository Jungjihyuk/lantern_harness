# 코딩 컨벤션 (CONVENTIONS.md)

> 작업 시 따라야 할 코드 규칙. **에이전트가 코드 변경 전 참조.**

## 1. 스타일

- 들여쓰기: (예: 2 spaces / tabs)
- 줄 길이 한도: (예: 100자)
- 따옴표: (예: single quote)

## 2. 파일 구조

- 한 파일에 한 컴포넌트/클래스
- export 순서: types → constants → functions → component
- (등등)

## 3. 커밋 메시지

- 형식: `<type>(<scope>): <subject>`
- type: feat / fix / refactor / docs / test / chore
- 예: `feat(auth): add OAuth callback handler`

## 4. PR 규칙

- 한 PR = 한 가지 변경
- 리뷰어 최소 1명
- CI 통과 필수

## 5. 테스트

- 새 기능에 테스트 동반
- 단위 테스트는 __tests__/ 또는 *.test.ts
- coverage 80% 이상 유지

## 6. 금지 패턴

- (예: console.log 남기지 말 것 — 디버깅 시만)
- (예: any 타입 남용 금지)
