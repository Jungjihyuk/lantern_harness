#!/bin/bash
# harness doctor — 설정·의존성·등록 상태 진단.

set +e  # 진단 도중 에러 무시 (모두 점검)

HARNESS_HOME="$HOME/.harness"
PROJECT_ROOT="$(pwd)"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

ok()   { printf "${GREEN}✓${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}⚠${NC} %s\n" "$*"; }
fail() { printf "${RED}✗${NC} %s\n" "$*"; }

section() { printf "\n%s\n" "── $* ──"; }

section "Global harness 설치"
if [[ -d "$HARNESS_HOME/standard" ]]; then
  ok "$HARNESS_HOME/standard 존재"
else
  fail "$HARNESS_HOME/standard 없음 — harness 재설치 필요"
fi

if [[ -x "$HARNESS_HOME/bin/harness" ]]; then
  ok "harness CLI 실행 가능: $HARNESS_HOME/bin/harness"
else
  fail "$HARNESS_HOME/bin/harness 없음/실행 불가"
fi

section "PATH 등록"
if echo "$PATH" | tr ':' '\n' | grep -qF "$HARNESS_HOME/bin"; then
  ok "현재 PATH에 $HARNESS_HOME/bin 있음"
else
  warn "현재 PATH에 없음. .zshrc/.bashrc에 추가 후 새 셸:"
  echo "       export PATH=\"\$HOME/.harness/bin:\$PATH\""
fi
if grep -q ".harness/bin" ~/.zshrc 2>/dev/null || grep -q ".harness/bin" ~/.bashrc 2>/dev/null; then
  ok "쉘 rc 파일에 PATH 등록 흔적"
else
  warn "쉘 rc 파일(.zshrc/.bashrc)에 PATH 등록 안 됨"
fi

section "의존성"
for cmd in python3 jq git; do
  if command -v "$cmd" >/dev/null 2>&1; then
    v="$($cmd --version 2>&1 | head -1)"
    ok "$cmd ($v)"
  else
    fail "$cmd 없음 — 설치 필요"
  fi
done
if python3 -c "import yaml" 2>/dev/null; then
  ok "PyYAML"
else
  fail "PyYAML 없음 — pip3 install pyyaml"
fi

section "현재 프로젝트 ($PROJECT_ROOT)"
if [[ -d "$PROJECT_ROOT/.harness" ]]; then
  ok ".harness/ 존재"
  if [[ -f "$PROJECT_ROOT/.harness/compose.yaml" ]]; then
    ok "compose.yaml 존재"
    if python3 -c "import yaml; yaml.safe_load(open('$PROJECT_ROOT/.harness/compose.yaml'))" 2>/dev/null; then
      ok "compose.yaml YAML 유효"
    else
      fail "compose.yaml YAML 파싱 에러"
    fi
  else
    fail "compose.yaml 없음"
  fi

  for sym in AGENTS.md hooks; do
    p="$PROJECT_ROOT/.harness/standard/$sym"
    if [[ -L "$p" ]]; then
      target="$(readlink "$p")"
      if [[ -e "$p" ]]; then
        ok "standard/$sym → $target"
      else
        fail "standard/$sym 깨진 symlink → $target"
      fi
    elif [[ -e "$p" ]]; then
      warn "standard/$sym 가 symlink 아님 (forked/local)"
    else
      warn "standard/$sym 없음 — harness install $sym 권장"
    fi
  done

  if [[ -d "$PROJECT_ROOT/.git" ]]; then
    ok ".git/ 존재 (진화 추적 가능)"
    if [[ -f "$PROJECT_ROOT/.git/hooks/post-commit" ]] && grep -qF "harness" "$PROJECT_ROOT/.git/hooks/post-commit"; then
      ok "git post-commit hook 설치됨 (CHANGELOG 자동 갱신)"
    else
      warn "git post-commit hook 없음 — harness init 재실행 또는 수동 설치"
    fi
  else
    warn ".git/ 없음 — 진화 추적 비활성"
  fi
else
  warn "이 디렉토리에 .harness/ 없음. 'harness init' 실행 필요."
fi

section "Claude Code 어댑터"
SETTINGS="$PROJECT_ROOT/.claude/settings.local.json"
if [[ -f "$SETTINGS" ]]; then
  if grep -qF "harness/standard/adapters/claude" "$SETTINGS"; then
    ok "프로젝트 settings.local.json에 harness hook 등록됨"
    pre_match="$(jq -r '.hooks.PreToolUse[] | select(.hooks[0].command | tostring | contains("harness")) | .matcher' "$SETTINGS" 2>/dev/null | head -1)"
    if [[ -n "$pre_match" ]]; then
      printf "       PreToolUse matcher: %s\n" "$pre_match"
      if echo "$pre_match" | grep -q "Read"; then
        ok "PreToolUse가 Read 매칭 (timing 정상 동작)"
      else
        warn "PreToolUse가 Read 안 매칭 — harness link claude 재실행 권장"
      fi
    fi
  else
    warn "settings.local.json 있지만 harness hook 미등록 — harness link claude"
  fi
else
  warn "$SETTINGS 없음 — harness link claude 실행 필요"
fi

GLOBAL_SETTINGS="$HOME/.claude/settings.json"
if [[ -f "$GLOBAL_SETTINGS" ]] && grep -qF "harness/standard/adapters/claude" "$GLOBAL_SETTINGS"; then
  warn "글로벌 ~/.claude/settings.json에 harness hook 등록됨 (모든 claude 세션 영향). 의도한 거면 OK."
fi

section "Runtime 상태"
RUNTIME="$PROJECT_ROOT/.harness/runtime"
if [[ -d "$RUNTIME" ]]; then
  n_traces=$(ls "$RUNTIME/traces/" 2>/dev/null | wc -l | tr -d ' ')
  ok "runtime/traces: $n_traces 세션 trace"
  n_sessions=$(ls "$RUNTIME/sessions/" 2>/dev/null | wc -l | tr -d ' ')
  ok "runtime/sessions: $n_sessions 세션 폴더"
else
  warn "runtime/ 없음 (아직 한 번도 hook 동작 안 함)"
fi

echo ""
echo "Done."
