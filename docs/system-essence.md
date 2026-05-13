# Harness — 시스템 본질

> 이 시스템이 무엇이고 어떻게 작동하는지 **진짜 핵심만**.
> 상세 schema 는 `architecture.md`, 구현은 `lib/*.py` 참고.

---

## 1. 한 줄 정의

> **LLM agent 의 행동 결정 요소를 모두 self-contained artifact 로 외부화해, 한눈에 보고·검증하고·진화시킬 수 있게 만든 메타 layer.**

provider (Claude Code, Codex, ...) 위에서 작동. LLM 자체를 만들지 않고, agent 가 *어떻게 행동할지*를 외부 구조로 통제한다.

---

## 2. 3개의 직교 축

```
[책임축] 5 도메인              [메커니즘축] 7 폴더               [소유축] 2 layer
─────────────────             ──────────────────              ───────────────
cognition  인식·판단           instructions  텍스트              standard   공인 토대
state      상태·흐름           hooks         시점 코드            know-how   개인 노하우
action     행동                tools         직접 능력
guard      제어·안전           adapters      provider 결합
observe    관측·피드백          workflows     반복 루프
                              traces        관측 신호
                              evals         검증 verdict
```

- **도메인** = *무엇을 달성하는가* (효과)
- **메커니즘** = *어떻게 구현되는가* (형태)
- **소유** = *누가 검증했는가* (trust boundary)

세 축은 직교. 한 artifact 의 위치 = `(domain, mechanism, source)` 좌표.

---

## 3. Artifact — 시스템의 최소 단위

> **harness 가 관리하는 self-contained 패키지.**

폴더 1개 = artifact 1개. 안에 `manifest.yaml` (정체성) + 실제 내용 (코드/텍스트).

```
standard/hooks/session_start/      ← 1 artifact
├── manifest.yaml                   ← 정체성
└── session_start.sh                ← 내용
```

manifest.yaml 의 필수 4필드:
- `id`: harness 전체에서 unique 식별자
- `domain`: 5 도메인 중 하나
- `mechanism`: 7 폴더 중 하나
- `roles`: 만족시킬 수 있는 역할 목록 (roles.yaml 의 enum)

---

## 4. 4개의 핵심 파일

| 파일 | 역할 | 비유 |
|---|---|---|
| `docs/architecture.md` | 개념·schema 정의 | 헌법 |
| `standard/roles.yaml` | 도메인별 허용 role 이름 enum | 직업 목록 |
| `<artifact>/manifest.yaml` | 개별 artifact 의 메타 | 신분증 |
| `<project>/.harness/compose.yaml` | 어느 artifact 를 어느 role 로 활성화할지 | 조직도 |

데이터 흐름:
```
roles.yaml 의 enum    ←──── 검증 ────    manifest.roles
                                              ↓
                                       artifact id
                                              ↓
                                       compose.yaml entry
                                       (artifact 활성화 매핑)
```

---

## 5. 핵심 원칙 5가지

### 1. **artifact = 의미 단위**
모든 hook·텍스트·도구·결합·루프·관측·평가가 *id 가진 패키지*로 외부화.

### 2. **id 가 unique key**
compose.yaml 은 path 가 아닌 id 로 참조. resolver 가 위치 찾음.

### 3. **N:N 정직**
한 artifact 가 여러 (domain, role) 에 등장 가능. 예: `session_start` 가 cognition + state + observe 셋에 모두 등록.

### 4. **discover & federate** (provider 자산)
Claude/Codex 의 skill·MCP·plugin 은 harness 가 소유 X. 원본 위치 그대로 두고 manifest 로 통합 뷰만.

### 5. **코드·데이터 분리**
설치 영역(`~/.harness/`) vs 사용자 데이터(`${XDG_DATA_HOME}/harness/`). install 이 갈아엎어도 데이터 안전.

---

## 6. compose.yaml — 활성화 지도

```yaml
version: 2

cognition:
  instructions: [agents_md]           # 텍스트 prefix
  context:
    required:  [{id: project_readme}] # 시작 시 필독
    triggered: [{id: api_spec, when: "src/api/**"}]
  rules: [rule_01, rule_02]
  hooks:
    - {id: session_start, role: prefix_injection}

guard:
  hooks:
    - {id: pre_tool_use, role: required_check}
    - {id: pre_tool_use, role: cognitive_guard}
  policies:
    cognitive_guard: {max_diff_lines: 200}

observe:
  hooks:
    - {id: session_start, role: trace_log}      # 같은 hook, 다른 도메인·role
    - {id: post_tool_use, role: trace_log}
```

→ "이 시스템이 무엇을 활성화했는가" 한 파일에 정직히 표현. 같은 id 가 다른 도메인·role 로 N:N 등장.

---

## 7. 핵심 명령

| 명령 | 역할 |
|---|---|
| `harness list` | provider 통합 + harness 내부 자산 한눈에 |
| `harness show <name>` | 단건 상세 |
| `harness disable / enable <name>` | provider 자산 활성/비활성 토글 |
| `harness validate` | compose.yaml + manifests + roles 통합 검증 |

provider 자산 (skill/MCP/plugin) 은 `harness list/show/disable/enable` 으로 federation 통합 제어.
harness 내부 자산 (artifact) 은 `validate` 로 schema 일관성 보장.

---

## 8. standard 와 know-how

같은 7 폴더 구조의 mirror. 차이는 **trust boundary**:

```
standard/                            know-how/
├── instructions/                    ├── instructions/
│   └── agents_md/                   │   └── my_extra_text/
├── hooks/                           ├── hooks/
│   └── session_start/               │   └── my_extra_hook/
├── tools/                           ├── tools/
├── adapters/                        ├── adapters/
├── workflows/                       ├── workflows/
├── traces/                          ├── traces/
├── evals/                           └── evals/
└── roles.yaml                       └── roles.yaml (선택, 사용자 확장)
```

- **standard** = 도구/도메인 중립의 검증된 하네스 기본 구성 (시간 따라 합의가 쌓임)
- **know-how** = 실험적인 하네스 또는 프로젝트 성격이 묻어나는 자산 (override 포함)
- **id 충돌 정책**: 같은 id 가 양쪽에 있으면 에러. override 원하면 다른 id 로

> 현재 standard 내부 항목 중 일부 (hooks skeleton, evals 재정비 중) 는 진행 중.

---

## 9. 자기진화 친화 패턴

agent 가 새 기능을 추가할 때 항상 같은 절차:

```
1. 적절한 메커니즘 폴더 (예: hooks/) 에 새 artifact 폴더 생성
2. manifest.yaml 작성 (id + domain + mechanism + roles + purpose)
3. compose.yaml 의 해당 도메인에 entry 추가
4. harness validate 로 검증
```

→ 자기 코드를 진화시킬 때마다 **5축 × 7폴더 × roles enum** 안에서 움직임. 무질서 X.

영향 추적: artifact 빼고 싶으면 compose.yaml grep 으로 어느 도메인에 영향 가는지 즉시 파악.

---

## 10. 구조의 검증 (Codex driver 사례)

Codex driver 를 추가하면서 **공통 코드 (base/registry/mutation/list/show) 한 줄도 수정하지 않음**. driver 폴더 하나만 추가. 모든 통합 명령이 자동으로 새 provider 인지.

→ 인터페이스 일반성 검증됨. 새 provider (Cursor 등) 도 같은 패턴.

---

## 마치며

이 시스템의 본질은 **"agent 행동을 결정하는 것들을 모두 외부로 빼서, 사람과 agent 가 함께 볼 수 있고 진화시킬 수 있게 한다"**. 

LLM provider 는 엔진. harness 는 그 엔진을 어떻게 운용할지 결정하는 외부 통제 시스템. 둘은 서로 대체하지 않고, 보완한다.
