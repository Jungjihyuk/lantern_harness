# Architecture — Schema 사양서

> **목적**: 이 시스템의 책임 / 메커니즘 / 소유 축, role enum, manifest, compose.yaml schema 를 한 문서에 정의. 본 문서는 schema reference — 구현은 `lib/*.py`.

## 목차

1. [#1. 개요 — 시스템의 정체성](#1-개요--시스템의-정체성)
2. [#2. A-1: 5 책임 도메인](#2-a-1-5-책임-도메인)
3. [#3. A-2: 7 메커니즘 폴더](#3-a-2-7-메커니즘-폴더)
4. [#4. A-3: `roles.yaml` — 도메인별 role enum](#4-a-3-rolesyaml--도메인별-role-enum)
5. [#5. A-4: `manifest.yaml` — artifact 메타 schema](#5-a-4-manifestyaml--artifact-메타-schema)
6. [#6. A-5: `compose.yaml` schema](#6-a-5-composeyaml-schema)
7. [#7. 결정 노트](#7-결정-노트)
8. [#8. 핵심 개념 · 결정사항](#8-핵심-개념--결정사항)
---

## 1. 개요 — 시스템의 정체성

**3개의 직교 축**:

```
[책임축] 5 도메인                    [메커니즘축] 7 폴더              [소유축] 2 layer
cognition / state / action /         instructions / hooks /            standard / know-how
guard / observe                      tools / adapters /                (양쪽이 동일 7 폴더 mirror)
                                     workflows / traces / evals
```

- **도메인** = "무엇을 달성하는가" (효과)
- **메커니즘** = "어떻게 구현되어 있는가" (형태)
- **소유** = "누가 검증한 것인가" (trust boundary)

세 축은 **직교**. 한 artifact 의 좌표 = `(provider/domain, mechanism, source)` 3-tuple.

**핵심 원리**:
1. **artifact = manifest 가진 self-contained 패키지** (단순 파일 X)
2. **id 가 unique key, name 은 표시용** (provider 내 unique 가 아닌 harness 전체에서 unique)
3. **compose.yaml 은 id 만 참조, resolver 가 위치를 찾음** (`source` 필드 사용 X)
4. **N:N 정직** — 같은 id 가 여러 (domain, role) 조합으로 compose.yaml 에 등장 가능
5. **roles.yaml 로 role enum 검증** — 임의 string 금지
6. **discover & federate** — provider 자산(skill/MCP/plugin) 은 harness 가 소유 X. 원본 위치 그대로 두고 manifest 로 통합 뷰만. (자세한 건 §7 결정 노트)

---

## 2. A-1: 5 책임 도메인

각 도메인 = LLM/시스템이 다루는 책임 영역. 동작 효과(effect) 기준 분류.

| key | 한글 | 정의 | 예 |
|---|---|---|---|
| `cognition` | 인식·판단 | LLM 이 *알고 판단할* 것 — 텍스트·문맥·규칙·트리거 | AGENTS.md, Required Context, Trigger→Read, Hard Rules |
| `state` | 상태·흐름 | 시간 축에서 *기억하고 흘러가는* 것 — 메모리·반복·진행 | status JSON, workflow loop (ralph), session meta |
| `action` | 행동 | *외부에 영향*을 주는 것 — tool 호출·MCP·provider 결합 | tools/, adapters/ (Claude/Codex/MCP) |
| `guard` | 제어·안전 | *못 하게 막거나 제한*하는 것 — 검증·차단·loop 감지 | required_check, cognitive_guard, loop_detection, stop_validation |
| `observe` | 관측·피드백 | 시스템에서 *나오는 신호를 보고 평가*하는 것 — log·진단·verdict | trace, metrics, state diagnosis, evals |

**경계 원칙**:
- 한 artifact 가 여러 효과를 낼 수 있음 → 여러 도메인에 entry 등록 (N:N)
- 도메인은 책임의 단위, 메커니즘은 구현의 단위

---

## 3. A-2: 7 메커니즘 폴더

각 메커니즘 = artifact 의 형태(form). 동일 인터페이스/계약을 만족하는 것끼리 한 폴더.

```
standard/                 (know-how/ 도 같은 7 폴더 mirror)
├── instructions/         # 텍스트 (LLM 이 읽는 것)
├── hooks/                # 시점 트리거 코드 (envelope in/out)
├── tools/                # 직접 능력 (tool spec + handler)
├── adapters/             # provider/protocol 결합 (driver)
├── workflows/            # 다단계 반복 루프 (step graph + state)
├── traces/               # 관측 신호 writer (이벤트/메트릭)
└── evals/                # 검증·평가 verdict 산출기
```

| 폴더 | 인터페이스 (계약) |
|---|---|
| `instructions/` | markdown/txt 파일. 런타임이 해석 X, LLM 에 그대로 전달 |
| `hooks/` | shell 또는 python 스크립트. stdin: envelope JSON, 응답: allow/self_correct/hard_stop |
| `tools/` | name, schema, handler 함수 (LLM 이 직접 호출) |
| `adapters/` | `ProviderDriver` 인터페이스 (list/disable/enable, 향후 install/remove) |
| `workflows/` | step graph 정의 + 진행 상태 메커니즘 |
| `traces/` | append-only writer (decision_log / trace_event / metric tick) |
| `evals/` | input → verdict 함수 (validation/judgment) |

**판별 기준**: 어떤 인터페이스를 만족하는가. 같은 효과(예: guard)라도 텍스트로 알리면 `instructions/`, 코드로 막으면 `hooks/`, 입력 평가로 막으면 `evals/`.

---

## 4. A-3: `roles.yaml` — 도메인별 role enum

**역할**: compose.yaml 의 entry 가 사용할 수 있는 role 식별자 목록. 임의 string 금지.

**파일 위치**:
- `standard/roles.yaml` — 기본 role 정의
- `know-how/roles.yaml` — 사용자 확장 (선택)

**병합 규칙**: `harness validate` 가 두 파일을 merge. 같은 도메인에서 role 충돌 → 에러.

### 4.1 standard/roles.yaml 초안

```yaml
# Standard role enum — 도메인별 허용 role 목록
# 새 role 추가는 의도적 행위로 강제 (random string 방지)

cognition:
  - prefix_injection      # 시스템 프롬프트에 텍스트 주입
  - context_gating        # required context 읽음 검증
  - rule_reminder         # 행동 규칙 재주입
  - trigger_match         # 파일 작업 시 추가 컨텍스트 트리거 (구 trigger_read)
  - on_demand_hint        # 자율 참조 카탈로그 노출

state:
  - status_init           # 세션 시작 시 상태 파일 초기화
  - status_track          # Read 도구 호출 추적 → status JSON 갱신
  - workflow_step         # 워크플로우 단계 실행 (ralph 등)
  - memory_persist        # 영구 메모리 갱신

action:
  - tool_invoke           # tool 직접 호출
  - adapter_call          # provider 결합 호출 (claude/codex/MCP)
  - external_send         # 외부 시스템 발화 (slack, email 등)

guard:
  - required_check        # required_context 미읽음 차단
  - cognitive_guard       # 변경 규모 제한 (per_call/per_session)
  - loop_detection        # doom loop 감지
  - stop_validation       # 종료 조건 검증
  - permission_gate       # 도구 권한 검사

observe:
  - trace_log             # 결정 이벤트 기록
  - metric_collect        # 토큰/시간/라인 누적
  - state_snapshot        # 시스템 상태 덤프
  - state_diagnose        # 상태 진단
  - eval_verdict          # 평가 verdict 산출
  - view_render           # 시각화/리포트 렌더링
```

**명명 규칙**: `snake_case`, 보통 `<동사>_<명사>` 또는 `<명사>_<동사>` 형식 일관.

**확장**: know-how/roles.yaml 에서 사용자가 추가 가능. 예시:
```yaml
# know-how/roles.yaml
guard:
  - my_custom_rate_limit   # 본인이 만든 추가 가드
```

---

## 5. A-4: `manifest.yaml` — artifact 메타 schema

**위치**: 각 artifact 패키지 폴더 안의 `manifest.yaml` (예: `standard/hooks/cognitive_guard/manifest.yaml`).

### 5.1 schema

```yaml
# 필수 필드
id: <unique-id>                       # harness 전체에서 unique. snake_case 권장.
domain: cognition|state|action|guard|observe
mechanism: instructions|hooks|tools|adapters|workflows|traces|evals
purpose: "<한 줄 설명>"                  # 사람이 읽는 용도

# role 정보 — 한 artifact 가 여러 role 가능
roles:                                 # 이 artifact 가 만족시킬 수 있는 role 목록
  - <role-from-roles.yaml>             # roles.yaml 에 등록된 것만 허용
  - <role-from-roles.yaml>

# 선택 필드 (해당되면)
provenance: local|external             # external 이면 import 된 것
origin: <path|url>                     # external 일 때 원본 위치
inputs: {<key>: <type>}                # 이 artifact 의 입력 spec
outputs: [<value>, ...]                # 출력 spec
provides: [<capability>, ...]          # 능력 명세 (semantic 비교 시 사용)
requires: [<dependency-id>, ...]       # 의존 artifact id

# 메커니즘별 추가 필드
entry: <relative-path>                 # hooks/tools/workflows — 실제 실행 파일
event: <lifecycle-event>               # hooks — 어느 시점에 발동 (pre_tool_use 등)
```

### 5.2 예시 — cognitive_guard hook

```yaml
# standard/hooks/cognitive_guard/manifest.yaml
id: cognitive_guard
domain: guard
mechanism: hooks
purpose: "변경 규모 per-call/per-session 한도 검사"
roles:
  - cognitive_guard
event: pre_tool_use
entry: ./handler.sh
inputs:
  max_diff_lines: int
  max_new_files: int
outputs: [allow, self_correct, hard_stop]
```

### 5.3 예시 — required_context 검사 (한 hook 이 여러 role)

```yaml
# standard/hooks/pre_tool_use_required/manifest.yaml
id: pre_tool_use_required
domain: guard
mechanism: hooks
purpose: "Required Context 미읽음 시 변경 도구 차단"
roles:
  - required_check
  - context_gating       # cognition 도메인에도 영향
event: pre_tool_use
entry: ./handler.sh
```

→ compose.yaml 에서 이 hook 을 `guard.hooks` 와 `cognition.hooks` 양쪽에 등록 가능 (다른 role 로).

---

## 6. A-5: `compose.yaml` schema

### 6.1 최상위 구조

```yaml
version: 2

# === 5 도메인 (모두 선택, 비어있어도 OK) ===
cognition:    {...}
state:        {...}
action:       {...}
guard:        {...}
observe:      {...}

# === 글로벌 정책 ===
policies:     {...}                    # 도메인 간 공통 설정 (선택)
```

### 6.2 도메인 entry 형식 — id + role 명시

각 도메인은 메커니즘별로 entry 목록을 가짐. 한 entry = `{id, role}` 또는 단순 `id`.

```yaml
guard:
  # 명시적 role (artifact 가 여러 role 가졌을 때)
  hooks:
    - {id: pre_tool_use_required, role: required_check}
    - {id: pre_tool_use_cognitive, role: cognitive_guard}
    - {id: pre_tool_use_loop, role: loop_detection}
  # 단순 id (artifact 의 manifest 가 단일 role 이면)
  evals:
    - stop_validator
```

**규칙**:
- entry 가 단순 string → artifact 의 manifest.roles 중 첫 번째 사용 (또는 단일 role 가정)
- entry 가 object → `role` 필드가 manifest.roles 에 포함되어 있어야 함
- 임의 role 사용 → `harness validate` 에러

### 6.3 도메인별 표준 entry 키

```yaml
cognition:
  instructions:    [<id>, ...]         # 텍스트 자산 (prefix 주입)
  context:
    required:      [<id>, ...]         # 세션 시작 시 무조건 읽기
    triggered:     [<id>, ...]         # 파일 작업 시 트리거 (옵션 when)
    suggested:     [<id>, ...]         # 자율 참조 카탈로그
  rules:           [<id>, ...]         # hard rules (텍스트)
  hooks:           [<entry>, ...]      # cognition 효과 hook (예: prefix 주입)

state:
  workflows:       [<id>, ...]         # 반복 루프 (ralph 등)
  hooks:           [<entry>, ...]      # 상태 init/track
  memory:          {...}               # 영구 메모리 backend 설정

action:
  adapters:        [<id>, ...]         # provider/MCP 결합
  tools:           [<id>, ...]         # 직접 능력

guard:
  hooks:           [<entry>, ...]      # 차단 hook들
  evals:           [<id>, ...]         # 검증 verdict
  policies:        {...}               # 임계값 (cognitive_guard, loop_detection)

observe:
  hooks:           [<entry>, ...]      # trace_log 등
  traces:          [<id>, ...]         # 관측 writer
  evals:           [<id>, ...]         # 후행 평가
```

### 6.4 전체 예시 (현재 시스템 표현)

```yaml
version: 2

cognition:
  instructions:
    - AGENTS_base
  context:
    required:
      - project_readme
      - design_doc
    triggered:
      - {id: api_contract, when: "src/api/**"}
    suggested:
      - architecture_overview
      - runbook
  rules:
    - rule_no_silent_failure
    - rule_korean_domain_terms
  hooks:
    - {id: session_start_prefix, role: prefix_injection}
    - {id: pre_tool_use_required, role: context_gating}

state:
  workflows:
    - ralph
  hooks:
    - {id: session_start_status, role: status_init}

action:
  adapters: [claude, codex]

guard:
  hooks:
    - {id: pre_tool_use_required, role: required_check}
    - {id: pre_tool_use_cognitive, role: cognitive_guard}
    - {id: pre_tool_use_loop, role: loop_detection}
    - {id: stop_validator_hook, role: stop_validation}
  policies:
    cognitive_guard:
      max_diff_lines: 200
      max_new_files: 3
    loop_detection:
      consecutive_same_path: 3
      on_loop: self_correct

observe:
  hooks:
    - {id: post_tool_use_trace, role: trace_log}
  traces:
    - decision_log
    - metric_collector
  evals:
    - stop_validator
```

### 6.5 검증 (`harness validate`)

`harness validate` 가 compose.yaml 을 검사:

1. **id resolution** — 모든 id 가 standard/ 또는 know-how/ 에 존재하는지
2. **role 매칭** — entry.role 이 해당 artifact 의 manifest.roles 에 포함되는지
3. **roles.yaml enum** — 모든 role 이 roles.yaml 에 등록되어 있는지
4. **domain ↔ mechanism 일관** — manifest.domain 이 compose 의 위치와 일치하는지
5. **id 충돌** — 같은 id 가 standard 와 know-how 양쪽에 존재 시 에러 (또는 know-how 우선 정책)

---

## 7. 결정 노트

### 왜 `source` 필드 없나
초기 설계엔 `source: standard|know-how|both` 가 있었으나, 사용자가 신경 쓸 필요 없는 표면 정보. id 가 unique 보장되면 resolver 가 자동으로 위치 찾음. 같은 id 가 양쪽에 있을 때 정책(`harness validate` 가 에러 / know-how 우선) 만 명시.

### 왜 manifest 가 여러 role 을 가지나
한 hook (예: `pre_tool_use_required`) 가 cognition (context_gating) + guard (required_check) 두 도메인에 효과를 미치는 게 자연스러움. manifest 에 가능한 role 다 적고, compose.yaml entry 에서 어느 role 로 등록할지 명시.

### 왜 N:N 표현 (같은 id 여러 entry)
"같은 hook 파일이 여러 도메인의 다른 role" 을 정직하게 표현. compose.yaml 만 보면 "이 시스템에 어떤 효과가 작동하는지" 한눈에 보임.

### 왜 roles.yaml enum 강제
새 role 추가 = 의도적 행위. random string 으로 효과 만들지 못하게. agent 가 자기 진화할 때 "사용 가능한 능력" 카탈로그로 작동.

### Skills 와 federation
provider (Claude/Codex/...) 가 가진 skill 은 **harness 가 소유하지 않음**. ~/.claude/skills/, ~/.codex/skills/ 그 자리에 그대로 둠. `harness list/show/disable/enable` 은 manifest 로 통합 뷰만 제공.

따라서 새 구조에 `standard/skills/` 폴더는 **없음**. skill 의 본질은 복합체 (text + scripts + 의존) 이고 단일 메커니즘에 강제로 매핑하면 어색. federation 원칙으로 provider 가 자기 방식대로 관리하게 두는 게 깔끔.

본인이 자체 skill 만들고 싶다면 → provider 위치 (`~/.claude/skills/my_skill/` 등) 에 직접. harness 가 자동 인지.

### 미래 확장 — multi-mechanism bundle 추가 가능
지금은 manifest 가 단일 메커니즘만 표현 (`mechanism: hooks` 같은 단일 값). 미래에 본인이 자체 runtime + 자체 skill 패키지를 만들고 싶어진다면 (B 시나리오), manifest 에 `bundle` 필드를 optional 로 추가하는 길이 열려있음:

```yaml
# 미래 — 단순 artifact (현재 동작)
id: my_text_artifact
mechanism: instructions

# 미래 — multi-mechanism bundle (그때 추가)
id: mygraphify
bundle:
  instructions: [./SKILL.md]
  tools: [./scripts/run.py]
  requires: [some_adapter]
```

미래 변경 비용 견적:
- manifest validator 에 `if "bundle" in m` 분기 한 줄
- resolver 에 bundle 로딩 로직 추가
- compose.yaml 형식 영향 0 (id 등록 그대로)
- 기존 manifest 무변경 (backward-compatible)

→ 지금 reserve 안 함. 필요해지면 schema 진화로 자연스럽게 추가.

---

## 8. 핵심 개념 · 결정사항

### 8.1 `id` 가 무엇인가

**id** = 한 artifact (hook/instructions/eval/...) 를 **harness 시스템 안에서 유일하게 가리키는 이름표**. manifest.yaml 안에 적힘.

```yaml
# standard/hooks/pre_tool_use/manifest.yaml
id: pre_tool_use              # ← 이게 id
domain: guard
mechanism: hooks
roles: [required_check, ...]
```

compose.yaml 은 이 id 로 artifact 를 참조:

```yaml
guard:
  hooks:
    - {id: pre_tool_use, role: required_check}   # ← id 로 참조
```

**작동 흐름**:
1. compose.yaml 에서 `pre_tool_use` id 를 봄
2. harness resolver 가 standard/ + know-how/ 의 모든 manifest.yaml 순회
3. `id: pre_tool_use` 인 폴더 찾음
4. 그 폴더의 handler.sh 실행

→ **id 는 compose.yaml 과 실 파일을 연결하는 키**.

### 8.2 결정 — id 명명 규칙: 사용자 명시

**갈래 비교**:

| 갈래 | 동작 | 장점 | 단점 |
|---|---|---|---|
| 자동 생성 | filename → id (`README.md` → `readme`) | 사용자 부담 0 | 의미 모호, 파일명 바꾸면 id 도 바뀜 |
| **사용자 명시** ✓ | manifest.yaml 의 `id` 필드 직접 작성 | 의미 명확, 파일명 독립 | 사용자가 manifest 작성 |

**결정**: 사용자 명시. manifest.yaml 의 `id` 필드를 직접 작성.

**명명 권장**:
- snake_case (`pre_tool_use` ✓, `PreToolUse` ✗)
- 의미 있는 단어 (`project_readme` ✓, `readme1` ✗, `r1` ✗)
- harness 전체에서 unique (standard + know-how 통틀어)

### 8.3 결정 — id 충돌 정책: 에러 강제

**충돌 시나리오**:

```
standard/hooks/pre_tool_use/
├── manifest.yaml          # id: pre_tool_use
└── handler.sh             # (공식 버전)

know-how/hooks/pre_tool_use/
├── manifest.yaml          # id: pre_tool_use  ⚠️ 같은 id!
└── handler.sh             # (본인이 만든 변형)
```

→ harness resolver 가 `pre_tool_use` 검색 → 2개 발견. 어느 걸?

**3 옵션 비교**:

| 옵션 | 동작 | 트레이드오프 |
|---|---|---|
| **A. 에러 강제** ✓ | `harness validate` 가 "id 충돌!" 에러. 다른 id 로 분리 강요 | 정직성. 의도 명시 |
| B. know-how 우선 | 자동으로 know-how 의 것 사용 (git-config 스타일) | 조용한 override 디버깅 어려움 |
| C. flag 로 명시 | compose entry 에 `--prefer know-how` 같은 옵션 | 수동 부담 |

**결정**: A 에러 강제. 이유:
1. 같은 id 가 두 곳에 의도치 않게 있는 건 보통 사고
2. 사용자가 standard 의 버전을 override 하고 싶다면 → **다른 id 로** know-how 에 만듦. 의도가 코드에 박힘
3. B 의 조용한 override 는 "왜 내 know-how 가 안 먹지?" 같은 디버깅 어려움 유발

**Override 시나리오 예** (A 정책 하에서):

본인이 standard 의 `pre_tool_use` 동작을 살짝 바꾸고 싶다면:

```
know-how/hooks/my_strict_pre_tool_use/
├── manifest.yaml          # id: my_strict_pre_tool_use  ← standard 와 다른 id
└── handler.sh             # 본인 변형 로직
```

compose.yaml 에서 standard 의 것 빼고 본인 것 등록:

```yaml
guard:
  hooks:
    # - {id: pre_tool_use, role: required_check}            # 빼고
    - {id: my_strict_pre_tool_use, role: required_check}    # 새로 등록
```

→ 의도가 명시적으로 표현. 다른 사람이 봐도 "이 프로젝트는 본인 변형 hook 을 쓴다" 즉시 보임. 자기진화 시 agent 도 명확히 인지.

### 8.4 결정 — manifest 위치: artifact 폴더 안

```
standard/hooks/pre_tool_use/
├── manifest.yaml          # ← 이 artifact 의 진실원
└── handler.sh
```

**3 옵션**:

| 옵션 | 동작 | 트레이드오프 |
|---|---|---|
| **A. 폴더 안 manifest.yaml** ✓ | 각 artifact 가 self-contained 패키지 | 이동성, import/promote 단순 |
| B. root 카탈로그 한 파일 | `standard/_manifest.yaml` 에 모두 명세 | 한눈에 보이지만 거대해짐, merge conflict |
| C. 하이브리드 | 폴더 manifest + auto-generated index | 양쪽 장점이지만 복잡도 ↑ |

**결정**: A 폴더 안. federation 원칙과 일관 (artifact 가 self-contained). 미래 bundle 도 자연스럽 (한 폴더 = 한 패키지). 동적 registry 패턴은 `provider adapter driver 자동 발견`에서 이미 검증됨 — 폴더 순회 부담 없음.

### 8.5 결정 — hook dispatcher: 통합 유지 (현재 그대로)

§8.3 의 A 결정과 짝. 한 hook 파일이 시점에 따라 여러 role 을 처리하지만, 내부 분기는 hook 코드가 알아서:

```bash
# pre_tool_use/handler.sh (현 구조 그대로)
case "$some_condition" in
  ...) # required_check 로직
  ...) # cognitive_guard 로직
  ...) # loop_detection 로직
esac
```

- compose.yaml entry 의 `role` 은 **의미 명세 (표시용)**
- harness 의 hook 실행기는 `HARNESS_ROLE` 환경변수로 정보만 전달 (옵션 — hook 이 활용해도 되고 무시해도 됨)
- 실제 dispatch 는 hook 내부의 if-else 가 처리 (현재 코드 변경 없음)

미래에 §8.3 B (role 별 분리) 로 갈 때 dispatcher 가 필요해짐. 지금은 단순.

### 8.6 결정 요약표

| 항목 | 결정 |
|---|---|
| id 명명 규칙 | 사용자 명시 (manifest.yaml 의 `id` 필드), snake_case, 의미 있는 단어 |
| id 충돌 (standard ↔ know-how) | **에러 강제** — 같은 id 양쪽 존재 시 `harness validate` 실패 |
| manifest 위치 | artifact 폴더 안 `manifest.yaml` |
| hook dispatcher | 통합 유지 — role 은 표시용, 내부 분기는 hook 코드가 처리 |

---
