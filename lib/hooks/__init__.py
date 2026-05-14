"""Hook handler 구현 — provider event 시점에 호출되는 logic.

각 hook 은 같은 패턴:
  - stdin: 표준 envelope JSON (provider adapter 가 translate 후 전달)
  - stdout: decision JSON ({decision: allow|self_correct|hard_stop|block, ...})

handler.sh 는 bash entry, 실 logic 은 lib.hooks.<id>.main().
"""
