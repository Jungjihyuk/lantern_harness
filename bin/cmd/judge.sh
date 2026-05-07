#!/bin/bash
# harness judge — LLM-as-judge 정성 평가.

set -euo pipefail

if [[ $# -eq 0 ]]; then
  cat <<USAGE
harness judge — LLM-as-judge 정성 평가

  harness judge run [<session-id>] [-y] [--all]
                                새 prompt 평가. -y면 비용 confirmation 건너뜀.
                                --all이면 이미 평가된 것도 재평가.
  harness judge status [<session-id>]
                                평가 진척 표시 (prompt 수 / 평가된 수 / 평균 점수)

활성화: compose.yaml 의 llm_judge.enabled: true
필수: API key를 환경변수에 (default: ANTHROPIC_API_KEY)
USAGE
  exit 0
fi

exec python3 "$HOME/.harness/lib/judge/main.py" "$@"
