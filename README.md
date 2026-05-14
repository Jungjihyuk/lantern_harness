<div align="center">

# Lantern Harness

**Lantern** — *the small flame you carry to walk with the agent at human pace.*

작은 등불을 들고 어둠 속을 함께 걷듯, 이 하네스는 LLM 에이전트의 걸음에 사람의 빛을 비춥니다. <br>
시키고 끝내는 게 아니라, 사람의 경험과 노하우가 더 빛나도록 — $\color{#D97706}{\textbf{의존}}$이 아닌 $\color{#D97706}{\textbf{동행}}$을 위한 하네스

<img src="./assets/intro/yagyong_jeong.png" alt="Lantern Harness" width="450"/>

[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-blue)](#요구-사항)
[![Lang](https://img.shields.io/badge/Bash%20%2B%20Python-3.10%2B-orange)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Stars](https://img.shields.io/github/stars/Jungjihyuk/lantern_harness?style=flat&logo=github)](https://github.com/Jungjihyuk/lantern_harness)


</div>


<div align="center">

> <br>
> <strong>"복잡할수록 더 잘 보이게, 흩어질수록 더 잘 모이게."</strong>
> 
> <sub> - Lantern Harness - </sub><br>
> <br>


</div>

<br />

## ⚡️ **빠르게 시작하기**

```bash
curl -fsSL https://raw.githubusercontent.com/Jungjihyuk/lantern_harness/main/install.sh | bash
```

<a href="#-설치-방법"><strong>다른 설치 방법 보기</strong></a>
 · 
<a href="docs/01-입문.md"><strong>📖 입문 문서 읽기</strong></a>

<sub>입문 문서 하나만 읽어도 단일 에이전트는 충분히 운영 가능합니다.</sub>



<br>

## 🪔 Lantern Harness란?

**Lantern Harness**는 LLM 에이전트(Claude Code · Codex 등)와 함께 일하는 *메타-구조*입니다. <br>
- 설계의 두 축은 **`standard`** 와 **`know-how`** <br>
— **standard** 는 도구/도메인 중립의 *검증된 하네스 기본 구성*입니다. **know-how** 에는 *실험적인 하네스* 또는 *프로젝트 성격이 묻어나는 자산*을 둡니다. <br>
- 두 축이 자유롭게 결합되어 하네스 구조를 $\color{#D97706}{\textbf{추가}}$ · $\color{#D97706}{\textbf{수정}}$ · $\color{#D97706}{\textbf{삭제}}$ 하기 쉬운 시스템 <br>
— 검증된 노하우 위에 자기 결을 얹어 빚어갈 수 있습니다.
- 자원은 **5 책임 도메인**(`cognition` / `state` / `action` / `guard` / `observe`) × **7 메커니즘 폴더**(`instructions` / `hooks` / `tools` / `adapters` / `workflows` / `traces` / `evals`) 의 직교 분류로 정리됩니다 — *효과* 와 *구현* 을 분리해 한 자원이 여러 역할로 등록될 수 있게 (N:N). 자세한 framing 은 [`docs/architecture.md`](docs/architecture.md).

### 왜 만들었나

|     | 동기 | 설명 |
| --- | --- | ---|
| 🔍 | **선별과 검증**| 검증된 하네스 패턴이 수없이 쏟아지지만, *내 작업 흐름에 정말 효과가 있는지*는 직접 가늠하지 않으면 모릅니다. `standard` 에는 검증된 기본 구성을, `know-how` 에는 실험적 시도나 프로젝트 성격이 묻어나는 자산을 분리해 두면 — 무엇이 내게 맞고 무엇이 안 맞는지 **각각 떼어 검증**할 수 있습니다.            |
| 🌊 | **개인 노하우의 기여**| 처음엔 *나만 쓰는 작은 노하우*라 생각했어도, 일반 작업에 효용이 보이면 *함께 발전시키고 싶은 마음*이 따라옵니다. `know-how` 의 실험적 자산이 검증을 거쳐 `standard` 로 승격되어, 다른 사람의 작업으로 흘러갑니다.                                                  |
| 📊 | **우리 모두 하네스 엔지니어**| *실제로 내 작업에 효과가 있는가?* 라는 질문에 **직관이 아닌 시각화·기록·데이터**로 답합니다. 매 세션의 흐름이 trace로 남고, viz·eval·improve가 그 데이터를 분석해 보여줍니다 — 사용자가 *하네스 엔지니어가 되어* 자기 시스템을 빚어가는 철학.                                |

## 📌 특징

|     | 기능 | 무엇을 |
| --- | --- | --- |
| 🪝 | **5-Hook 시스템** | Claude 이벤트 5종(`SessionStart` / `UserPromptSubmit` / `PreToolUse` / `PostToolUse` / `Stop`)에 1:1 매핑 — 도구 호출 직전 가로채 자가수정 유도 |
| 🎯 | **AGENTS.md 자동 생성 (SSOT)** | `compose.yaml` (5 도메인 × 7 메커니즘 schema) 에서 `cognition.prefix` + `cognition.context` 3-단(`required` / `triggered` / `suggested`) 합성 → 매 세션 LLM prefix 에 주입 |
| 🛡️ | **인지 한계 가드레일** | Cognitive Guard · Doom Loop 감지 · Stop Validation — *bypass marker*로 의도적 우회 가능 |
| 🔄 | **Ralph 무인 루프** | `state.workflows[ralph]` 에 task·verify 명세만 주고 사람 없이 verify까지 반복 |
| 🪟 | **시각 편집 대시보드** | `harness dashboard` — n8n 스타일 web UI 에서 compose entry CRUD · 노드 drag&drop · 본문 편집 |
| 📊 | **6 viz** | workflow · subagents · bottleneck · eval · improve · prompts 정적 시각화 (`harness viz <type>`) |
| 🧪 | **측정·개선 도구** | Eval 회귀 테스트 · Improve 룰 기반 제안 · LLM-as-judge (claude_cli / codex / manual) |
| 🔌 | **Provider 어댑터** | Claude 1차 + Codex 2차 (driver 구체 구현 — config.toml / skills / MCP) · 표준 envelope 으로 도구 무관 |
| 🌱 | **하네스 자체 진화** | git post-commit으로 CHANGELOG 자동 갱신 · `know-how` → `standard` 승격 (publish 자격 검증) |

---

## 🚀 설치 방법

### A. 빠른 설치

```bash
curl -fsSL https://raw.githubusercontent.com/Jungjihyuk/lantern_harness/main/install.sh | bash
```

한 줄로 끝. 설치 스크립트가 자동으로 repo를 임시 폴더에 받아 `~/.harness/`로 복사합니다.

설치 중 `harness dashboard` 가 사용할 Python deps (`fastapi` / `uvicorn` / `pydantic`) 도 자동으로 user-pip 에 설치됩니다. 건너뛰려면 `SKIP_DASHBOARD_DEPS=1` 환경변수를 함께 설정하세요.

> ⚠️ `curl | bash`는 코드를 검토 없이 실행합니다.


### B. 직접 수정해서 사용하거나 기여하고 싶을 때

```bash
git clone https://github.com/Jungjihyuk/lantern_harness.git
cd lantern_harness
bash install.sh
```

설치가 끝나면 아래와 같이 개인 프로젝트에서 적용해보세요.

```bash
cd <my-project>
harness init                # .harness/ 초기화
harness link claude         # provider hook 등록 (.claude/settings.local.json)

# .harness/compose.yaml 을 편집기로 열어 정책 설정 (cognition.context.required 등)
# 또는: harness dashboard 로 시각 편집기에서 entry 추가/수정

claude                      # 새 세션 열기 (AGENTS.md 자동 주입 + 가드레일 활성)
```

문제 발생 시 `harness doctor` 로 진단.

> ⚠️ **PATH 안내** — install 후 다음 줄을 `~/.zshrc` 또는 `~/.bashrc` 에 추가하세요:
> ```bash
> export PATH="$HOME/.harness/bin:$PATH"
> ```

### 요구 사항

- **macOS** 또는 **Linux**
- **Bash** 4+
- **Python** 3.10+ (PyYAML 필수 — `pip install pyyaml`. `harness dashboard` 사용 시 `fastapi` / `uvicorn` / `pydantic` 도 필요 — install.sh 가 자동 설치)
- **jq** (필수) — `brew install jq` / `apt install jq`
- **git** (진화 추적용)
- **LLM CLI 중 하나 이상**:
  - [`claude`](https://docs.claude.com/claude-code) — 1차 지원
  - `codex` — 2차 지원 (driver 구체 구현 — `~/.codex/config.toml` / skills / MCP 관리. 검증 진행 중)
  - 기타 — 어댑터 추가로 확장 가능

### 제거

```bash
cd lantern_harness
bash uninstall.sh
```

`~/.harness/` 를 안전 백업 후 제거합니다.

---

## ⌨️ 명령어 한눈에 보기

설치 후 사용 가능한 20개 명령. *카테고리별*로 묶어 한 자리에:

```bash
# ─── 시작·연결 ───
harness init              # 현재 프로젝트에 .harness/ 초기화
harness link <provider>   # provider hook 등록 (예: .claude/settings.local.json)
harness unlink <provider> # provider hook 해제
harness reload            # compose.yaml 변경 후 resolved.md 재생성

# ─── 자원 활성화·검증 ───
harness list              # 가용/설치 아티팩트 목록 (--provider / --kind 필터)
harness show <name>       # 특정 아티팩트 상세 (--provider / --kind 필터)
harness enable <name>     # 아티팩트 활성화 (--dry-run 가능)
harness disable <name>    # 아티팩트 비활성화 (--dry-run 가능)
harness validate          # compose.yaml + manifests + roles 통합 검증
harness ctx <budget|...>  # context inspection (cognition entry 별 토큰 등)
harness publish <path>    # know-how → standard 승격 (자격 검증)
harness scaffold <name>   # 프로젝트 문서 빈 뼈대 생성

# ─── 시각 편집·측정 ───
harness dashboard         # n8n 스타일 web 시각 편집기 (compose CRUD · drag&drop · 본문 편집)
harness viz <type>        # 6 viz 렌더러 (workflow/subagents/bottleneck/eval/improve/prompts)
harness viz dashboard     # 라이브 SSE 대시보드 (read-only)
harness eval              # 회귀 테스트 실행 (기본 5 케이스 + 프로젝트 추가분)
harness improve           # 사용 패턴 분석 + 룰 기반 개선 제안
harness judge run         # LLM-as-judge로 응답 정성 평가

# ─── 자동화 (Ralph 무인 루프) ───
harness ralph start       # 무인 루프 시작 (task → verify 반복)
harness ralph status      # 현재 ralph 실행 상태
harness ralph list        # 과거 ralph 실행 기록
harness ralph stop        # 무인 루프 중단

# ─── 진단·메타 ───
harness doctor            # 환경 진단 — 무엇이 깨졌는지 한 줄로
harness version           # 버전·plugin·linked provider 표시
```

자주 쓰는 5개 입문 명령은 [`docs/01-입문.md`](docs/01-입문.md) 9장 — 전체 명령의 옵션·시나리오는 [`docs/02-중급.md`](docs/02-중급.md) 9장 참조.

---

## 🪟 시각 편집 — `harness dashboard`

`compose.yaml` 을 직접 손대지 않고도 entry 를 추가·삭제·이동할 수 있는 **로컬 web 편집기**. n8n 스타일의 노드 그래프 위에서 5 도메인 × 7 메커니즘 구조가 그대로 펼쳐집니다.

```bash
harness dashboard                 # 기본 포트 8766, 브라우저 자동 오픈
harness dashboard --port 9000     # 포트 지정
harness dashboard --no-open       # 브라우저 자동 오픈 끄기
```

할 수 있는 일:
- compose entry **추가 / role 변경 / 삭제** (서버가 `compose.yaml` 안전 저장)
- 노드 **drag&drop** 으로 시각 정렬 (artifact 의 layer 이동 포함)
- artifact 본문(예: `instructions/*/body.md`) **인라인 편집**

포트가 점유돼 있으면 자동으로 다음 free port (최대 10회) 를 시도합니다. 디폴트 8766 은 agentcat daemon 과 충돌 회피 차원의 선택입니다.

> Python deps (`fastapi` / `uvicorn` / `pydantic`) 는 install.sh 가 자동 설치합니다. 수동 설치는 `pip3 install --user fastapi 'uvicorn[standard]' 'pydantic>=2'`.

수동 테스트 시나리오는 [`docs/dashboard-manual-test.md`](docs/dashboard-manual-test.md) 참조.

---

## 🪔 상세 사용법

세 단계의 학습 경로가 마련되어 있습니다 — 천천히, 자기 프로젝트에서 *충분히 굴려본 후* 다음으로.

| 단계 | 문서 | 정체성 |
|---|---|---|
| **입문** | [`docs/01-입문.md`](docs/01-입문.md) | 단일 에이전트를 안전하게 — 방어 메커니즘과 Karpathy 한정 철학 |
| **중급** | [`docs/02-중급.md`](docs/02-중급.md) | 위임·병렬·맥락·품질 — Subagent / Worktree / 세션 공유 / Multi-agent |
| **고급** | [`docs/03-고급.md`](docs/03-고급.md) | Trade-off 마스터 — 안전 ↔ 성능 균형 조절 |

레퍼런스:

| 문서 | 내용 |
|------|------|
| [`docs/architecture.md`](docs/architecture.md) | 5 책임 도메인 × 7 메커니즘 직교 설계 + `compose.yaml` schema 전체 |
| [`docs/system-essence.md`](docs/system-essence.md) | "왜 이렇게 설계했는가" — 핵심 개념의 일관된 뿌리 |
| [`docs/provider-adapter.md`](docs/provider-adapter.md) | provider adapter (claude / codex / 기타) 규약과 envelope |
| [`docs/claude-hook-reference.md`](docs/claude-hook-reference.md) | Claude Hook 시스템 규약·exit code 프로토콜 |
| [`docs/codex-hook-reference.md`](docs/codex-hook-reference.md) | Codex Hook 시스템 규약 + Claude 와의 비교 + harness adapter 매핑 가이드 |
| [`docs/dashboard-manual-test.md`](docs/dashboard-manual-test.md) | `harness dashboard` 수동 테스트 시나리오 |

처음 보는 분은 **입문**부터. 자체 완결되어 있어 단일 에이전트는 입문만으로 충분히 운영 가능합니다.

---

## 🪔 이웃 프로젝트 — `lantern-docs`

Lantern Harness가 **LLM 에이전트의 행동**을 통제한다면, [`lantern-docs`](https://github.com/Jungjihyuk/lantern_docs/tree/main)는 그 위에서 **프로젝트 문서 작성 컨벤션**을 다룹니다 — 기획→설계→구현→배포→운영의 5 단계 흐름과 desktop/mobile/web 3-type 별 템플릿이 마련된 Obsidian 기반 문서 프레임워크.

| 시스템 | 다루는 영역 | 대상 |
|---|---|---|
| **Lantern Harness** *(이 repo)* | LLM 에이전트의 *행동* 통제 | LLM (AI) |
| **Lantern Docs** *(이웃 repo)* | 프로젝트 *문서 작성* 컨벤션·템플릿 | 사람 (팀) |

---

## 🤝 기여 방법

기여는 언제든 환영합니다. 🪔

1. **이슈로 먼저 의견을** — 버그 / 기능 / 문서 무엇이든 좋습니다.
2. 논의가 정리되면 포크 → 브랜치(`feature/#이슈번호-짧은-설명`) → PR.
3. 이 시스템은 *살아있는 메타-구조*로 설계되었습니다. 사용 중에 발견한 패턴·개선은:
   - 자기 프로젝트의 `know-how/` 에서 검증
   - 일정 기간 안정적이면 `harness publish` 로 standard 승격
   - PR로 이 repo에 기여

자세한 진화 메커니즘은 [`docs/02-중급.md`](docs/02-중급.md) 12장(진화 추적) 참조.

---

## 📄 라이센스

| 영역 | 라이센스 | 요약 |
|------|----------|------|
| 소스 코드 | [MIT License](LICENSE) | 자유로운 사용·수정·재배포 가능 |
| 문서 (`docs/`) | MIT (코드와 동일) | 동일 조건 |
| 이미지·자산 (`assets/`) | [© All Rights Reserved](assets/LICENSE) | Lantern Harness 프로젝트 식별 용도로만 사용 가능 |

---

## ✨ 기여자

<div align="center">
<a href="https://github.com/Jungjihyuk">
<img src="https://avatars.githubusercontent.com/u/33630505?v=4" width="100px;" alt=""/><br />
<sub><b>정지혁</b></sub></a><br />
<a href="https://github.com/Jungjihyuk/lantern_harness/commits/main/?author=Jungjihyuk" title="Code">🛠️</a>


🪔 *Made with a small flame.*

</div>
