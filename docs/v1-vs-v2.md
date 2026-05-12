# v1 vs v2 — 현재 시스템 상태 정리

> **"지금 어디까지 v1 이고 어디까지 v2 인가"** 한눈에 보기.
> issue #6 작업 중간 상태. v2 인프라 + 마이그레이션 도구는 완성, 기존 명령은 v1 그대로.

## 1. 한 줄 요약

**v1 시스템이 여전히 primary. v2 는 옆에 완비된 상태로 대기 중. `harness upgrade` 가 둘 사이의 다리.**

---

## 2. v1 영역 (기존, 변경 없음)

Claude Code 와 실제로 통신하는 영역. **현재 사용자 환경에서 작동 중인 것**.

### 자산 위치
```
~/.harness/standard/             ← Claude Code 가 실제 사용
├── AGENTS.md                     # 한 파일, manifest 없음
├── hooks/
│   ├── session_start.sh          # 시점별 단일 파일
│   ├── pre_tool_use.sh
│   └── ...
├── eval/                         # 단수형
├── ralph/
├── templates/
└── adapters/                     # provider 결합 (이건 사실상 v1/v2 무관)
```

### compose.yaml (사용자 프로젝트)
```
<project>/.harness/compose.yaml   ← v1 형식
```
키: `prefix`, `required_context`, `trigger_read`, `hard_rules`, `cognitive_guard`, `loop_detection`, ...

### v1 만 다루는 명령 (bin/cmd/)
| 명령 | 역할 |
|---|---|
| `harness init` | v1 compose 생성 |
| `harness install <name>` | 글로벌 → 프로젝트 symlink |
| `harness remove <name>` | symlink 삭제 |
| `harness fork <name>` | symlink → 로컬 복사 |
| `harness link / unlink` | provider hook 등록 |
| `harness reload` | runtime/AGENTS.md 재생성 |
| `harness scaffold` | 템플릿 복사 |
| `harness doctor` | 진단 |
| `harness eval / improve / judge / ralph / viz / publish` | v1 영역 도구 |

### v1 코드 위치
- `lib/eval/`, `lib/improve/`, `lib/judge/`, `lib/prompts/`, `lib/viz/`
- `standard/hooks/lib/` (hook 공유 라이브러리)

---

## 3. v2 영역 (새로 만든 인프라 + 자산)

새 schema 의 핵심. **존재하지만 아직 시스템이 primary 로 안 씀**.

### 자산 위치
```
~/.harness/standard_v2/          ← migrate_v2 가 생성한 v2 layout
├── instructions/
│   ├── agents_md/
│   │   ├── manifest.yaml          # 각 자산이 폴더 + manifest
│   │   └── AGENTS.md
│   └── templates/
│       ├── readme/, design/, conventions/, security/
├── hooks/
│   ├── session_start/             # 시점별 폴더화
│   │   ├── manifest.yaml
│   │   └── session_start.sh
│   ├── pre_tool_use/, post_tool_use/, stop/, ...
│   └── _lib/                       # 공유 라이브러리
├── evals/                          # 복수형
├── workflows/ralph/
├── adapters/                       # claude / codex (manifest 추가됨)
└── roles.yaml
```

### compose.yaml v2 (사용자 프로젝트, upgrade 후)
```
<project>/.harness/compose.v2.yaml   ← v2 형식
<project>/.harness/know-how/          ← 사용자 path/rule artifact 자동 emit
```
키: `version: 2`, `cognition`, `state`, `action`, `guard`, `observe` 5 도메인

### v2 만 다루는 명령 (bin/cmd/)
| 명령 | 역할 |
|---|---|
| `harness validate` | v2 compose + manifest + roles 통합 검증 |
| `harness upgrade` | v1 → v2 통합 마이그레이션 (bridge) |

### v2 코드 위치 (`lib/`)
| 파일 | 역할 |
|---|---|
| `manifest.py` | Manifest dataclass + parser + validator |
| `roles_registry.py` | roles.yaml 로드 + 도메인별 enum |
| `resolver.py` | id → manifest path 매핑 (충돌 검사) |
| `compose.py` | v2 compose 파서 (5 도메인 entry) |
| `validator.py` | 통합 검증 orchestrator |
| `validate_cli.py` | `harness validate` 엔트리 |
| `migrate_v2.py` | standard/ → standard_v2/ 마이그레이션 |
| `migrate_compose.py` | compose v1 → v2 변환 + know-how artifact emit |
| `upgrade.py` | upgrade 통합 orchestrator |

---

## 4. 공유 영역 (v1/v2 무관)

provider adapter 처럼 schema 와 독립적인 부분.

### Provider adapter
```
standard/adapters/          # v1
standard_v2/adapters/       # v2 사본 (둘이 동일 내용)
```

내부:
- `base.py`, `registry.py`, `_mutation.py`
- `list.py`, `show.py`, `disable.py`, `enable.py`
- `claude/driver.py`, `codex/driver.py`

### 명령 (provider 통합, v1/v2 무관)
| 명령 | 역할 |
|---|---|
| `harness list` | Claude/Codex 의 MCP/skill/plugin 통합 뷰 |
| `harness show <name>` | 단건 상세 |
| `harness disable / enable <name>` | provider 자산 토글 |

### 사용자 데이터 (XDG 영역, install 영향 X)
```
${XDG_DATA_HOME}/harness/state/   ← MCP 백업 등
```

---

## 5. Bridge — v1 ↔ v2 다리

### `harness upgrade`
사용자 프로젝트에서 한 번 실행:

```
~/.harness/standard/              ──── migrate_v2 ────→  standard_v2/
.harness/compose.yaml             ──── migrate_compose ──→  compose.v2.yaml
                                                          + .harness/know-how/<artifacts>/
```

3 단계 (각 step idempotent):
1. **standard 마이그레이션** — 폴더 구조 v2 화
2. **compose 변환** — 키 매핑 + 사용자 path/rule 자동 artifact 화
3. **validate** — 결과 검증

### `harness validate`
v2 결과 검증 — manifest 형식 + roles enum + id 충돌 + entry 매핑.

---

## 6. 시스템 상태 그림

```
┌─────────────────────────────────────────────────────────────────────┐
│                   현재 작동 중 (v1 — primary)                          │
│                                                                       │
│   ~/.harness/standard/  ──────────  Claude Code runtime              │
│         │                                  │                          │
│         │ session_start.sh 등              │                          │
│         ▼                                  │                          │
│   <project>/.harness/compose.yaml  ◀───── hooks 가 읽음               │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘

                    │ harness upgrade
                    │ (사용자가 실행)
                    ▼

┌─────────────────────────────────────────────────────────────────────┐
│                   완비됨 (v2 — 대기 중)                                │
│                                                                       │
│   ~/.harness/standard_v2/                                             │
│         │                                                             │
│         │  manifest 들                                                 │
│         ▼                                                             │
│   <project>/.harness/compose.v2.yaml                                  │
│   <project>/.harness/know-how/<artifacts>                             │
│                                                                       │
│   ↑ harness validate 가 정합성 검증                                    │
│                                                                       │
│   ⚠️ Claude Code 의 hook 들은 여전히 v1 위치 가리킴.                    │
│      v2 의 hook 들은 정의돼 있지만 아직 발동 X.                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. v2 가 진짜 primary 되려면 — 남은 일

### Phase E — 기존 명령 v2 적응
| 작업 | 의미 |
|---|---|
| `harness init` v2 모드 | 새 프로젝트가 v2 compose 로 시작 |
| hook 들이 v2 compose 읽기 | session_start.sh 등이 v1/v2 둘 다 인지 (또는 v2 우선) |
| `install / remove` 의미 재정의 | symlink 모델 vs compose id 추가 모델 |

### Cutover — standard_v2 → standard swap
```bash
mv ~/.harness/standard ~/.harness/standard_v1_archive
mv ~/.harness/standard_v2 ~/.harness/standard
```
이 시점부터 hook 들이 v2 자산 사용. 큰 결정 — 한번 swap 하면 v1 동작 멈춤.

### Phase F — 문서·가이드
| 작업 | 의미 |
|---|---|
| `docs/01-입문.md` ~ `03-고급.md` v2 반영 | 사용자 가이드 갱신 |
| `docs/migration-v1-to-v2.md` 신규 | 마이그레이션 매뉴얼 |
| `README.md` 갱신 | 프로젝트 첫 인상 |

---

## 8. 본인 검증해보기

지금 상태에서 작동 확인:

```bash
# 기존 명령 (v1)
harness init                            # v1 compose 생성
harness list                            # provider 자산 (v1/v2 무관)

# 새 명령 (v2)
harness validate --standard standard_v2 # v2 검증
harness upgrade --dry-run               # v1 → v2 미리보기
harness upgrade                         # 실 마이그레이션
```

---

## 9. 정리

**현재 = 두 시스템이 공존하지만 v1 이 primary**:

- ✅ v2 인프라 (lib/, standard_v2/, manifest schema, validate, upgrade) 완비
- ✅ 마이그레이션 도구 (upgrade) 통과
- ✅ provider adapter 는 v1/v2 무관하게 작동
- ❌ Claude Code 의 hook 들이 여전히 v1 자산 사용
- ❌ 새 프로젝트 시작 시 v1 으로 init 됨
- ❌ install/remove 같은 기존 명령은 v1 만 다룸

**다음 큰 결정: Cutover 시점**. v2 가 충분히 검증됐다 판단하면 `mv` 두 번으로 primary 전환. 그 후 Phase E (기존 명령 v2 적응) + Phase F (docs) 로 마무리.
