"""harness validate CLI 엔트리 (v2).

compose.yaml v2 + manifest + roles.yaml 을 통합 검증.

옵션:
  --compose <path>     compose.yaml 위치 (기본: <cwd>/.harness/compose.yaml)
  --standard <path>    standard 루트 (기본: ~/.harness/standard)
  --know-how <path>    know-how 루트 (기본: <cwd>/.harness/know-how, 없으면 무시)

exit code:
  0  — valid
  1  — 검증 에러 (메시지 출력)
  2  — 파일 없음 등 사전 조건 실패
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lib.compose import ComposeError, parse_compose
from lib.resolver import Resolver, ResolverError
from lib.roles_registry import RolesRegistryError, load_roles
from lib.validator import validate_compose


def main() -> int:
    ap = argparse.ArgumentParser(
        description="compose.yaml v2 + manifests + roles.yaml 통합 검증",
    )
    ap.add_argument(
        "--compose",
        type=Path,
        default=Path(".harness/compose.yaml"),
        help="compose.yaml 경로",
    )
    ap.add_argument(
        "--standard",
        type=Path,
        default=Path.home() / ".harness" / "standard",
        help="standard 루트 경로",
    )
    ap.add_argument(
        "--know-how",
        type=Path,
        default=Path(".harness") / "know-how",
        help="know-how 루트 경로 (선택)",
    )
    args = ap.parse_args()

    # 1) compose 파싱
    try:
        compose = parse_compose(args.compose)
    except FileNotFoundError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    except ComposeError as e:
        print(f"✗ compose 파싱 실패 — {e}", file=sys.stderr)
        return 1

    # 2) resolver 인덱스 구축
    know_how_arg = args.know_how if args.know_how.exists() else None
    try:
        resolver = Resolver(args.standard, know_how_arg)
    except ResolverError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1

    # 3) roles 로드
    try:
        roles = load_roles(args.standard, know_how_arg)
    except FileNotFoundError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    except RolesRegistryError as e:
        print(f"✗ roles.yaml 형식 오류 — {e}", file=sys.stderr)
        return 1

    # 4) 통합 검증
    errors = validate_compose(compose, resolver, roles)

    if errors:
        print(f"✗ {len(errors)}개 검증 실패:")
        for err in errors:
            print(f"  - {err}")
        return 1

    # 5) 성공 — 요약 출력
    counts: dict[str, int] = {}
    for e in compose.entries:
        counts[e.domain] = counts.get(e.domain, 0) + 1
    by_domain = ", ".join(f"{d}: {n}" for d, n in sorted(counts.items()))
    print(
        f"✓ compose.yaml valid — {len(compose.entries)} entries "
        f"({by_domain or '비어있음'})"
    )
    if compose.policies:
        print(f"  policies: {sorted(compose.policies)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
