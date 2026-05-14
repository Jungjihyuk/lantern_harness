#!/bin/bash
# Lantern Harness installer.
# 이 repo의 standard/lib/bin을 ~/.harness/로 복사.
# 기존 ~/.harness/가 있으면 자동 백업.
#
# 세 가지 호출 방식 모두 지원:
#   1. curl -fsSL .../install.sh | bash         (stdin 파이프)
#   2. curl -o install.sh ... && bash install.sh (검토 후 실행)
#   3. git clone ... && bash install.sh          (로컬 clone)

set -euo pipefail

REPO_URL="${LANTERN_REPO:-https://github.com/Jungjihyuk/lantern_harness.git}"
REPO_BRANCH="${LANTERN_BRANCH:-main}"
DEST="$HOME/.harness"

# 호출 방식 감지: 로컬에서 실행한 건지 / curl|bash 같은 stdin 실행인지
SCRIPT_DIR=""
if [[ "${BASH_SOURCE[0]:-}" != "" ]]; then
  candidate_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"
  # v1: standard/AGENTS.md, v2: standard/roles.yaml — 어느 쪽이든 있으면 dev repo
  if [[ -n "$candidate_dir" && ( -f "$candidate_dir/bin/harness" || -f "$candidate_dir/standard/roles.yaml" ) ]]; then
    SCRIPT_DIR="$candidate_dir"
  fi
fi

# Source 결정
if [[ -n "$SCRIPT_DIR" ]]; then
  SRC="$SCRIPT_DIR"
  CLEANUP=""
else
  # stdin 또는 standalone install.sh — 임시 폴더에 repo clone
  if ! command -v git >/dev/null 2>&1; then
    echo "Error: git이 필요합니다 (repo clone용)." >&2
    exit 1
  fi
  TMPDIR="$(mktemp -d)"
  CLEANUP="$TMPDIR"
  echo "Cloning $REPO_URL ($REPO_BRANCH) ..."
  git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$TMPDIR/lantern" -q
  SRC="$TMPDIR/lantern"
fi

# 종료 시 임시 폴더 정리
[[ -n "$CLEANUP" ]] && trap 'rm -rf "$CLEANUP"' EXIT

echo ""
echo "Lantern Harness installer"
echo "  source: $SRC"
echo "  dest:   $DEST"
echo ""

# 기존 설치 백업
if [[ -d "$DEST" ]]; then
  BAK="$DEST.bak.$(date +%s)"
  echo "기존 ~/.harness/ 발견 → $BAK 로 백업"
  mv "$DEST" "$BAK"
fi

# 복사
mkdir -p "$DEST"
cp -R "$SRC/standard" "$DEST/standard"
cp -R "$SRC/lib"      "$DEST/lib"
cp -R "$SRC/bin"      "$DEST/bin"

# 글로벌 know-how 빈 폴더
mkdir -p "$DEST/know-how"

# registry.yaml 복사 (있으면)
[[ -f "$SRC/registry.yaml" ]] && cp "$SRC/registry.yaml" "$DEST/registry.yaml"

# 실행권한 보장
chmod +x "$DEST/bin/harness" 2>/dev/null || true
find "$DEST/bin/cmd" -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true
find "$DEST/standard" -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true

echo ""
echo "✓ 파일 복사 완료."

# dashboard Python deps — optional. SKIP_DASHBOARD_DEPS=1 로 건너뜀.
if [[ "${SKIP_DASHBOARD_DEPS:-0}" != "1" ]]; then
  if command -v python3 >/dev/null 2>&1 && python3 -m pip --version >/dev/null 2>&1; then
    if ! python3 -c "import fastapi, uvicorn, pydantic" >/dev/null 2>&1; then
      echo ""
      echo "harness dashboard deps 설치 중 (fastapi / uvicorn / pydantic)…"
      python3 -m pip install --user --quiet --disable-pip-version-check \
        fastapi 'uvicorn[standard]' 'pydantic>=2' 2>&1 \
        | grep -v "WARNING: The script" || true
      echo "✓ dashboard deps 설치 완료."
    fi
  else
    echo ""
    echo "⚠ python3 / pip 미발견. dashboard 사용하려면 별도로:"
    echo "    pip3 install --user fastapi 'uvicorn[standard]' 'pydantic>=2'"
  fi
fi

echo ""
echo "다음 단계:"
echo "  1. PATH에 추가 (~/.zshrc 또는 ~/.bashrc):"
echo "       export PATH=\"\$HOME/.harness/bin:\$PATH\""
echo "  2. 새 셸 열거나 source ~/.zshrc"
echo "  3. 프로젝트에서:"
echo "       harness init"
echo "       harness link claude"
echo "       harness dashboard       # 시각 편집기 (n8n 스타일)"
echo ""
echo "처음 사용자는 docs/01-입문.md 부터 읽어보세요."
