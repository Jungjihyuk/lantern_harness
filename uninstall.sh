#!/bin/bash
# Lantern Harness uninstaller.
# ~/.harness/를 제거. 백업본은 그대로 둠.

set -euo pipefail

DEST="$HOME/.harness"

if [[ ! -d "$DEST" ]]; then
  echo "~/.harness/가 없음. 제거할 게 없습니다."
  exit 0
fi

echo "이 작업은 ~/.harness/ 전체를 제거합니다."
echo "  대상: $DEST"
echo ""
echo "기존 백업본(~/.harness.bak.*)은 그대로 둡니다."
echo ""
read -r -p "계속하시겠어요? [y/N]: " ans
if [[ "$ans" != "y" && "$ans" != "Y" ]]; then
  echo "취소"
  exit 0
fi

# 마지막 안전 백업
SAFETY="$DEST.bak.uninstall.$(date +%s)"
mv "$DEST" "$SAFETY"
echo "✓ ~/.harness/ 제거 (안전 백업: $SAFETY)"
echo ""
echo "PATH에서 제거하려면 ~/.zshrc·~/.bashrc 의 다음 줄을 수동 삭제:"
echo "  export PATH=\"\$HOME/.harness/bin:\$PATH\""
