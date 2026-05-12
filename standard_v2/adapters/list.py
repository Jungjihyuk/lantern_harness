"""harness list (provider 섹션) 엔트리포인트.

bin/cmd/list.sh 에서 호출되어 provider별 설치 아티팩트를 표 형식으로 출력한다.

옵션:
  --provider <id>            특정 provider만 (예: claude)
  --kind <mcp|skill|plugin>  특정 종류만
  --json                     JSON 출력
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# adapters/ 를 sys.path 에 추가해 base/registry 임포트
sys.path.insert(0, str(Path(__file__).resolve().parent))
from base import KINDS, Item  # noqa: E402
from registry import discover_drivers, list_all  # noqa: E402


def _available_providers() -> list[str]:
    """registry 가 발견한 driver id 목록 — argparse choices 용."""
    try:
        return sorted(d.id for d in discover_drivers())
    except Exception:
        return []


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: max(1, n - 1)] + "…"


def _print_table(rows: list[dict], headers: list[tuple[str, int]]) -> None:
    """간단 고정폭 표 출력. headers = [(컬럼명, 너비), ...]"""
    header_line = "  ".join(name.ljust(w) for name, w in headers)
    print(header_line)
    print("  ".join("-" * w for _, w in headers))
    for row in rows:
        cells = [
            _truncate(str(row.get(name, "")), w).ljust(w)
            for name, w in headers
        ]
        print("  ".join(cells))


# 세 kind 모두 동일한 컬럼 셋 사용 — list는 스캐닝 용도, 상세는 show 가 담당
_LIST_COLUMNS = [
    ("Name", 42),
    ("Provider", 10),
    ("Status", 10),
    ("Scope", 10),
    ("Version", 14),
]


def _row_for(it: Item) -> dict:
    return {
        "Name": it.name,
        "Provider": it.provider,
        "Status": "enabled" if it.enabled else "disabled",
        "Scope": it.meta.get("scope", ""),
        "Version": it.meta.get("version", ""),
    }


def _section(title: str, items: list[Item]) -> None:
    print(f"\n[ {title} ]  ({len(items)})")
    if not items:
        print("  (없음)")
        return
    _print_table([_row_for(it) for it in items], _LIST_COLUMNS)


def _section_mcps(items: list[Item]) -> None:
    _section("MCP", items)


def _section_skills(items: list[Item]) -> None:
    _section("Skill", items)


def _section_plugins(items: list[Item]) -> None:
    _section("Plugin", items)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="provider별 설치 아티팩트 통합 리스트",
    )
    providers = _available_providers()
    if providers:
        ap.add_argument(
            "--provider",
            default=None,
            choices=providers,
            help="특정 provider만",
        )
    else:
        ap.add_argument("--provider", default=None, help="특정 provider만")
    ap.add_argument("--kind", default=None, choices=KINDS, help="특정 종류만")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    args = ap.parse_args()

    items = list_all(kind=args.kind, provider=args.provider)

    if args.json:
        payload = [
            {
                "name": it.name,
                "provider": it.provider,
                "kind": it.kind,
                "enabled": it.enabled,
                "source": it.source,
                "meta": it.meta,
            }
            for it in items
        ]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    by_kind = {k: [it for it in items if it.kind == k] for k in KINDS}
    if args.kind in (None, "mcp"):
        _section_mcps(by_kind["mcp"])
    if args.kind in (None, "skill"):
        _section_skills(by_kind["skill"])
    if args.kind in (None, "plugin"):
        _section_plugins(by_kind["plugin"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
