"""ctx budget — compose 의 cognition entries 별 토큰 추정 + 비율 표.

호출:
    python3 -m lib.ctx.budget [compose_path]

토큰 추정은 단순 char/4 (정확한 token 은 provider tokenizer 필요).
recent tool results / compressed history 는 세션 외부 호출이라 N/A.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from lib.compose import parse_compose
from lib.manifest import parse_manifest
from lib.resolver import IdConflict, IdNotFound, Resolver

CONTEXT_WINDOW = 200_000   # Claude 200K 기본 — provider 별 다름


def estimate_tokens(text: str) -> int:
    """char count / 4 단순 추정. 영한 mixed 평균."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def read_entry_body(manifest_path: Path) -> str:
    m = parse_manifest(manifest_path)
    entry_path = manifest_path.parent / m.entry
    if not entry_path.exists():
        return ""
    try:
        return entry_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def read_context_src(src_path: str, project_root: Path) -> str:
    if not src_path:
        return ""
    p = project_root / src_path
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def find_standard_root(harness_home: Path) -> Path:
    """install 된 ~/.harness/standard 우선, 없으면 dev repo fallback."""
    if (harness_home / "standard").exists():
        return harness_home / "standard"
    # dev fallback: <repo>/standard
    dev = Path(__file__).resolve().parent.parent.parent / "standard"
    if dev.exists():
        return dev
    raise FileNotFoundError(f"standard root 없음 — {harness_home}/standard 또는 dev fallback")


def main() -> int:
    ap = argparse.ArgumentParser(description="cognition entries 별 토큰 예산 + 비율 표")
    ap.add_argument("compose_path", nargs="?", default=None,
                    help="compose.yaml 경로 (기본: ./.harness/compose.yaml)")
    ap.add_argument("--window", type=int, default=CONTEXT_WINDOW,
                    help=f"context window 크기 (기본 {CONTEXT_WINDOW})")
    args = ap.parse_args()

    project_root = Path.cwd()
    compose_path = Path(args.compose_path) if args.compose_path else project_root / ".harness" / "compose.yaml"
    if not compose_path.exists():
        print(f"Error: compose.yaml 없음 ({compose_path}). harness init 부터.", file=sys.stderr)
        return 1

    harness_home = Path(os.environ.get("HARNESS_HOME", Path.home() / ".harness"))
    try:
        standard_root = find_standard_root(harness_home)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    know_how_root = project_root / ".harness" / "know-how"

    compose = parse_compose(compose_path)
    resolver = Resolver(standard_root=standard_root, know_how_root=know_how_root)

    cats = {
        "cognition.instructions": [],            # [(id, tokens)]
        "cognition.context.required": [],
        "cognition.context.triggered": [],
        "cognition.context.suggested": "lazy",
        "cognition.rules": [],
    }

    for entry in compose.entries:
        if entry.domain != "cognition":
            continue
        section = entry.section
        if section == "instructions":
            try:
                body = read_entry_body(resolver.resolve(entry.id))
            except (IdNotFound, IdConflict):
                body = ""
            cats["cognition.instructions"].append((entry.id, estimate_tokens(body)))
        elif section == "rules":
            try:
                body = read_entry_body(resolver.resolve(entry.id))
            except (IdNotFound, IdConflict):
                body = ""
            cats["cognition.rules"].append((entry.id, estimate_tokens(body)))
        elif section == "context.required":
            body = read_context_src(entry.extras.get("src_path", ""), project_root)
            cats["cognition.context.required"].append((entry.id, estimate_tokens(body)))
        elif section == "context.triggered":
            body = read_context_src(entry.extras.get("src_path", ""), project_root)
            cats["cognition.context.triggered"].append((entry.id, estimate_tokens(body)))

    # ─────────────── 출력 ───────────────
    window = args.window
    print()
    print("Context Budget")
    print("─" * 64)

    total = 0
    for name, items, note in [
        ("cognition.instructions", cats["cognition.instructions"], "← 본문 직접 (압축 X)"),
        ("cognition.context.required", cats["cognition.context.required"], ""),
        ("cognition.context.triggered", cats["cognition.context.triggered"], "← 매칭된 것만 합성"),
        ("cognition.context.suggested", cats["cognition.context.suggested"], ""),
        ("cognition.rules", cats["cognition.rules"], ""),
    ]:
        if isinstance(items, str):  # lazy marker
            print(f"[{name:<32}] ({items} — 합성 X)")
            continue
        if not items:
            print(f"[{name:<32}]     0 tokens   (비어있음)")
            continue
        subtotal = sum(t for _, t in items)
        total += subtotal
        pct = subtotal / window * 100
        bar = "▮" * max(1, int(pct / 2))   # 2% per bar
        note_str = f"   {note}" if note else ""
        print(f"[{name:<32}] {subtotal:>6,} tokens   [{bar} {pct:.1f}%]{note_str}")
        for eid, t in items:
            print(f"  {eid:<35}  {t:>6,}")

    print("─" * 64)
    print(f"[recent tool results]              (세션 외부 호출 — 측정 N/A)")
    print(f"[compressed history]               (세션 외부 호출 — 측정 N/A)")
    print("─" * 64)
    pct = total / window * 100
    print(f"prefix subtotal:               {total:>6,} / {window:>6,} tokens ({pct:.1f}%)")
    print()
    print("note:")
    print("  - 토큰 추정은 char/4 (간단). 정확한 count 는 provider tokenizer 필요.")
    print("  - recent tool results / compressed history 는 진행 중인 세션 안에서만 측정 가능.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
