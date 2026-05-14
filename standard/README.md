# standard/

> **도구/도메인 중립의 검증된 하네스 기본 구성.** 시간이 흐르며 합의가 쌓여간다.
> 누구나 가져다 자기 프로젝트에 적용 가능하다. 실험적 하네스나 프로젝트 성격이 묻어나는 자산은 `know-how/` 에 둔다.

## 한눈에 이해하기

- **standard** = 검증된 하네스 (도구/도메인 중립)
- **know-how** = 실험적 하네스 + 프로젝트 성격이 묻어나는 자산 (override 포함)
- 같은 id 가 양쪽에 있으면 에러 — override 원하면 다른 id 로
- 자세한 trust boundary 는 [docs/system-essence.md §8](../docs/system-essence.md) 참고

## 구조

`standard/` 안에는 성격이 다른 2가지가 있다:

### 1. Artifact 컨테이너 (7 메커니즘 폴더)
각 폴더는 `manifest.yaml` 을 가진 artifact 들의 모음:

- `instructions/` — 텍스트 prefix
- `hooks/` — 시점 코드 (session_start, pre_tool_use, post_tool_use, stop 등)
- `tools/` — 직접 능력 (현재 비어있음, 향후 추가)
- `adapters/` — provider 결합 코드 (Claude · Codex 등 매핑) ※ 다른 메커니즘과 달리 *결합 layer* 성격
- `workflows/` — 반복 루프
- `traces/` — 관측 신호
- `evals/` — 검증 verdict

### 2. Schema 정의
- `roles.yaml` — 도메인별 허용 role 이름 enum (검증 기준)

## 현재 상태 (정직 기록)

- `hooks/` 7개는 현재 **skeleton placeholder** — 실 logic 은 후속 작업에서 채워짐

## Artifact 추가 절차

1. 적절한 메커니즘 폴더에 새 artifact 폴더 생성
2. `manifest.yaml` 작성 (`id` · `domain` · `mechanism` · `roles` · `purpose`)
3. 프로젝트의 `.harness/compose.yaml` 에 entry 추가
4. `harness validate` 로 검증

자세한 schema 는 [docs/architecture.md](../docs/architecture.md) 참고.
