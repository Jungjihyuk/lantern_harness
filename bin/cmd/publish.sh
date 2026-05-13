#!/bin/bash
# harness publish <know-how-artifact-path> — know-how → standard 승격.
#
# 입력: know-how 안의 artifact 폴더 (manifest.yaml 가진).
# 동작:
#   1. manifest.yaml 파싱 → id, mechanism 확보
#   2. 같은 id 가 standard 에 이미 있으면 충돌 → 거부
#   3. 사용자 확인 + reason 받음
#   4. 폴더 통째 ~/.harness/standard/<mechanism>/<id>/ 로 cp
#   5. ~/.harness/evolution/publish-log.jsonl 에 audit log 추가
#   6. know-how 폴더 정리 안내 (resolver 가 양쪽 발견 시 IdConflict 에러)
#
# 옵션:
#   --reason "<text>"     승격 사유 (audit log 기록, 필수)
#   --yes                 인터랙티브 confirm 건너뜀 (--reason 필수)

set -euo pipefail

HARNESS_HOME="$HOME/.harness"

# dev fallback for standard root
STANDARD_ROOT="$HARNESS_HOME/standard"
if [[ ! -d "$STANDARD_ROOT" ]]; then
  DEV_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
  if [[ -d "$DEV_ROOT/standard" ]]; then
    STANDARD_ROOT="$DEV_ROOT/standard"
  fi
fi

EVOLUTION_DIR="$HOME/.harness/evolution"

# ─────────────── 옵션 파싱 ───────────────
SRC=""
REASON=""
YES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes) YES=1; shift ;;
    --reason) REASON="${2:-}"; shift 2 ;;
    --reason=*) REASON="${1#--reason=}"; shift ;;
    -h|--help)
      cat <<USAGE
Usage: harness publish <know-how-artifact-path> [options]

know-how 의 artifact 폴더를 글로벌 standard 로 승격.

Options:
  --reason "<text>"     승격 사유 (audit log 에 기록, 필수)
  --yes                 인터랙티브 confirm 건너뜀

예:
  harness publish .harness/know-how/hooks/my_pre_tool_use --reason "팀 공통 가드"
  harness publish .harness/know-how/instructions/company_rules --reason "회사 규약"
USAGE
      exit 0 ;;
    -*) echo "Error: unknown option '$1'" >&2; exit 1 ;;
    *) SRC="$1"; shift ;;
  esac
done

# ─────────────── 검증 ───────────────
if [[ -z "$SRC" ]]; then
  echo "Error: artifact 경로 필요" >&2
  echo "Usage: harness publish <know-how-artifact-path> --reason \"<...>\"" >&2
  exit 1
fi

if [[ ! -d "$SRC" ]]; then
  echo "Error: 폴더 없음: $SRC" >&2
  exit 1
fi

MANIFEST="$SRC/manifest.yaml"
if [[ ! -f "$MANIFEST" ]]; then
  echo "Error: manifest.yaml 없음: $MANIFEST" >&2
  exit 1
fi

# manifest 에서 id + mechanism 파싱 (python)
read -r ID MECHANISM <<< "$(python3 -c "
import yaml, sys
m = yaml.safe_load(open('$MANIFEST'))
print(m.get('id', ''), m.get('mechanism', ''))
" 2>/dev/null)"

if [[ -z "$ID" ]]; then
  echo "Error: manifest 의 id 필드 비어있음" >&2
  exit 1
fi
if [[ -z "$MECHANISM" ]]; then
  echo "Error: manifest 의 mechanism 필드 비어있음" >&2
  exit 1
fi

# 표준 mechanism 검증
case "$MECHANISM" in
  instructions|hooks|tools|adapters|workflows|traces|evals) ;;
  *) echo "Error: 알 수 없는 mechanism '$MECHANISM' (7 메커니즘 중 하나여야 함)" >&2; exit 1 ;;
esac

# 충돌 검사
DEST="$STANDARD_ROOT/$MECHANISM/$ID"
if [[ -d "$DEST" ]]; then
  echo "Error: id 충돌 — standard 에 이미 '$ID' 존재 ($DEST)" >&2
  echo "  resolver 가 IdConflict 에러를 내므로 publish 거부." >&2
  echo "  override 원하면 know-how 의 id 를 다른 이름으로 변경 후 publish." >&2
  exit 2
fi

# ─────────────── 사용자 확인 ───────────────
echo ""
echo "publish candidate:"
echo "  id:        $ID"
echo "  mechanism: $MECHANISM"
echo "  source:    $SRC"
echo "  dest:      $DEST"
echo ""

if [[ $YES -eq 0 ]]; then
  read -r -p "publish? (y/N) " ans
  if [[ "$ans" != "y" && "$ans" != "Y" ]]; then
    echo "취소됨."
    exit 0
  fi
  if [[ -z "$REASON" ]]; then
    read -r -p "reason (필수): " REASON
  fi
fi

if [[ -z "$REASON" ]]; then
  echo "Error: --reason 필수 (audit log 에 기록)" >&2
  exit 1
fi

# ─────────────── 복사 ───────────────
mkdir -p "$STANDARD_ROOT/$MECHANISM"
cp -R "$SRC" "$DEST"
echo "✓ copied: $SRC → $DEST"

# ─────────────── audit log ───────────────
mkdir -p "$EVOLUTION_DIR"
LOG="$EVOLUTION_DIR/publish-log.jsonl"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# JSON escape reason (python)
REASON_JSON=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$REASON")

cat >> "$LOG" <<JSON
{"timestamp":"$TS","id":"$ID","mechanism":"$MECHANISM","source":"$SRC","dest":"$DEST","reason":$REASON_JSON}
JSON

echo "✓ audit log: $LOG"
echo ""
echo "다음 단계 — 충돌 회피를 위해 know-how 의 원본 폴더 정리:"
echo "  rm -rf \"$SRC\""
echo ""
echo "또는 know-how 의 id 를 다른 이름으로 변경 (양쪽 보존 시)."
