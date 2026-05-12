"""harness upgrade — v1 → v2 통합 마이그레이션 orchestrator.

두 가지 마이그레이션을 한 번에 실행:
  1. standard/ → standard_v2/ (lib.migrate_v2)
  2. .harness/compose.yaml → .harness/compose.v2.yaml + know-how artifact (lib.migrate_compose)

각 단계는 idempotent — 이미 v2 면 skip. side-by-side 안전 (v1 안 건드림).

사용 예:
    harness upgrade --dry-run     # 미리보기
    harness upgrade               # 실 실행
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Optional

import yaml

from lib.compose import parse_compose
from lib.migrate_compose import (
    _build_hook_routing,
    _build_role_to_domain,
    convert as convert_compose,
)
from lib.migrate_v2 import Migration as V2StandardMigration
from lib.resolver import Resolver
from lib.roles_registry import load_roles
from lib.validator import validate_compose


def main() -> int:
    ap = argparse.ArgumentParser(
        description="v1 → v2 통합 마이그레이션 (standard + compose)",
    )
    ap.add_argument("--project", type=Path, default=Path("."),
                    help="대상 프로젝트 루트 (기본: 현재 디렉토리)")
    ap.add_argument("--standard-src", type=Path, default=None,
                    help="v1 standard 경로 (기본: <project>/standard 또는 ~/.harness/standard)")
    ap.add_argument("--standard-dst", type=Path, default=None,
                    help="v2 standard 출력 경로 (기본: <standard-src>_v2)")
    ap.add_argument("--dry-run", action="store_true",
                    help="실제 변경 없이 plan 만 출력")
    ap.add_argument("--force", action="store_true",
                    help="기존 v2 출력 덮어쓰기")
    args = ap.parse_args()

    project = args.project.resolve()
    print(f"📦 project: {project}")

    # ─────────── Step 1: standard 마이그레이션 ───────────
    print("\n── Step 1: standard/ → standard_v2/ ──")
    src = args.standard_src or _infer_standard_src(project)
    if src is None:
        print("⊙ standard/ 못 찾음 — skip")
    else:
        dst = args.standard_dst or src.with_name(src.name + "_v2")
        if dst.exists() and not args.force:
            print(f"⊙ {dst} 이미 존재 — skip (--force 로 덮어쓰기)")
        else:
            if args.force and dst.exists() and not args.dry_run:
                shutil.rmtree(dst)
            print(f"   src: {src}")
            print(f"   dst: {dst}")
            m = V2StandardMigration(src, dst, dry_run=args.dry_run)
            m.run()
            mode = "(dry-run) " if args.dry_run else ""
            print(f"   ✓ {mode}{len(m.actions)} actions")

    # ─────────── Step 2: compose 마이그레이션 ───────────
    print("\n── Step 2: compose.yaml v1 → v2 ──")
    compose_v1 = project / ".harness" / "compose.yaml"
    if not compose_v1.exists():
        print(f"⊙ {compose_v1} 없음 — skip")
        return _summary(args.dry_run)

    with open(compose_v1, encoding="utf-8") as f:
        v1_dict = yaml.safe_load(f) or {}

    if v1_dict.get("version") == 2:
        print("⊙ 이미 v2 — skip")
        return _summary(args.dry_run)

    # standard_v2 의 hook routing + known ids
    standard_dst = args.standard_dst or _infer_standard_v2(project)
    if standard_dst is None or not standard_dst.exists():
        if args.dry_run:
            print("⊙ standard_v2 가 아직 없음 — 실 실행 후 compose 변환 가능 (dry-run skip)")
            return _summary(args.dry_run)
        print(f"✗ standard_v2 못 찾음 — compose 변환 불가", file=sys.stderr)
        return 2

    role_to_domain = _build_role_to_domain(standard_dst)
    hook_routing = _build_hook_routing(standard_dst, role_to_domain)
    resolver = Resolver(standard_dst, None)
    known_ids = set(resolver.all_ids())

    know_how_dst = project / ".harness" / "know-how"
    compose_v2_path = project / ".harness" / "compose.v2.yaml"

    print(f"   compose v1: {compose_v1}")
    print(f"   compose v2: {compose_v2_path}")
    print(f"   know-how:   {know_how_dst}")

    # dry-run 일 때는 know_how 안 만지도록
    know_how_arg = None if args.dry_run else know_how_dst

    v2_dict = convert_compose(
        v1_dict,
        hook_routing,
        know_how_root=know_how_arg,
        known_ids=known_ids,
    )

    if args.dry_run:
        print(f"   ✓ (dry-run) compose v2 변환 plan 완성 — entries 추정 {_count_entries(v2_dict)}")
    else:
        compose_v2_path.parent.mkdir(parents=True, exist_ok=True)
        with open(compose_v2_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(v2_dict, f, allow_unicode=True, sort_keys=False)
        emitted = v2_dict.get("_meta", {}).get("emitted_artifacts", [])
        print(f"   ✓ compose v2 생성, know-how artifact {len(emitted)}개 emit")

    # ─────────── Step 3: validate ───────────
    if not args.dry_run:
        print("\n── Step 3: 검증 (harness validate) ──")
        compose_obj = parse_compose(compose_v2_path)
        kh = know_how_dst if know_how_dst.exists() else None
        roles = load_roles(standard_dst, kh)
        resolver2 = Resolver(standard_dst, kh)
        errors = validate_compose(compose_obj, resolver2, roles)
        if errors:
            print(f"   ✗ {len(errors)}개 검증 실패:")
            for e in errors[:10]:
                print(f"      - {e}")
            if len(errors) > 10:
                print(f"      ... +{len(errors) - 10}개")
            return 1
        print(f"   ✓ valid — {len(compose_obj.entries)} entries")

    return _summary(args.dry_run)


def _summary(dry_run: bool) -> int:
    print()
    if dry_run:
        print("(dry-run — 실제 변경 없음)")
    else:
        print("✓ upgrade 완료")
    return 0


def _infer_standard_src(project: Path) -> Optional[Path]:
    """v1 standard 위치 추정."""
    candidates = [
        project / "standard",
        Path.home() / ".harness" / "standard",
    ]
    for c in candidates:
        if c.exists() and (c / "AGENTS.md").exists():
            return c
    return None


def _infer_standard_v2(project: Path) -> Optional[Path]:
    candidates = [
        project / "standard_v2",
        Path.home() / ".harness" / "standard_v2",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _count_entries(v2: dict) -> int:
    """v2 dict 에서 entry 들 대략 카운트 (dry-run 보고용)."""
    count = 0
    for domain in ("cognition", "state", "action", "guard", "observe"):
        block = v2.get(domain) or {}
        for key, val in block.items():
            if isinstance(val, list):
                count += len(val)
            elif isinstance(val, dict) and key == "context":
                for sub in val.values():
                    if isinstance(sub, list):
                        count += len(sub)
    return count


if __name__ == "__main__":
    sys.exit(main())
