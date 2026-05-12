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

# 1. 디렉토리 생성
mkdir -p "$HARNESS_DIR"/{standard,know-how/hooks,know-how/skills,runtime,evolution}

# 2. standard symlinks (compose.yaml에 적힌 것들)
ln -sfn "$HARNESS_HOME/standard/AGENTS.md" "$HARNESS_DIR/standard/AGENTS.md"
ln -sfn "$HARNESS_HOME/standard/hooks" "$HARNESS_DIR/standard/hooks"

# 3. compose.yaml (default — SSOT)
cat > "$HARNESS_DIR/compose.yaml" <<'YAML'
# compose.yaml — 이 프로젝트 하네스의 단일 출처(SSOT).
# 이 파일만 편집하면 동작·정책 모두 바뀜.
# AGENTS.md는 이 파일로부터 매 세션 자동 생성됨 (know-how/AGENTS.md로 override 가능).

mode: human-gated      # | ralph

prefix:
  - AGENTS.md

plugins:
  - hooks

hooks:
  session_start:        enabled    # SessionStart — AGENTS.md 주입·status 초기화
  user_prompt_submit:   enabled    # UserPromptSubmit — 가드레일(input filter, placeholder)
  pre_tool_use:         enabled    # PreToolUse — Required·trigger·loop·cognitive 검사
  post_tool_use:        enabled    # PostToolUse — status·trace·timing 갱신
  stop:                 enabled    # Stop — 응답 완료 전 작업 검증 (stop_validation)

# === 컨텍스트 정책 (AGENTS.md가 여기로부터 생성됨) ===

required_context:
  # 시작 시 반드시 읽어야 할 문서들
  default_on_deny: self_correct      # self_correct(부드럽게) | hard_stop(엄격)
  paths:
    - { path: README.md,  label: "프로젝트 정의" }
    # 보안·DB 등 빡빡하게 강제하고 싶은 항목은 on_deny 명시:
    # - { path: SECURITY.md, label: "보안 정책", on_deny: hard_stop }

on_demand_context:
  # 필요할 때 lazy 읽기
  paths: []
    # - { path: docs/system-design.md, label: "시스템 설계" }

trigger_read:
  # 특정 도구 호출 패턴 시 강제 읽기.
  # match_path: glob 패턴 (Edit/Write 의 file_path와 매칭)
  # require: 추가로 읽어야 하는 문서 path
  # on_deny: self_correct (default) | hard_stop
  []
  # - { match_path: "**/*.sql",         require: docs/data-spec.md, on_deny: hard_stop }
  # - { match_path: "src/api/**",       require: docs/api-spec.md }
  # - { match_path: "**/.env*",         require: SECURITY.md,       on_deny: hard_stop }

hard_rules:
  # 변경 거의 없는 강제선 (LLM prefix에 직접 박힘 — 압축 안 됨)
  - "Required Context를 읽지 않은 채 코드 변경 금지"
  - "Trigger 매칭 시 해당 문서를 먼저 읽고 작업"

# === 인지 한계 가드 ===
cognitive_guard:
  enabled: true
  per_call:
    max_diff_lines: 200
    max_new_files: 3
  per_session:
    max_changed_files: 10
    max_diff_lines: 1000
  on_breach: ask_human
  bypass_marker: "@harness allow-large"

# === Doom loop 감지 (같은 path를 의미 없이 반복 수정) ===
loop_detection:
  enabled: true
  consecutive_same_path: 3       # 같은 path 연속 N번 수정 시 차단
  on_loop: self_correct           # | hard_stop

# === LLM-as-judge (정성 평가) ===
# prompt-응답 쌍을 LLM이 0~10점으로 채점. 'harness judge run'으로 수동 트리거.
# backend 3종:
#   claude_cli — `claude -p` 비대화 모드 (claude code 구독 활용)
#   codex      — `codex exec` 비대화 모드 (codex CLI 구독 활용)
#   manual     — 사용자 직접 채점 (콘솔 입력)
llm_judge:
  enabled: false
  backend: claude_cli                 # claude_cli | codex | manual
  claude_cli:
    # claude -p 사용
  codex:
    # codex exec 사용
  manual:
    # 콘솔 입력으로 채점
  # prompt_template: "..."             # 커스텀 평가 프롬프트 (옵션)

# === 응답 완료 전 작업 검증 (stop hook이 실행) ===
# claude의 응답이 끝나려는 시점(Stop)에 발동. checks 모두 통과해야 정상 완료.
# 비용 ↑ — 매 응답에 실행됨. 처음엔 enabled: false로 두고 필요 시 활성화.
stop_validation:
  enabled: false
  on_fail: warn                   # warn (경고만) | block (응답 차단, claude 재작업 유도)
  checks: []
    # - { command: "pytest -x" }
    # - { command: "tsc --noEmit" }
    # - { script: ./know-how/checks/no-todo.sh }

# === Ralph (mode: ralph 일 때만) ===
# ralph:
#   task: ./know-how/ralph-task.md
#   max_iterations: 20
#   stuck_threshold: 3
#   on_stuck: ask_human
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
# .harness — generalized harness for this project

## 빠른 가이드

- `compose.yaml` — **SSOT** (Single Source of Truth). 이 파일만 편집하면 동작·정책 다 바뀜.
- `standard/` — 글로벌 `~/.harness/standard/`의 symlink (수정 X, 시스템이 관리).
- `know-how/` — 자기 노하우 (override·추가, gitignore 가능).
- `runtime/` — 자동 생성 (gitignore). AGENTS.md/status JSON/trace 보관.
- `evolution/CHANGELOG.md` — 진화 이력.

## 한눈에 이해하기

`standard/`(공식 기본값)와 `know-how/`(개인 노하우)는 **부모-자식 관계**예요.
"부모 그대로 쓰거나, 일부만 갈아끼우거나, 새걸 추가하거나" 셋 중 하나.

- **그대로 쓰기**: `know-how/`를 비워두면 → standard가 그대로 적용됨
- **갈아끼우기**: `know-how/<같은이름>` 만들면 → standard 무시, 내 것 사용
- **뒤에 추가하기**: `know-how/hooks/<이름>.d/*.sh` 두면 → standard 실행 후 내 스크립트 차례로 실행

## 다음 단계

1. `compose.yaml`의 `required_context.paths`를 자기 프로젝트 path로 채우기.
2. `harness link claude` — provider hook 등록 (프로젝트 로컬).
3. 새 claude session 시작 — 자동으로 AGENTS.md 생성 + Required 강제 시작.

## 자주 묻는 것

**Q. AGENTS.md는 어디 있나?**
A. `runtime/AGENTS.resolved.md`에 매 세션 자동 생성. `compose.yaml`로부터 derived.
   직접 쓰고 싶으면 `know-how/AGENTS.md` 만들면 그게 우선.

**Q. 자기 hook 추가하려면?**
A. `know-how/hooks/<name>.d/10_my_hook.sh` 작성. standard hook 후 chain 실행됨.

**Q. 글로벌 standard는 어떻게 갱신?**
A. `~/.harness/standard/` 직접 갱신. 모든 프로젝트가 자동 반영.
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

# 8. git post-commit hook 설치 (진화 추적)
GIT_HOOKS="$PROJECT_ROOT/.git/hooks"
if [[ -d "$GIT_HOOKS" ]]; then
  HOOK="$GIT_HOOKS/post-commit"
  HARNESS_LINE="$HOME/.harness/standard/hooks/post_commit/post_commit.sh \"\$(git rev-parse --show-toplevel)\""
  if [[ ! -f "$HOOK" ]]; then
    cat > "$HOOK" <<EOF
#!/bin/bash
# harness evolution tracking
$HARNESS_LINE
EOF
    chmod +x "$HOOK"
    echo "✓ git post-commit hook 설치 (진화 자동 추적)"
  elif ! grep -qF ".harness/standard/hooks/post_commit/post_commit.sh" "$HOOK"; then
    echo "" >> "$HOOK"
    echo "# harness evolution tracking" >> "$HOOK"
    echo "$HARNESS_LINE" >> "$HOOK"
    chmod +x "$HOOK"
    echo "✓ 기존 post-commit에 harness 진화 hook 추가"
  fi
fi

echo "✓ .harness/ 초기 설정 완료"
echo ""
echo "다음 단계:"
echo "  1. .harness/compose.yaml 의 required_context.paths 를 프로젝트에 맞게 수정"
echo "  2. (옵션) harness scaffold --all  — 빈 README/SECURITY/DESIGN/CONVENTIONS 생성"
echo "  3. harness link claude (또는 다른 provider)"
echo "  4. 새 claude session 시작 — AGENTS.md는 매 세션 자동 생성됨"
