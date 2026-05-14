# Provider Adapter — `harness list / show / disable / enable`

`harness` 가 Claude Code · Codex 같은 외부 provider 들이 설치한 아티팩트 (MCP · skill · plugin) 를 **한 곳에서 보고 제어** 할 수 있도록 만든 어댑터 레이어.

현재 지원:
- **통합 뷰** — `harness list`, `harness show`
- **활성 / 비활성 토글** — `harness disable`, `harness enable`
- **두 provider** — Claude / Codex 둘 다 동일 인터페이스로 제어

향후 후보:
- `harness remove` — 가장 위험, 백업 정책 필요
- bundle / package 개념

> 관련 conversation: 5축 책임축(cognition/state/action/guard/observe) × 7 메커니즘 폴더 × standard/know-how 소유축 설계 논의 결과의 첫 실체화. 본 문서는 그 중 **action 도메인의 adapters 메커니즘** 부분에 해당.

## 목차

1. [#1. 왜 만들었나](#1-왜-만들었나)
2. [#2. 설계 결정](#2-설계-결정)
3. [#3. 컴포넌트 구조](#3-컴포넌트-구조)
4. [#4. 파일별 상세](#4-파일별-상세)
5. [#5. 데이터 흐름](#5-데이터-흐름)
6. [#6. 사용법](#6-사용법)
7. [#7. 한계와 다음 단계](#7-한계와-다음-단계)
8. [부록](#부록-본-설계가-큰-그림에서-차지하는-위치)

---

## 1. 왜 만들었나

### 1.1 문제

`/plugin` (Claude Code)·Codex의 자체 명령 등으로 설치한 자산이 **provider별로 흩어져 저장**된다:

- Claude Code MCPs → `~/.claude/mcp.json`
- Claude Code skills → `~/.claude/skills/<name>/SKILL.md`
- Claude Code plugins → `~/.claude/plugins/installed_plugins.json` + `~/.claude/settings.json`
- Codex MCPs / plugins → `~/.codex/config.toml` (한 파일에 통합, TOML 포맷)
- Codex skills → `~/.codex/skills/<name>/SKILL.md` (Claude 와 동일 형식)

사용자는 provider마다 다른 명령·다른 위치를 외워야 했다. **무엇이 어디 깔려 있는지, 어느 게 켜져 있는지, 끄려면 어디를 만져야 하는지 한눈에 보는 수단이 없음.**

### 1.2 의도

`harness` = provider들 **위의 통합 control plane**. 한 명령어로:

- 모든 provider의 설치 상태 조회 (`harness list`)
- 단건 상세 확인 (`harness show <name>`)
- 활성/비활성 토글 (`harness disable/enable <name>`)
- (장차) 삭제·설치도 한 곳에서

각 provider의 native 문법을 사용자가 외울 필요 없이 driver가 캡슐화.

---

## 2. 설계 결정

### 2.1 모델: "import & own"이 아니라 **"discover & federate"**

provider가 깐 파일을 harness가 **소유·복제하지 않는다**. 원본 위치 그대로 두고 harness는 **읽어서 정규화**해 통합 뷰만 제공. 변경이 필요할 때(disable 등)는 provider 자체 메커니즘을 우선 활용.

이유:
- provider가 자체 갱신할 수 있어 사용자가 잡아두면 sync 깨짐
- harness가 모든 provider runtime을 재현할 필요 없음 (실행은 provider에게 위임)
- read·disable·enable은 위임 가능, install은 provider 자체 명령이 이미 있음

### 2.2 driver 패턴 (provider 추상화)

각 provider별로 `driver.py` 한 개. 동일 인터페이스(`ProviderDriver`) 구현.

```
adapters/
├── base.py        # ProviderDriver 추상 + Item dataclass + ItemNotFound 예외
├── registry.py    # driver 자동 발견 + dispatch + get_driver(id)
├── list.py        # `harness list` CLI 엔트리
├── show.py        # `harness show` CLI 엔트리
├── disable.py     # `harness disable` 진입점 (실 로직은 _mutation.py)
├── enable.py      # `harness enable` 진입점
├── _mutation.py   # disable/enable 공통 CLI 로직 (matching, dry-run, idempotent)
├── claude/
│   └── driver.py  # Claude Code 전용 driver
└── codex/
    └── driver.py  # Codex 전용 driver (자체 minimal TOML 파서 포함)
```

driver 추가 = `adapters/<provider>/driver.py` 한 파일만 작성. registry가 자동 발견.

### 2.3 정규화된 `Item` 모델

provider별로 다른 데이터 구조를 **공통 dataclass** 한 형태로 normalize.

```python
@dataclass
class Item:
    name: str       # 표시 이름 (provider/kind 안에서만 유효 — unique id 아님)
    provider: str   # "claude" 등
    kind: str       # mcp | skill | plugin
    enabled: bool   # 활성 여부
    source: str     # 출처 파일 경로
    meta: dict      # version, scope, command, trigger 등 추가 정보
```

이 정규화 덕분에 출력 포맷터(`list.py`, `show.py`)와 CLI 로직(`_mutation.py`)이 provider 무관하게 작동.

**`name`은 unique id가 아님**: 같은 `name`이 서로 다른 (provider, kind) 조합에서 중복될 수 있다.
정확 지칭은 `(provider, kind, name)` 셋으로 한다 — show/disable/enable 명령이 `--provider`/`--kind` 필터를 받는 이유.

### 2.4 list.sh 호환성 보존

`bin/cmd/list.sh`는 원래 harness 내부 아티팩트(standard md, plugin folders, know-how)만 보여줬다. 그 동작을 그대로 두고 **provider 섹션만 뒤에 추가**. 플래그(`--provider/--kind/--json`)를 주면 harness 내부 섹션은 생략하고 provider 섹션만 출력.

### 2.5 코드 / 데이터 분리 (XDG)

mutation에 따른 사용자 데이터(예: disable된 MCP 백업)는 **`~/.harness/` 밖**에 저장한다.

```
~/.harness/                              # install.sh 가 통째로 갈아엎는 코드/standard 영역
${XDG_DATA_HOME:-~/.local/share}/harness/   # 사용자 데이터, install이 절대 못 건드림
└── state/
    └── claude/
        └── mcp_backup.json              # disabled MCP의 원본 설정 백업
```

`install.sh`가 `~/.harness/`를 갈아엎어도 사용자 데이터는 안전. 이 분리가 없으면 단순 install 한 번이 disable 백업을 날려버려 **실데이터 손실**이 발생함 (실제 개발 도중 한 번 노출됨).

---

## 3. 컴포넌트 구조

```
사용자
  │
  ▼
[harness <verb>]              ← bin/cmd/{list,show,disable,enable}.sh
  │
  ▼
[adapters/{list,show,disable,enable}.py]   ← Python CLI 엔트리 (argparse)
  │                                            disable/enable은 _mutation.py 공유
  ▼
[adapters/registry.py]        ← driver 자동 발견 + list_all + get_driver
  │
  ├──────────────┐
  ▼              ▼
[claude/driver]  [codex/driver]   ← provider 별 구현체 (둘 다 활성)
  │              │
  │              └─read→ ~/.codex/config.toml + ~/.codex/skills/
  │              └─write→ ~/.codex/config.toml (line surgery)
  │                       ${XDG_DATA_HOME}/harness/state/codex/   (MCP 백업)
  ├──read──→    ~/.claude/...      (mcp.json, skills/, plugins/, settings.json)
  └──write→     ~/.claude/...      (disable/enable 시)
                ${XDG_DATA_HOME}/harness/state/claude/   (MCP 백업)
```

각 driver는 provider의 config 파일을 읽어/쓰며 `Item` 리스트로 반환. registry가 모아 정렬·반환. 포맷터가 표/JSON 출력 또는 mutation 분기.

---

## 4. 파일별 상세

### 4.1 `lib/adapters/base.py`

추상 인터페이스 + 데이터 모델 + 예외.

```python
KINDS = ("mcp", "skill", "plugin")

@dataclass
class Item:
    name: str
    provider: str
    kind: str
    enabled: bool
    source: str
    meta: dict = field(default_factory=dict)

class ItemNotFound(LookupError):
    """disable/enable 대상이 provider 상태에 없을 때."""

class ProviderDriver(ABC):
    id: str = ""

    @abstractmethod
    def list(self, kind: Optional[str] = None) -> list[Item]: ...

    @abstractmethod
    def disable(self, kind: str, name: str) -> bool: ...
        # True: 변경됨, False: 이미 disabled (idempotent), 없으면 ItemNotFound

    @abstractmethod
    def enable(self, kind: str, name: str) -> bool: ...
```

**역할**:
- `KINDS` 튜플로 지원 아티팩트 종류 고정 (argparse choices에도 재사용)
- `Item`이 모든 provider의 정규화된 표현
- `ProviderDriver` ABC가 driver 계약 강제. 메서드 추가 = 본 파일 수정 + 각 driver 갱신

### 4.2 `lib/adapters/registry.py`

driver 동적 발견 + 통합 호출.

핵심 API:

```python
def discover_drivers() -> list[ProviderDriver]
def list_all(kind=None, provider=None) -> list[Item]
def get_driver(provider_id: str) -> Optional[ProviderDriver]   # 신규
```

**동적 로딩**: `importlib.util.spec_from_file_location()`로 `adapters/<provider>/driver.py`를 직접 로드. 한 driver 실패는 try/except로 흡수 → 나머지는 정상 동작.

**get_driver 추가 이유**: mutation CLI가 매치된 Item 의 `provider`로 정확한 driver를 찾아 disable/enable 메서드를 호출해야 함.

### 4.3 `standard/adapters/claude/driver.py`

Claude Code 전용 driver. `ClaudeDriver(ProviderDriver)`.

#### 데이터 소스

| 작업 | 위치 |
|---|---|
| MCP 읽기 | `~/.claude/mcp.json` |
| MCP 쓰기 (disable) | `~/.claude/mcp.json` (제거) + `${XDG_DATA_HOME}/harness/state/claude/mcp_backup.json` (백업) |
| Skill 읽기 | `~/.claude/skills/<dir>/SKILL.md` 또는 `SKILL.md.disabled` |
| Skill 쓰기 (disable) | `SKILL.md` ↔ `SKILL.md.disabled` rename |
| Plugin 읽기 | `~/.claude/plugins/installed_plugins.json` (메타) + `~/.claude/settings.json` (`enabledPlugins`) |
| Plugin 쓰기 (disable) | `~/.claude/settings.json.enabledPlugins[name]` 토글 |

#### `list()` — disabled 상태 반영

- `_list_mcps()` — mcp.json (enabled) + mcp_backup.json (disabled) **둘 다 읽어** 통합
- `_list_skills()` — skill 폴더에 `SKILL.md`가 있으면 enabled, `SKILL.md.disabled`만 있으면 disabled로 표시
- `_list_plugins()` — `installed_plugins.json` 에 있는 모든 plugin을 listing, `settings.json.enabledPlugins[name] = false`면 disabled로 마킹

모든 Item의 `meta` 에 일관된 field 채움: `scope`, `version` (+ kind별 추가 정보). list 출력이 세 kind 모두 동일 컬럼이라 가능.

#### `disable()` / `enable()`

kind dispatch:

```python
def disable(kind, name):
    if kind == "mcp":    return self._disable_mcp(name)
    if kind == "skill":  return self._disable_skill(name)
    if kind == "plugin": return self._disable_plugin(name)
```

**`_disable_mcp`**:
- `mcp.json`에서 해당 entry 추출 → `mcp_backup.json`에 추가
- `mcp.json`에서 제거
- 이미 backup에 있고 mcp.json에 없으면 no-op (False 반환)

**`_enable_mcp`**:
- `mcp_backup.json`에서 entry 추출 → `mcp.json`에 재삽입
- 양쪽 atomic write

**`_disable_skill` / `_enable_skill`**: `SKILL.md` ↔ `SKILL.md.disabled` 사이 `os.rename`. Claude Code는 `SKILL.md` 파일명만 로드하므로 `.disabled` suffix면 자동 무시.

**`_disable_plugin` / `_enable_plugin`**: `settings.json` 읽음 → `enabledPlugins[name] = false/true` 토글 → atomic write. 다른 키(`extraKnownMarketplaces` 등) 절대 손상 X.

#### 안전 헬퍼

- `_read_json(path, default)` — 파일 없음·JSON 깨짐 → default 반환 (예외 throw X)
- `_write_json_atomic(path, data)` — tmp 파일 작성 후 `os.replace` → 중간 중단 시에도 원본 보존
- `_find_skill_dir(name)` — frontmatter `name` 매치 우선, 없으면 폴더명 매치

#### 데이터 디렉토리

```python
def _harness_data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME")
    return Path(base or Path.home() / ".local" / "share") / "harness"

HARNESS_STATE_DIR = _harness_data_dir() / "state" / "claude"
MCP_BACKUP = HARNESS_STATE_DIR / "mcp_backup.json"
```

XDG 표준 준수. `install.sh`가 `~/.harness/`를 갈아엎어도 영향 없음.

### 4.4 `standard/adapters/codex/driver.py`

Codex CLI 전용 driver. `CodexDriver(ProviderDriver)`.

#### 데이터 소스

| 작업 | 위치 |
|---|---|
| MCP 읽기 | `~/.codex/config.toml` 의 `[mcp_servers.<name>]` 섹션 |
| MCP 쓰기 (disable) | `config.toml` 에서 섹션 제거 + `${XDG_DATA_HOME}/harness/state/codex/mcp_backup.json` 백업 |
| Skill 읽기 | `~/.codex/skills/<dir>/SKILL.md` 또는 `SKILL.md.disabled` (Claude 와 동일 형식) |
| Skill 쓰기 (disable) | `SKILL.md` ↔ `SKILL.md.disabled` rename |
| Plugin 읽기 | `~/.codex/config.toml` 의 `[plugins."<id>"]` 섹션 + `enabled` 키 |
| Plugin 쓰기 (disable) | `config.toml` 의 해당 섹션에서 `enabled = true/false` 토글 |

Claude 와 비교: Codex 는 **MCP·plugin 모두 단일 파일(`config.toml`)** 에 통합. Claude 는 4개 파일에 분산.

#### 자체 minimal TOML 파서

`tomli`/`tomllib` 같은 외부 의존 없이 Python 표준 라이브러리(`re`)만 사용한 자체 파서.
PyYAML 회피하고 `_parse_frontmatter` 자체 작성한 것과 동일 원칙 (standalone 운영).

**지원 패턴**:
- 섹션 헤더 `[a.b]` / `[plugins."name@source"]`
- 단순 key-value (string / bool / int / float / 배열)
- 주석 (`#`)

**미지원** (Codex 케이스에 불필요):
- inline table (`{ k = v }`)
- multi-line string (`"""..."""`)
- dotted keys (단일 라인)
- array of tables (`[[...]]`) — 만나면 skip

자체 파서가 작동하는 부분만 처리하고, 모르는 라인은 silently skip. Codex 가 향후 더 복잡한 TOML 사양 도입 시 보강 필요.

#### config.toml 쓰기 — line-level surgery

disable/enable 시 전체 파일 재생성하지 않고 **해당 섹션 line block 만 편집**. 다른 섹션·주석·formatting 보존.

**`_find_section_block(lines, section)`**: 섹션 헤더부터 다음 섹션 직전까지 `[start, end)` 반환.

**`_toggle_bool_in_block(lines, start, end, key, target)`**: 정규식 매치로 `<key> = true/false` 라인 찾아 target 값으로 교체. 없으면 False 반환 (호출자가 새로 삽입).

**MCP enable 시 섹션 복원**: 백업 dict 를 `[mcp_servers.<name>]` 헤더 + `_render_toml_kv()` 가 생성한 단순 key-value 라인들로 직렬화 후 파일 끝에 append.

#### 안전 헬퍼

- `_read_text(path)` — 파일 없으면 빈 문자열 (예외 X)
- `_write_text_atomic(path, text)` — tmp 작성 후 `os.replace`
- 모든 list 메서드: 파일/디렉토리 없으면 빈 list 반환 (Codex 미설치 환경 graceful)

### 4.5 `lib/adapters/list.py`

argparse 기반 CLI 엔트리.

**옵션**:
```
--provider <id>            특정 provider만  (choices는 registry 동적 발견)
--kind <mcp|skill|plugin>  특정 종류만
--json                     JSON 출력
```

**출력 포맷 — 세 kind 모두 동일 컬럼**:

```python
_LIST_COLUMNS = [
    ("Name", 42),
    ("Provider", 10),
    ("Status", 10),     # enabled / disabled
    ("Scope", 10),      # user / local / project
    ("Version", 14),
]
```

상세 정보(MCP command, skill description, plugin install_path 등)는 list에서 빼고 **`harness show`에 일임** — 사용자가 "스캐닝은 list, 상세는 show" 라는 명확한 흐름 갖도록.

`--provider` choices는 `discover_drivers()` 결과로 동적 채움 — Codex driver 추가되면 `--provider {claude,codex}`로 자동 갱신.

### 4.6 `lib/adapters/show.py`

`harness show <name>` 의 CLI 엔트리. list가 표라면 show는 **수직 key:value + (skill의 경우) 본문 일부**로 한 건의 깊은 뷰.

**매칭 규칙**:
- 인자 `<name>` 만 → `it.name == <name>` 정확 일치 검색
- 매치 1개 → 상세 출력
- 0개 → not found + 유사 후보 힌트 (부분 문자열 매치)
- 2개 이상 → `--provider X --kind Y` 추천 안내
- `--provider` / `--kind` 가 있으면 후보부터 그 조건으로 좁힘

**kind별 포맷터**:
- MCP: command, args
- Skill: trigger, description 전체, **SKILL.md 본문 (`--full` 전체 / `--lines N` 지정 / 기본 20줄)**
- Plugin: version, scope, install_path, project_path, git_commit_sha, installed_at, last_updated

**skill 본문 출력 제어 (mutually exclusive)**:
- `--full` → 전체 본문
- `--lines N` → 앞 N줄
- 둘 다 없으면 기본 20줄 + "(N줄 더)" 안내

**exit code**:
- `0` — 매치 1개, 정상 출력
- `1` — not found
- `2` — disambiguation 필요

### 4.7 `lib/adapters/_mutation.py`

disable / enable 공통 CLI 로직. `disable.py` / `enable.py` 가 본 모듈의 `run(verb)` 만 호출.

**4단계 흐름**:

1. **name 으로 후보 좁히기** — `list_all(kind, provider)` + name 정확 매치 (show 와 동일 로직)
2. **idempotency 검사** — 이미 목표 상태면 `⊙ 이미 disabled/enabled` 출력 + exit 0
3. **dry-run** — `--dry-run` 이면 실제 변경 없이 `[dry-run] ... → verb 예정` 출력
4. **driver 메서드 호출** — `get_driver(item.provider).disable/enable(kind, name)` 실행

**exit code**:
- `0` — 성공 (변경 또는 no-op)
- `1` — 매치 0개
- `2` — 매치 2개 이상
- `3` — driver 조회 실패
- `4` — `ItemNotFound` (provider 상태에서 못 찾음)
- `5` — 기타 mutation 예외

### 4.8 `lib/adapters/disable.py` / `enable.py`

각각 `_mutation.run("disable")` / `_mutation.run("enable")` 만 호출하는 얇은 진입점. verb 외 동작은 동일.

### 4.9 `bin/cmd/{list,show,disable,enable}.sh`

shell 래퍼들. 공통 패턴:

```bash
HARNESS_HOME="$HOME/.harness"
entry="$HARNESS_HOME/standard/adapters/<verb>.py"
[[ ! -f "$entry" ]] && { echo "Error: 미설치"; exit 1; }
command -v python3 >/dev/null || { echo "Error: python3 필요"; exit 1; }
exec python3 "$entry" "$@"
```

argparse 가 usage / -h / 잘못된 인자 자체 처리하므로 shell 단의 하드코딩 usage는 두지 않음.

### 4.10 `bin/harness` (dispatcher)

git-style CLI. case whitelist에 새 verb 추가 + usage 텍스트 갱신. **이 단계를 빠뜨리면 verb 호출 시 `unknown command` 에러**.

```bash
case "$cmd" in
  init|link|unlink|list|show|disable|enable|install|remove|...)
    exec "$CMD_DIR/$cmd.sh" "$@"
    ;;
```

---

## 5. 데이터 흐름

### 5.1 `harness list`

```
1. bin/cmd/list.sh
   ├─ harness 내부 섹션 (md / plugin / know-how) 출력
   └─ python3 ~/.harness/lib/adapters/list.py "$@"
2. adapters/list.py — argparse 파싱
3. registry.list_all(kind, provider)
4. discover_drivers() → adapters/*/driver.py 동적 로드
5. 각 driver.list(kind)
   ClaudeDriver:
     _list_mcps()    — mcp.json + mcp_backup.json 통합
     _list_skills()  — SKILL.md / SKILL.md.disabled 인지
     _list_plugins() — installed_plugins.json + settings.json.enabledPlugins
6. list[Item] → list.py 가 5컬럼 표 출력 (또는 --json)
```

### 5.2 `harness disable / enable <name>`

```
1. bin/cmd/<verb>.sh → python3 .../adapters/<verb>.py
2. <verb>.py → _mutation.run(verb)
3. _mutation:
   ├─ list_all() 로 후보 수집
   ├─ name 정확 매치
   ├─ idempotency 검사 (이미 목표 상태면 0 반환)
   ├─ --dry-run 이면 의도만 출력
   └─ registry.get_driver(item.provider) → driver.disable/enable(kind, name)
4. driver:
   ├─ mcp:    mcp.json ↔ mcp_backup.json 양방향 이동 (atomic JSON write)
   ├─ skill:  SKILL.md ↔ SKILL.md.disabled rename
   └─ plugin: settings.json.enabledPlugins[name] 토글
5. 결과 출력 ("✓ ... → disabled/enabled" 또는 "⊙ 이미 ...")
```

**한 driver 실패는 다른 driver에 영향 X** — registry 가 try/except 흡수.

---

## 6. 사용법

### 6.1 `harness list`

```bash
harness list                        # harness 내부 + provider 통합
harness list --kind mcp             # MCP만 (harness 섹션 생략)
harness list --kind skill --json    # skill JSON
harness list --provider claude      # provider 필터
```

세 kind 모두 동일 5컬럼:
```
Name                  Provider    Status      Scope       Version
--------------------  ----------  ----------  ----------  --------------
graphify              claude      enabled     user        
ouroboros             claude      enabled     user        
context-mode@...      claude      enabled     user        1.0.53
```

### 6.2 `harness show <name>`

단건 상세. **kind/provider 필터 없으면 name 정확 일치로 자동 탐색**.

```bash
harness show graphify
harness show ouroboros                       # MCP (plugin은 'ouroboros@ouroboros'라 별개)
harness show ouroboros@ouroboros             # plugin
harness show <name> --provider claude --kind mcp   # 충돌 시 좁히기

# 없는 이름 → 유사 후보 힌트
$ harness show langchain
'langchain' 일치 항목 없음
유사 후보:
  langchain-dependencies  (provider=claude, kind=skill)
  ...

harness show graphify --json
harness show graphify              # skill 본문 앞 20줄 + 안내
harness show graphify --lines 50   # 앞 50줄
harness show graphify --full       # 전체
```

### 6.3 `harness disable / enable <name>`

특정 아티팩트를 활성/비활성. 매칭 규칙은 show 와 동일.

```bash
harness disable graphify                            # skill 비활성
harness enable graphify                             # 다시 활성
harness disable ouroboros --kind mcp                # MCP 비활성 (백업 자동)
harness disable swift-lsp@claude-plugins-official   # plugin 비활성
harness disable graphify --dry-run                  # 의도만 출력
```

**kind별 메커니즘**:

| kind | disable | enable | 백업 |
|---|---|---|---|
| **mcp** | `mcp.json` 에서 entry 제거 | 백업에서 복원 | `${XDG_DATA_HOME:-~/.local/share}/harness/state/claude/mcp_backup.json` |
| **skill** | `SKILL.md` → `SKILL.md.disabled` | 반대 rename | 없음 (rename) |
| **plugin** | `settings.json.enabledPlugins[name] = false` | `= true` | 없음 (native) |

**Claude Code 인지**:
- plugin: 다음 세션부터 `enabledPlugins` 반영
- skill: `SKILL.md` 없으면 자동 무시
- mcp: `mcp.json` 비어 있으면 미로드

**idempotency**: 이미 목표 상태면 `⊙` 출력 + exit 0.

### 6.4 두 명령의 매칭 동일성

show/disable/enable 모두 같은 매칭 로직 사용:
1. name 정확 일치로 후보 좁힘
2. `--provider`/`--kind` 가 있으면 그것도 적용
3. 매치 0개 → not found, 2개 이상 → disambiguation 안내

→ 한 번 익히면 세 명령 모두 같은 사용감.

### 6.5 스크립트와 결합

```bash
# 모든 disabled 아이템 이름 추출
harness list --json | jq -r '.[] | select(.enabled == false) | .name'

# 설치된 MCP 이름 목록
harness list --kind mcp --json | jq -r '.[].name'

# 특정 plugin 설치 여부
harness list --kind plugin --json | jq '.[] | select(.name | contains("ouroboros"))'
```

`--provider` choices 는 **registry 동적 발견 결과** — Codex driver 추가 시 자동으로 `--provider {claude,codex}`로 확장 (하드코딩 X).

---

## 7. 한계와 다음 단계

### 7.1 현재 한계

1. **plugin 중복 scope 표현 부족** — 동일 plugin이 user/local 양쪽에 설치되어 있어도 첫 항목만 대표. 향후 멀티 scope 표시 고려.
2. **remove 없음** — 하드 삭제는 미구현. 백업 정책 결정 후 진행 예정.
3. **bundle 개념 없음** — 같은 패키지가 MCP + plugin 둘로 노출되는 경우(예: ouroboros), 사용자가 두 번 disable 해야 함. 향후 manifest 기반 bundle 도입 고려.
4. **이미 열린 provider 세션은 변경 미반영** — disable/enable 결과는 다음 세션부터 인식됨. provider 자체 동작이라 harness가 해결할 수 없음.
5. **Codex 자체 TOML 파서 한계** — inline table / multi-line / array of tables 미지원. 현재 Codex `config.toml` 케이스엔 충분하지만, 향후 Codex 가 고급 사양 도입 시 보강 필요.

### 7.2 다음 단계 (우선순위 후보)

| 작업 | 작업량 | 가치 |
|---|---|---|
| `harness remove <name>` | 중간 | 가장 위험, 백업 정책 필요 |
| bundle / package 개념 | 큼 | UX 개선 — 묶음 한 번에 토글 |

### 7.3 driver 추가 가이드 (Codex 등)

새 provider 추가는 3단계:

1. `standard/adapters/<provider>/driver.py` 생성
2. `ProviderDriver` 상속 + `id` 클래스 변수 + `list/disable/enable` 메서드 구현
3. 끝. registry가 자동 발견.

**참조 패턴**:

```python
from base import ProviderDriver, Item, ItemNotFound

class CodexDriver(ProviderDriver):
    id = "codex"

    def list(self, kind=None):
        items = []
        if kind in (None, "mcp"):
            items.extend(self._list_mcps())
        # ...
        return items

    def disable(self, kind, name):
        if kind == "mcp":    return self._disable_mcp(name)
        if kind == "skill":  return self._disable_skill(name)
        if kind == "plugin": return self._disable_plugin(name)
        raise ValueError(f"지원되지 않는 kind: {kind}")

    def enable(self, kind, name):
        # ...
```

`claude/driver.py` 가 reference implementation. `Item(name=..., meta={"scope":..., "version":...})` 만 정직하게 채우면 list/show 자동 동작.

---

## 부록: 본 설계가 큰 그림에서 차지하는 위치

| 큰 그림 요소 | 위치 |
|---|---|
| **5 책임 도메인** (cognition/state/action/guard/observe) | `action` 도메인 |
| **7 메커니즘 폴더** (instructions/hooks/tools/adapters/workflows/traces/evals) | `adapters` 메커니즘 |
| **2 소유 축** (standard/know-how) | `standard` (외부 import 통합은 standard에 위치, 본인 작성 driver는 know-how 가능) |
| **lifecycle 도구** (scan/import/promote/adopt/upgrade) | `harness list` = scan, `disable/enable` = 가벼운 lifecycle 제어 |

본 구현으로 검증된 원칙:

1. **discover & federate** — provider가 깐 것을 owner로 두고 harness는 view + thin control 만
2. **코드/데이터 분리** — install이 갈아엎어도 사용자 데이터는 XDG 영역에 안전
3. **driver 인터페이스 통일** — 새 provider 추가는 driver.py 한 파일 (registry 자동 발견)
4. **N:N 정직성** — `name`은 unique id 아님, `(provider, kind, name)` 셋이 진짜 키
5. **dispatcher 동기 잊지 않기** — verb 추가 시 `bin/harness` whitelist 갱신 필수 (한 번 빠뜨려 트러블 발생함)
6. **외부 의존 zero, standalone 운영** — PyYAML / tomli 모두 회피, 우리 use case 에 맞춰 자체 파서 작성

### Codex driver 추가로 검증된 일반성

Codex driver 를 추가하면서 **공통 코드(`base.py` / `registry.py` / `_mutation.py` / `list.py` / `show.py`)는 한 줄도 수정하지 않음**. driver 폴더 하나만 추가했고, 모든 통합 명령이 자동으로 새 provider 를 인지·제어. 추상화 누수 없음 = ProviderDriver 인터페이스가 정말 일반적이었다는 강한 증거.

**두 driver 비교** (인터페이스가 같은 도구를 다른 provider에 적용한 결과):

| 측면 | Claude | Codex |
|---|---|---|
| MCP 저장 | `mcp.json` 단독 (JSON) | `config.toml` 안 섹션 (TOML) |
| Plugin 메타 | `installed_plugins.json` 별도 | `config.toml` 안 섹션 |
| Plugin 토글 | `settings.json.enabledPlugins[id]` | `config.toml.plugins."id".enabled` |
| Skill | `<dir>/SKILL.md` (YAML frontmatter) | **동일** |
| 파일 수정 패턴 | JSON load → dict 수정 → JSON dump | TOML line-level surgery (섹션 block 보존) |
| 외부 의존 | 없음 (stdlib `json`) | 없음 (자체 minimal TOML 파서) |

같은 인터페이스(`list/disable/enable`) 가 두 매우 다른 storage 모델 위에서 동일하게 작동.

이번 구현은 **action.adapters 메커니즘의 두 번째 실체** + **lifecycle 도구의 4개 명령**(list, show, disable, enable) 이 두 provider 에서 모두 검증됨. 다음 단계로 `remove` / `install` 이 붙고 향후 다른 provider (예: Cursor) 가 추가되면 본 구조가 일반 시스템으로 자리잡는다.
