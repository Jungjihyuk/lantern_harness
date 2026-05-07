#!/bin/bash
# harness install <name> — 글로벌 plugin을 프로젝트 .harness/standard/로 symlink.
set -euo pipefail

HARNESS_HOME="$HOME/.harness"
PROJECT_ROOT="$(pwd)"
PROJ_HARNESS="$PROJECT_ROOT/.harness"

if [[ $# -eq 0 ]]; then
  echo "Usage: harness install <name>" >&2
  exit 1
fi

if [[ ! -d "$PROJ_HARNESS" ]]; then
  echo "Error: 이 디렉토리에 .harness/ 없음. 먼저 'harness init' 실행." >&2
  exit 1
fi

name="$1"
src="$HARNESS_HOME/standard/$name"
dst="$PROJ_HARNESS/standard/$name"

if [[ ! -e "$src" ]]; then
  echo "Error: 글로벌에 '$name' 없음 ($src)" >&2
  echo "Available:" >&2
  ls "$HARNESS_HOME/standard/" >&2
  exit 1
fi

if [[ -e "$dst" ]]; then
  echo "Error: 이미 설치됨: $dst" >&2
  exit 1
fi

ln -sfn "$src" "$dst"
echo "✓ Installed: $name → $src"

# compose.yaml 갱신 — plugin이면 plugins:, md면 prefix:에 추가
ACTIVE="$PROJ_HARNESS/compose.yaml"
if [[ -f "$ACTIVE" ]] && command -v jq >/dev/null 2>&1; then
  if [[ -d "$src" ]]; then
    # plugin
    if ! grep -qE "^\s*-\s+$name\s*$" "$ACTIVE"; then
      # plugins: 섹션에 추가 (단순 sed)
      awk -v p="$name" '
        /^plugins:/ { print; in_plugins=1; next }
        in_plugins && /^[a-zA-Z]/ {
          print "  - " p
          in_plugins=0
        }
        { print }
        END { if (in_plugins) print "  - " p }
      ' "$ACTIVE" > "$ACTIVE.tmp" && mv "$ACTIVE.tmp" "$ACTIVE"
      echo "  compose.yaml plugins에 추가됨"
    fi
  elif [[ "$name" == *.md ]]; then
    if ! grep -qE "^\s*-\s+$name\s*$" "$ACTIVE"; then
      awk -v p="$name" '
        /^prefix:/ { print; in_prefix=1; next }
        in_prefix && /^[a-zA-Z]/ {
          print "  - " p
          in_prefix=0
        }
        { print }
        END { if (in_prefix) print "  - " p }
      ' "$ACTIVE" > "$ACTIVE.tmp" && mv "$ACTIVE.tmp" "$ACTIVE"
      echo "  compose.yaml prefix에 추가됨"
    fi
  fi
fi
