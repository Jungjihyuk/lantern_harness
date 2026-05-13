# Architecture v2 — Schema 사양서

> **목적**: issue #6 (3축 마이그레이션) 의 Phase A 결과물. v2 의 책임/메커니즘/소유 축, role enum, manifest, compose.yaml schema 를 한 문서에 정의.
>
> **작성 단계**: Phase A — 종이 위에서 schema 확정 (코드 X). Phase B/C 에서 본 문서를 reference 로 구현.

## 목차

1. [#1. 개요 — v2 의 정체성](#1-개요--v2-의-정체성)
2. [#2. A-1: 5 책임 도메인](#2-a-1-5-책임-도메인)
3. [#3. A-2: 7 메커니즘 폴더](#3-a-2-7-메커니즘-폴더)
4. [#4. A-3: roles.yaml — 도메인별 role enum](#4-a-3-rolesyaml--도메인별-role-enum)
5. [#5. A-4: manifest.yaml — artifact 메타 schema](#5-a-4-manifestyaml--artifact-메타-schema)
6. [#6. A-5: compose.yaml v2 schema](#6-a-5-composeyaml-v2-schema)
7. [#7. 결정 노트](#7-결정-노트)
8. [#8. Phase B — 기존 자산 매핑](#8-phase-b--기존-자산--새-구조-매핑)
9. [#9. 다음 단계](#9-다음-단계-phase-c-이후)

---

## 1. 개요 — v2 의 정체성

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

## 6. A-5: `compose.yaml` v2 schema

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

### 6.4 전체 예시 (현재 시스템을 v2 로 표현)

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

### compose.yaml v1 → v2 매핑 (Phase B 결과)
| v1 키 | v2 위치 |
|---|---|
| `required_context.paths` | `cognition.context.required` |
| `trigger_read` | `cognition.context.triggered` |
| `on_demand_context.paths` | `cognition.context.suggested` |
| `hard_rules` | `cognition.rules` |
| `cognitive_guard` | `guard.policies.cognitive_guard` |
| `loop_detection` | `guard.policies.loop_detection` |
| `stop_validation` | `guard.evals` + `guard.policies.stop_validation` |
| `ralph` | `state.workflows: [ralph]` |
| (hooks 자체) | 각 hook 의 manifest.roles 에 따라 cognition/state/guard/observe 의 hooks 에 분산 |

상세 매핑은 Phase B 에서 추가 작업.

---

## 8. Phase B — 기존 자산 → 새 구조 매핑

본 schema 를 기준으로 현 `standard/*` 자산을 v2 새 구조로 어떻게 옮길지.

### 8.1 폴더 레벨 매핑

```
[현재 standard/]                [새 standard/]
├── AGENTS.md                ──→ ├── instructions/AGENTS.md
├── README.md                ──→ ├── README.md  (그대로, standard 자체 설명)
├── adapters/                ──→ ├── adapters/  (그대로)
│   ├── base.py
│   ├── registry.py
│   ├── list.py
│   ├── show.py
│   ├── _mutation.py
│   ├── disable.py
│   ├── enable.py
│   ├── claude/
│   └── codex/
├── eval/                    ──→ ├── evals/  (rename, 복수형 통일)
├── hooks/                   ──→ ├── hooks/  (그대로)
├── ralph/                   ──→ ├── workflows/ralph/  (workflows/ 하위로)
├── skills/                  ──→ (삭제 — federation 원칙. provider 위치에 그대로 둠)
└── templates/               ──→ └── instructions/templates/  (instructions 하위로)

신규 (현재 없음):
                                  ├── tools/  (LLM 이 호출하는 직접 능력 — 추후 채움)
                                  └── traces/  (관측 writer — 추후 채움)
```

**변화 요약**:
| 작업 | 대상 | 이유 |
|---|---|---|
| 이동 | `AGENTS.md` → `instructions/AGENTS.md` | LLM 이 읽는 텍스트 |
| 이동 | `templates/*` → `instructions/templates/*` | LLM 이 읽는 스카폴드 자산 |
| rename | `eval/` → `evals/` | 복수형 통일 (메커니즘 7개 모두 복수형) |
| 이동 | `ralph/` → `workflows/ralph/` | ralph 는 self-loop = workflow |
| 삭제 | `skills/` | federation 원칙 — provider 영역 |
| 신규 | `tools/`, `traces/` | 7 메커니즘 완성. 비어있어도 OK |

### 8.2 hooks/ 파일별 상세 매핑 (N:N 핵심)

현 hook 파일들은 시점별로 묶여 있고, 한 파일이 여러 도메인에 영향. **파일은 그대로 두고 manifest 의 roles 다중 선언 + compose.yaml 에서 다른 entry 로 N:N 등록**.

| 파일 | 시점 (event) | 만족하는 roles | 등록될 compose entry |
|---|---|---|---|
| `session_start.sh` | `session_start` | prefix_injection, status_init, trace_log | `cognition.hooks` + `state.hooks` + `observe.hooks` (한 id 3 entry) |
| `pre_tool_use.sh` | `pre_tool_use` | required_check, cognitive_guard, loop_detection, context_gating, trace_log | `guard.hooks` (3 entry) + `cognition.hooks` + `observe.hooks` |
| `post_tool_use.sh` | `post_tool_use` | trace_log, metric_collect | `observe.hooks` (2 entry) |
| `stop.sh` | `stop` | stop_validation, trace_log | `guard.hooks` + `observe.hooks` |
| `user_prompt_submit.sh` | `user_prompt_submit` | rule_reminder, trace_log | `cognition.hooks` + `observe.hooks` |
| `post_commit.sh` | `post_commit` (커스텀) | trace_log | `observe.hooks` |

**예시 manifest** (session_start hook):
```yaml
# standard/hooks/session_start/manifest.yaml
id: session_start
domain: cognition       # 주 도메인 (가장 큰 효과)
mechanism: hooks
event: session_start
entry: ./session_start.sh
purpose: "세션 시작 시 prefix 주입 + 상태 초기화 + trace 기록"
roles:
  - prefix_injection    # cognition 효과
  - status_init         # state 효과
  - trace_log           # observe 효과
```

**예시 compose.yaml entry** (같은 id 가 3 도메인에 등장):
```yaml
cognition:
  hooks:
    - {id: session_start, role: prefix_injection}
state:
  hooks:
    - {id: session_start, role: status_init}
observe:
  hooks:
    - {id: session_start, role: trace_log}
```

→ 한 hook 파일을 어떤 효과로 활성화할지 사용자가 명시. 효과 조합 가시화.

#### N:N 매핑 도식

```
[hook 파일]                  [compose.yaml entry]
session_start.sh ────┬──→ cognition.hooks: {id: session_start, role: prefix_injection}
                     ├──→ state.hooks:     {id: session_start, role: status_init}
                     └──→ observe.hooks:   {id: session_start, role: trace_log}

pre_tool_use.sh  ────┬──→ guard.hooks:    {id: pre_tool_use, role: required_check}
                     ├──→ guard.hooks:    {id: pre_tool_use, role: cognitive_guard}
                     ├──→ guard.hooks:    {id: pre_tool_use, role: loop_detection}
                     └──→ observe.hooks:  {id: pre_tool_use, role: trace_log}
```

한 hook 의 효과들이 도메인별로 흩어져 표시 → "도메인별로 한눈에" 가시성 실현.

#### 1:N 단순 모델 vs N:N 정직 모델 — 왜 N:N 인가

| 모델 | compose.yaml 모양 | 가시성 |
|---|---|---|
| **1:N 단순** | `hooks: [session_start]` 한 줄 | "이게 어떤 효과 주는지" 불분명 |
| **N:N 정직 (현재 결정)** | 도메인별 entry 분산 | "session_start 가 cognition/state/observe 3가지" 즉시 보임 |

특히 **자기 진화 친화**: agent 가 compose.yaml 만 보고 "현재 시스템이 cognition 에 무엇을 하나" 즉시 파악 가능.

### 8.3 hook 분리 vs 통합 — 결정 보류

#### 현 상태 — 한 파일이 여러 책임

현재 `pre_tool_use.sh` 한 파일이 if-else 와 순차 검사로 5가지 일을 다 처리:

```bash
# 현 pre_tool_use.sh 내부 흐름
1. Required Context 미읽음 검사 → 차단 (required_check)
2. 변경 규모 검사               → 차단 (cognitive_guard)
3. Doom loop 감지              → 차단 (loop_detection)
4. cognition context gating    → 차단 (context_gating)
5. 결정 로그 기록              (trace_log)
```

한 파일에 5가지 책임이 섞임. v2 manifest 의 roles 에 다 선언.

#### 두 갈래 선택지

**A. 시점별 통합 유지 (현재)**
```
standard/hooks/pre_tool_use/
├── manifest.yaml        # roles: [required_check, cognitive_guard, loop_detection, context_gating, trace_log]
└── handler.sh           # 한 파일에 다 처리 (현재 그대로)
```
- 파일 1개, 책임 5개
- 마이그레이션 부담 0 (현재 코드 그대로)
- 단점: 한 파일이 크고 분기 복잡. 한 책임만 수정해도 다른 것에 영향 가능

**B. role 별 분리**
```
standard/hooks/
├── required_check/
│   ├── manifest.yaml    # roles: [required_check]
│   └── handler.sh       # Required 검사만
├── cognitive_guard/
│   ├── manifest.yaml    # roles: [cognitive_guard]
│   └── handler.sh       # 변경 규모만
├── loop_detection/...   # 각 분리
└── trace_log/...
```
- 파일 5개, 각각 단일 책임
- 단점: 큰 리팩토링. pre_tool_use 시점에 5개를 순차 호출하는 dispatcher 필요

#### 트레이드오프

| 측면 | A (통합) | B (분리) |
|---|---|---|
| 마이그레이션 비용 | 0 | 큼 (리팩토링 + dispatcher) |
| 단일 책임 원칙 | ✗ | ✓ |
| 각 role 독립 enable/disable | 어려움 (한 파일 안 조건) | 쉬움 (파일 단위) |
| 디버깅 | 한 곳 다 봐야 | 해당 폴더만 |
| 새 role 추가 | 기존 파일 수정 | 새 폴더만 추가 |

**Phase B 결정**: 일단 **A 채택** (통합 유지). 이유:
1. 현재 코드가 이미 작동 — 마이그레이션 부담 최소화
2. v2 의 본질 (5 도메인 × 7 메커니즘 × N:N) 은 A 로도 충분히 표현됨 (manifest 의 roles 가 N:N 처리)
3. 실제 운영하면서 "이 hook 만 따로 끄고 싶다" 같은 니즈가 발생하면 그때 B 로 점진 분리

→ 운영 → 필요 시 분리는 manifest 와 entry 만 갱신하면 되므로 후방 호환.

### 8.4 compose.yaml v1 → v2 자동 변환 규칙 *(history, cutover 완료)*

v1 → v2 cutover 시점에 사용된 변환 규칙:

| v1 키 | v2 위치 | 변환 |
|---|---|---|
| `prefix:` | `cognition.instructions:` | id 리스트로 |
| `required_context.paths` | `cognition.context.required` | path/label → id 매핑 (자동 생성 또는 사용자 입력) |
| `trigger_read` | `cognition.context.triggered` | `match_path` + `require` → `{when, id}` |
| `on_demand_context.paths` | `cognition.context.suggested` | path/label → id |
| `hard_rules` | `cognition.rules` | 문자열 리스트 → id 리스트 (각 rule 을 instructions artifact 화) |
| `cognitive_guard` | `guard.policies.cognitive_guard` | 그대로 |
| `loop_detection` | `guard.policies.loop_detection` | 그대로 |
| `stop_validation` | `guard.policies.stop_validation` + `guard.evals` | 정책 + eval 분리 |
| `llm_judge` | `observe.evals` | 그대로 옮김 |
| `ralph` | `state.workflows: [ralph]` | id 만 |

**도전 과제**: path → id 매핑. v1 에선 path 그대로 사용(`README.md`), v2 에선 id (`project_readme`) 필요. 자동 변환 시 path 의 basename + 사용자 확정 step 또는 자동 id 부여 정책 결정 필요.

### 8.5 마이그레이션 사이드 이펙트 분석 *(history, cutover 완료)*

| 영향 | 대상 | 완화 방법 |
|---|---|---|
| hook 경로 변경 | settings.json 의 Claude Code hook 등록 | `harness link claude` 재실행으로 새 경로 등록 |
| compose.yaml 키 변경 | 기존 사용자의 compose.yaml | cutover 시점 일괄 변환 |
| `eval/` → `evals/` rename | 기존 reference 코드 | grep 으로 모든 reference 갱신 (lib/eval/runner.py 등) |
| `ralph/` → `workflows/ralph/` | bin/cmd/ralph.sh 의 경로 참조 | path 한 줄 갱신 |
| `templates/` → `instructions/templates/` | bin/cmd/scaffold.sh 의 `TEMPLATES_DIR` | 경로 갱신 |
| `~/.claude/skills/` 영역 무변경 | provider skill | federation 그대로, 영향 X |

### 8.6 핵심 개념 · 결정사항

#### 8.6.1 `id` 가 무엇인가

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

#### 8.6.2 결정 — id 명명 규칙: 사용자 명시

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

#### 8.6.3 결정 — id 충돌 정책: 에러 강제

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

#### 8.6.4 결정 — manifest 위치: artifact 폴더 안

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

#### 8.6.5 결정 — hook dispatcher: 통합 유지 (현재 그대로)

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

#### 8.6.6 결정 요약표

| 항목 | 결정 |
|---|---|
| id 명명 규칙 | 사용자 명시 (manifest.yaml 의 `id` 필드), snake_case, 의미 있는 단어 |
| id 충돌 (standard ↔ know-how) | **에러 강제** — 같은 id 양쪽 존재 시 `harness validate` 실패 |
| manifest 위치 | artifact 폴더 안 `manifest.yaml` |
| hook dispatcher | 통합 유지 — role 은 표시용, 내부 분기는 hook 코드가 처리 |

---

## 9. 다음 단계 *(history — Phase C/D 완료, E/F 점진)*

**Phase C (코드)**: 본 schema 를 기준으로 resolver / validator / parser 구현 — 완료.

**Phase D**: v1 → v2 자동 마이그레이션 도구 — cutover 완료 후 제거 (v3 시점에 새로 만들 예정).

**Phase E**: 기존 `install/remove` 의미 재정의 — v2 에서 사용 안 함, 명령 자체 제거됨.

**Phase F**: docs 전면 갱신 — 점진 진행 중.
