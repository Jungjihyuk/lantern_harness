#!/bin/bash
# harness publish <path> — know-how → 글로벌 standard로 승격.
# 표준 자격 4기준 검증 + 사용자 확인 + audit log.
#
# 옵션:
#   --yes                인터랙티브 Y/N 건너뜀. --reason 필수.
#   --reason "<설명>"     승격 사유 (audit log에 기록)
#   --force              모든 검증 우회 (위험). --reason 권장.
#   --as <new-path>      다른 이름으로 promote (예: publish know-how/skills/foo --as skills/team-foo)

set -euo pipefail

HARNESS_HOME="$HOME/.harness"
PROJECT_ROOT="$(pwd)"

# 옵션 파싱
SRC_REL=""
YES=0
FORCE=0
REASON=""
AS_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes) YES=1; shift ;;
    --force) FORCE=1; shift ;;
    --reason) REASON="${2:-}"; shift 2 ;;
    --as) AS_PATH="${2:-}"; shift 2 ;;
    -h|--help)
      cat <<USAGE
Usage: harness publish <know-how-path> [options]

Options:
  --yes                 인터랙티브 건너뜀 (--reason 필수)
  --reason "<text>"     승격 사유 (audit log)
  --force               모든 검증 우회 (위험)
  --as <new-path>       다른 이름으로 (예: --as skills/team-foo)

표준 자격 4기준:
  1. 항상 적용되어야 하는가         [수동 — 도메인 판단]
  2. 압축되면 손해가 큰가            [자동 — prefix 적합성]
  3. 짧게 표현 가능한가              [자동 — 크기]
  4. 프로젝트 무관 보편적인가         [수동 — 도메인 판단]

후보 폴더에 publishable.yaml 있으면 1·4 자동:
  universal: true
  always_applicable: true
  reason: "..."
USAGE
      exit 0 ;;
    *)
      if [[ -z "$SRC_REL" ]]; then
        SRC_REL="$1"
      else
        echo "Error: unexpected arg: $1" >&2; exit 1
      fi
      shift ;;
  esac
done

if [[ -z "$SRC_REL" ]]; then
  echo "Usage: harness publish <know-how-path> [--yes] [--reason \"...\"] [--force] [--as <path>]" >&2
  exit 1
fi

src="$PROJECT_ROOT/.harness/$SRC_REL"

# 기본 가드
if [[ ! -e "$src" ]]; then
  echo "Error: $src 존재 안 함" >&2
  exit 1
fi
case "$SRC_REL" in
  know-how/*) ;;
  *) echo "Error: know-how/ 하위만 publish 가능" >&2; exit 1 ;;
esac

# 대상 path
DST_REL="${AS_PATH:-${SRC_REL#know-how/}}"
dst="$HARNESS_HOME/standard/$DST_REL"

if [[ -e "$dst" ]]; then
  echo "Error: 글로벌에 이미 존재: $dst" >&2
  echo "       다른 이름으로 가려면 --as <new-path> 사용" >&2
  exit 1
fi

# ---------- 자동 검증 (자격 2, 3) ----------

echo "표준 자격 검증:"

# (3) 크기 검증
if [[ -d "$src" ]]; then
  total_size=$(find "$src" -type f -exec wc -c {} + 2>/dev/null | awk 'END{print $1}')
  file_count=$(find "$src" -type f | wc -l | tr -d ' ')
else
  total_size=$(wc -c < "$src" | tr -d ' ')
  file_count=1
fi
total_kb=$((total_size / 1024))
size_ok=1
if [[ $total_size -gt 100000 ]]; then  # 100KB 초과 시 경고
  echo "  ⚠ 크기: $file_count files, ${total_kb}KB (대용량 — '짧게 표현' 자격 의심)"
  size_ok=0
else
  echo "  ✓ 크기: $file_count files, ${total_kb}KB (적절)"
fi

# (2) Prefix 적합성: standard 평평한 path에 .md 직접이면 prefix 후보, 그 외엔 N/A
prefix_check="N/A"
if [[ "$DST_REL" == *.md && "$DST_REL" != */* ]]; then
  # 표준 md 후보 (예: DESIGN.md). 4 블록 구조 검증
  if grep -qE "^## (Required Context|On-Demand Context|Trigger|Hard Rules)" "$src" 2>/dev/null; then
    echo "  ✓ Prefix 적합성: 표준 md 형식 부합"
    prefix_check="ok"
  else
    echo "  ⚠ Prefix 적합성: 4-블록 구조 아님 (prefix 주입엔 부적절)"
    prefix_check="warn"
  fi
fi

# ---------- 사전 선언 publishable.yaml ----------
PUBLISHABLE=""
if [[ -d "$src" && -f "$src/publishable.yaml" ]]; then
  PUBLISHABLE="$src/publishable.yaml"
fi

universal=""
always=""
yaml_reason=""

if [[ -n "$PUBLISHABLE" ]] && command -v python3 >/dev/null 2>&1; then
  vals="$(python3 -c "
import yaml
with open('$PUBLISHABLE') as f: d = yaml.safe_load(f) or {}
print(d.get('universal', ''))
print(d.get('always_applicable', ''))
print(d.get('reason', ''))
")"
  universal="$(echo "$vals" | sed -n '1p')"
  always="$(echo "$vals" | sed -n '2p')"
  yaml_reason="$(echo "$vals" | sed -n '3p')"
  echo "  ℹ publishable.yaml 발견: universal=$universal, always_applicable=$always"
fi

# ---------- 자격 1, 4 (도메인 판단) ----------

if [[ $FORCE -eq 1 ]]; then
  echo "  ⚠ --force: 자격 1, 4 검증 건너뜀"
  if [[ -z "$REASON" ]]; then
    echo "Error: --force 시 --reason 권장 (audit log)"
    REASON="(force, no reason)"
  fi
elif [[ -n "$universal" && -n "$always" ]]; then
  # publishable.yaml에 답변 있음
  if [[ "$universal" != "True" && "$universal" != "true" ]]; then
    echo "Error: publishable.yaml에 universal: false — promote 거부"
    exit 1
  fi
  if [[ "$always" != "True" && "$always" != "true" ]]; then
    echo "Error: publishable.yaml에 always_applicable: false — promote 거부"
    exit 1
  fi
  echo "  ✓ 자격 1, 4: publishable.yaml에서 확인됨"
  REASON="${REASON:-$yaml_reason}"
elif [[ $YES -eq 1 ]]; then
  if [[ -z "$REASON" ]]; then
    echo "Error: --yes 시 --reason 필수 (audit log)" >&2
    exit 1
  fi
  echo "  ⚠ --yes: 자격 1, 4 건너뜀 (--reason: $REASON)"
else
  echo ""
  echo "다음 질문에 답변 (도메인 판단):"
  read -r -p "  Q1. 다른 프로젝트에도 보편적으로 적용 가능한가? [y/N]: " q1
  read -r -p "  Q4. 항상 적용되어야 하는가 (가끔 X)? [y/N]: " q4
  if [[ "$q1" != "y" && "$q1" != "Y" ]]; then
    echo "  ✗ 자격 4 (보편성) 미충족 → 취소"
    exit 1
  fi
  if [[ "$q4" != "y" && "$q4" != "Y" ]]; then
    echo "  ✗ 자격 1 (항상 적용) 미충족 → 취소"
    exit 1
  fi
  if [[ -z "$REASON" ]]; then
    read -r -p "승격 사유 (한 줄): " REASON
  fi
fi

# ---------- 이동 ----------
mkdir -p "$(dirname "$dst")"
if [[ -d "$src" ]]; then
  cp -R "$src" "$dst"
else
  cp "$src" "$dst"
fi

echo ""
echo "✓ Promoted: $SRC_REL → $dst"
[[ -n "$REASON" ]] && echo "  사유: $REASON"

# ---------- Audit log ----------
LOG="$PROJECT_ROOT/.harness/evolution/publish-log.jsonl"
mkdir -p "$(dirname "$LOG")"
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
mode="interactive"
[[ -n "$PUBLISHABLE" ]] && mode="yaml"
[[ $YES -eq 1 ]] && mode="yes-flag"
[[ $FORCE -eq 1 ]] && mode="force"

if command -v jq >/dev/null 2>&1; then
  jq -nc --arg ts "$ts" --arg src "$SRC_REL" --arg dst "$DST_REL" \
         --arg reason "$REASON" --arg mode "$mode" \
    '{ts:$ts, src:$src, dst:$dst, reason:$reason, mode:$mode}' >> "$LOG"
fi

echo ""
echo "참고: 원본 ($SRC_REL)은 know-how에 그대로 있음."
echo "       다른 프로젝트가 사용하려면 'harness install $DST_REL'"
