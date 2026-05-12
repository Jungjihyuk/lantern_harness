#!/bin/bash
# harness init — 현재 디렉토리에 .harness/ 초기 설정.

set -euo pipefail

HARNESS_HOME="$HOME/.harness"
PROJECT_ROOT="$(pwd)"
HARNESS_DIR="$PROJECT_ROOT/.harness"

if [[ -d "$HARNESS_DIR" ]]; then
  echo "Error: .harness/ 이미 존재. 먼저 제거하거나 다른 디렉토리에서 실행." >&2
  exit 1
fi

echo "Initializing harness in: $PROJECT_ROOT"

# 0. git 저장소 보장 (진화 추적·.gitignore 의미 있으려면 git 필수)
if [[ ! -d "$PROJECT_ROOT/.git" ]]; then
  if command -v git >/dev/null 2>&1; then
    git -C "$PROJECT_ROOT" init -q
    echo "✓ git init (없어서 새로 생성)"
  else
    echo "⚠ git 없음. 진화 추적 기능 동작하지 않음."
  fi
fi

# 1. 디렉토리 생성 — v2 구조 (.harness/{know-how, runtime, evolution})
#    standard/ symlink 는 v2 에서 불필요 — resolver 가 ~/.harness/standard 직접 발견.
mkdir -p "$HARNESS_DIR"/{know-how,runtime,evolution}

# 2. compose.yaml (v2 default — SSOT)
cat > "$HARNESS_DIR/compose.yaml" <<'YAML'
# compose.yaml v2 — 5 도메인 활성화 매핑.
# 모든 entry 는 id 로 artifact 참조. `harness validate` 가 일관성 검증.
# AGENTS.md 는 매 세션 자동 생성 (cognition.instructions + rules 기반).

version: 2

cognition:
  instructions:
    - agents_md                  # standard 의 시스템 prefix 텍스트
  context:
    required: []                 # 사용자 채우기. 예: [{id: project_readme, src_path: README.md}]
    suggested: []                # 필요 시 자율 참조
    triggered: []                # 예: [{id: api_spec, src_path: docs/api-spec.md, when: "src/api/**"}]
  rules: []                      # 행동 규칙 artifact id 리스트
  hooks:
    - {id: session_start, role: prefix_injection}
    - {id: pre_tool_use, role: context_gating}

state:
  hooks:
    - {id: session_start, role: status_init}
    - {id: post_tool_use, role: status_track}

action:
  adapters:
    - claude_adapter             # 필요 시 codex_adapter 추가

guard:
  hooks:
    - {id: pre_tool_use, role: required_check}
    - {id: pre_tool_use, role: cognitive_guard}
    - {id: pre_tool_use, role: loop_detection}
    - {id: permission_request, role: permission_gate}
    - {id: stop, role: stop_validation}
  policies:
    cognitive_guard:
      per_call: {max_diff_lines: 200, max_new_files: 3}
      per_session: {max_changed_files: 10, max_diff_lines: 1000}
      on_breach: ask_human
      bypass_marker: "@harness allow-large"
    loop_detection:
      consecutive_same_path: 3
      on_loop: self_correct
    stop_validation:
      enabled: false
      on_fail: warn
      checks: []                  # 예: [{command: "pytest -x"}, {command: "tsc --noEmit"}]

observe:
  hooks:
    - {id: session_start, role: trace_log}
    - {id: pre_tool_use, role: trace_log}
    - {id: post_tool_use, role: trace_log}
    - {id: post_tool_use, role: metric_collect}
    - {id: post_tool_use_failure, role: trace_log}
    - {id: post_tool_use_failure, role: eval_verdict}
    - {id: post_tool_batch, role: metric_collect}
    - {id: stop, role: trace_log}
YAML

# 4. know-how/ 빈 폴더만 (AGENTS.md는 자동 생성 — 수동 override 원하면 직접 만들기)
# 단, 처음 사용자에게 안내용 placeholder 만 두기:
cat > "$HARNESS_DIR/know-how/README.md" <<'KH'
# know-how/ — 자기 노하우 layering

이 폴더는 "자식 클래스" 역할. 같은 path를 standard로부터 통째 override하거나,
hook chain (`<name>.d/*.sh`) 추가 가능.

## 자주 사용하는 패턴

### AGENTS.md 자동 생성 X, 직접 작성하고 싶을 때
`know-how/AGENTS.md` 파일을 만들어 직접 작성. session_start hook이 compose.yaml 대신
이 파일을 사용.

### Hook 추가
- `know-how/hooks/<name>.sh` — standard hook 통째 override
- `know-how/hooks/<name>.d/10_my_extra.sh` — standard 후 chain 실행

### Skill 추가
- `know-how/skills/<name>/SKILL.md` — 자기 반복 작업 skill
KH

# 5. README
cat > "$HARNESS_DIR/README.md" <<'README'
# .harness — v2 harness for this project

## 빠른 가이드

- `compose.yaml` — **활성화 지도** (v2). 5 도메인(cognition/state/action/guard/observe) 별로 어느 artifact 를 어느 role 로 활성화할지.
- `know-how/` — 자기 자작 artifact (선택). 같은 7 메커니즘 구조 (instructions/hooks/tools/...) 로 추가.
- `runtime/` — 자동 생성 (gitignore). 상태 JSON, trace, AGENTS.md 등.
- `evolution/CHANGELOG.md` — 진화 이력.

> 글로벌 standard 는 `~/.harness/standard/`. resolver 가 자동 발견하므로 프로젝트에 symlink 안 만듦.

## 한눈에 이해하기

- **artifact** = `manifest.yaml` 가진 self-contained 패키지 (id 로 식별)
- **compose.yaml** = 어떤 artifact 를 어느 role 로 활성화할지 매핑
- **standard / know-how** = 두 layer (공인 토대 vs 본인 노하우). 같은 id 충돌 시 에러

## 다음 단계

1. `compose.yaml` 의 `cognition.context.required` 를 본인 프로젝트 path 로 채우기
2. `harness validate` — 검증
3. `harness link claude` — provider hook 등록
4. 새 session 시작 — AGENTS.md 자동 생성 + 가드 자동 활성

## 자주 묻는 것

**Q. AGENTS.md 는?**
A. session_start hook 이 매 세션 `runtime/AGENTS.resolved.md` 에 생성. compose 의 `cognition.instructions` + `cognition.rules` 가 source.

**Q. 본인 artifact 추가는?**
A. `know-how/<mechanism>/<id>/manifest.yaml` + 내용. 그 후 `compose.yaml` 의 적절한 domain 에 entry 추가.

**Q. 글로벌 standard 갱신은?**
A. `~/.harness/standard/` 직접 갱신 — 모든 프로젝트 자동 반영.

**Q. compose schema 검증?**
A. `harness validate` — manifest 형식 + role enum + id 충돌 + entry 매핑 일괄 검사.
README

# 6. evolution/CHANGELOG.md
cat > "$HARNESS_DIR/evolution/CHANGELOG.md" <<'CHANGELOG'
# Harness Evolution Changelog

## [Initial]
### Added
- harness init 초기 설정
CHANGELOG

# 7. .gitignore 갱신
GITIGNORE="$PROJECT_ROOT/.gitignore"
if ! grep -qF ".harness/runtime" "$GITIGNORE" 2>/dev/null; then
  echo "" >> "$GITIGNORE"
  echo "# harness runtime (auto-generated)" >> "$GITIGNORE"
  echo ".harness/runtime/" >> "$GITIGNORE"
fi

# (v2: post_commit hook 제거됨 — git post-commit 자동 등록 비활성화.
#  필요 시 사용자가 직접 hook 추가 가능.)

echo "✓ .harness/ 초기 설정 완료"
echo ""
echo "다음 단계:"
echo "  1. .harness/compose.yaml 의 cognition.context.required 채우기"
echo "  2. harness validate — 설정 검증"
echo "  3. harness link claude (또는 다른 provider)"
echo "  4. 새 session 시작 — 자동 활성"
