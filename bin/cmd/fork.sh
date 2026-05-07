#!/bin/bash
# harness fork <name> — symlink로 연결된 글로벌 plugin을 프로젝트 로컬 복사본으로 변환.
# 변환 후 프로젝트만 수정해도 글로벌 영향 X (분리됨).
# 단점: 글로벌 standard 업데이트 자동 반영 X.

set -euo pipefail

PROJECT_ROOT="$(pwd)"
PROJ_HARNESS="$PROJECT_ROOT/.harness"

if [[ ! -d "$PROJ_HARNESS" ]]; then
  echo "Error: .harness/ 없음. 'harness init' 먼저." >&2
  exit 1
fi

if [[ $# -eq 0 ]]; then
  echo "Usage: harness fork <name>"
  echo ""
  echo "현재 standard/ 상태:"
  for entry in "$PROJ_HARNESS"/standard/*; do
    [[ -e "$entry" ]] || continue
    n="$(basename "$entry")"
    if [[ -L "$entry" ]]; then
      printf "  %-20s → %s  [symlink — 글로벌 공유]\n" "$n" "$(readlink "$entry")"
    elif [[ -d "$entry" ]]; then
      printf "  %-20s [forked — 로컬 사본]\n" "$n"
    else
      printf "  %-20s [파일]\n" "$n"
    fi
  done
  echo ""
  echo "Fork 후엔 'harness remove <name>' + 'harness install <name>'으로 symlink로 복귀 가능."
  exit 0
fi

name="$1"
target="$PROJ_HARNESS/standard/$name"

if [[ ! -e "$target" && ! -L "$target" ]]; then
  echo "Error: 설치되지 않음: $name" >&2
  echo "       'harness install $name' 먼저." >&2
  exit 1
fi

if [[ ! -L "$target" ]]; then
  echo "Error: '$name'은 이미 symlink가 아님 (이미 forked 또는 로컬)" >&2
  exit 1
fi

resolved="$(readlink "$target")"
if [[ ! -e "$resolved" ]]; then
  echo "Error: symlink 대상 없음: $resolved" >&2
  exit 1
fi

# Symlink 제거 → 실제 복사
rm "$target"
cp -R "$resolved" "$target"

echo "✓ Forked: $name"
echo "  was: symlink → $resolved"
echo "  now: 로컬 사본 ($target)"
echo ""
echo "이제 이 프로젝트만의 변형을 자유롭게 수정 가능."
echo "글로벌 업데이트 다시 받으려면: harness remove $name && harness install $name"
