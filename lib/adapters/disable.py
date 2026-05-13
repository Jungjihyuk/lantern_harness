"""harness disable <name> 엔트리포인트.

기본 매칭 규칙은 show 와 동일:
  - <name> 만 주면 provider/kind 무관하게 정확 일치 검색
  - 0개 → not found
  - 2개 이상 → --provider / --kind 로 좁히도록 안내
  - 1개 → 해당 driver 의 disable() 호출

옵션:
  --provider <id>            특정 provider 만 필터
  --kind <mcp|skill|plugin>  특정 종류 만 필터
  --dry-run                  실제 변경 없이 예정만 출력
"""
import sys

from lib.adapters._mutation import run


if __name__ == "__main__":
    sys.exit(run("disable"))
