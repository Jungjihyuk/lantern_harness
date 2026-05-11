"""disable / enable 공통 CLI 로직.

각 엔트리(disable.py, enable.py) 는 본 모듈의 run() 을 호출하면서
'disable' 또는 'enable' verb 만 다르게 넘긴다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

# adapters/ 를 sys.path 에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent))
from base import KINDS, ItemNotFound  # noqa: E402
from registry import discover_drivers, get_driver, list_all  # noqa: E402


def _available_providers() -> list[str]:
    try:
        return sorted(d.id for d in discover_drivers())
    except Exception:
        return []


def run(verb: str) -> int:
    """verb = 'disable' 또는 'enable'."""
    assert verb in ("disable", "enable")

    ap = argparse.ArgumentParser(
        description=f"아티팩트를 {verb} 상태로 전환",
    )
    ap.add_argument("name", help="대상 아티팩트 이름")
    providers = _available_providers()
    if providers:
        ap.add_argument(
            "--provider",
            default=None,
            choices=providers,
            help="특정 provider 만 필터",
        )
    else:
        ap.add_argument("--provider", default=None, help="특정 provider 만 필터")
    ap.add_argument("--kind", default=None, choices=KINDS, help="특정 종류 만 필터")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 파일 변경 없이 무엇이 바뀔지만 출력",
    )
    args = ap.parse_args()

    # 1) name 으로 후보 좁히기 (provider/kind 필터 적용)
    candidates = list_all(kind=args.kind, provider=args.provider)
    matches = [it for it in candidates if it.name == args.name]

    if not matches:
        msg = f"'{args.name}' 일치 항목 없음"
        if args.provider or args.kind:
            extras = []
            if args.provider:
                extras.append(f"--provider {args.provider}")
            if args.kind:
                extras.append(f"--kind {args.kind}")
            msg += f" (필터: {' '.join(extras)})"
        print(msg, file=sys.stderr)
        return 1

    if len(matches) > 1:
        print(
            f"'{args.name}' 매치 {len(matches)}개 — --provider / --kind 로 좁히세요:",
            file=sys.stderr,
        )
        for it in matches:
            print(
                f"  --provider {it.provider} --kind {it.kind}",
                file=sys.stderr,
            )
        return 2

    item = matches[0]

    # 2) 이미 목표 상태면 안내만 (idempotent)
    already = (verb == "disable" and not item.enabled) or (
        verb == "enable" and item.enabled
    )
    if already:
        state = "disabled" if verb == "disable" else "enabled"
        print(f"⊙ '{item.name}' ({item.kind}) — 이미 {state}")
        return 0

    # 3) dry-run
    if args.dry_run:
        print(
            f"[dry-run] '{item.name}' ({item.provider}/{item.kind}) "
            f"→ {verb} 예정"
        )
        return 0

    # 4) driver 의 disable/enable 호출
    driver = get_driver(item.provider)
    if driver is None:
        print(f"Error: provider '{item.provider}' driver 를 찾을 수 없음", file=sys.stderr)
        return 3

    action: Callable[[str, str], bool] = getattr(driver, verb)
    try:
        changed = action(item.kind, item.name)
    except ItemNotFound as e:
        print(f"Error: {e}", file=sys.stderr)
        return 4
    except Exception as e:  # pragma: no cover — 안전망
        print(f"Error: {verb} 실패 — {e}", file=sys.stderr)
        return 5

    if changed:
        state = "disabled" if verb == "disable" else "enabled"
        print(f"✓ '{item.name}' ({item.kind}) → {state}")
    else:
        # 이론상 위 already 검사로 걸렸어야 하지만 race 등 대비
        state = "disabled" if verb == "disable" else "enabled"
        print(f"⊙ '{item.name}' ({item.kind}) — 이미 {state}")
    return 0
