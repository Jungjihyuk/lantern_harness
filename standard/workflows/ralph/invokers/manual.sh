#!/bin/bash
# Manual invoker — 사용자가 prompt를 claude session에 paste, 응답을 파일에 저장.
# 가장 안전·예측 가능. 우리 hook 시스템 그대로 작동.
#
# 인자: <prompt_file> <response_file>
# 종료: 0 success, 1 user abort

set -euo pipefail

PROMPT_FILE="$1"
RESPONSE_FILE="$2"

cat <<EOF
═══════════════════════════════════════════════════════════════
Ralph — User Mediation Mode
다음 프롬프트를 새 claude session에 paste 후, 응답이 끝나면
응답을 다음 파일에 저장하세요:

  $RESPONSE_FILE

저장 후 [ENTER]로 계속, [q]+[ENTER]로 abort.
═══════════════════════════════════════════════════════════════

--- PROMPT ---
EOF
cat "$PROMPT_FILE"
echo "--- /PROMPT ---"
echo ""

read -r -p "응답 저장 완료? [ENTER/q]: " ans
if [[ "$ans" == "q" ]]; then
  echo "abort by user"
  exit 1
fi

if [[ ! -f "$RESPONSE_FILE" ]]; then
  echo "Warning: $RESPONSE_FILE 없음. 빈 파일 생성." >&2
  echo "" > "$RESPONSE_FILE"
fi

echo "✓ 응답 수신 완료"
exit 0
