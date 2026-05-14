# tools/

LLM 이 직접 행사하지 못하는 능력의 **로컬 실행 스크립트** 모음.

- 각 tool: `<id>/manifest.yaml + entry script` 패턴 (다른 메커니즘과 동일).
- 주 도메인: `action` (compose.yaml 의 `action.tools` entry 로 등록).

현재 비어있음. 검증된 tool 이 누적되면 여기 모임. 사용자 실험적인 tool 은 `know-how/tools/` 에.

> MCP 와의 경계: MCP **protocol** 결합은 `adapters/`, MCP 가 노출하는 **개별 tool entry** 는 여기로 분류 (실 도입 시점에 결정).
