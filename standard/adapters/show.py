"""harness show <name> 엔트리포인트.

특정 아티팩트 한 건의 상세 정보를 출력한다. list 의 짝.

기본 매칭 규칙:
  - <name> 만 주면 provider/kind 무관하게 name이 일치하는 항목 검색
  - 매치가 정확히 1개면 상세 출력
  - 0개면 not found 에러
  - 2개 이상이면 매치 목록을 보여주고 --provider / --kind 로 좁히도록 안내

옵션:
  --provider <id>            특정 provider 만 필터
  --kind <mcp|skill|plugin>  특정 종류 만 필터
  --json                     JSON 출력
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# adapters/ 를 sys.path 에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent))
from base import KINDS, Item  # noqa: E402
from registry import discover_drivers, list_all  # noqa: E402


# skill body 미리보기 기본 라인 수 (--full / --lines 로 override 가능)
DEFAULT_PREVIEW_LINES = 20


def _read_skill_body(source: str, max_lines: int | None) -> str:
    """SKILL.md 의 frontmatter 이후 본문을 반환.

    max_lines:
      - None  → 전체 본문 (truncation 없음)
      - 정수  → 해당 라인 수까지만, 잘리면 안내 메시지 추가
    """
    try:
        text = Path(source).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end >= 0:
            text = text[end + 4 :].lstrip("\n")
    lines = text.splitlines()
    total = len(lines)
    if max_lines is None or total <= max_lines:
        return "\n".join(lines)
    preview = "\n".join(lines[:max_lines])
    preview += f"\n... ({total - max_lines}줄 더)"
    return preview


def _available_providers() -> list[str]:
    """registry 가 발견한 driver id 목록 — argparse choices 용."""
    try:
        return sorted(d.id for d in discover_drivers())
    except Exception:
        return []


def _show_mcp(item: Item) -> None:
    print(f"\n[ MCP: {item.name} ]")
    print(f"Provider:   {item.provider}")
    print(f"Status:     {'enabled' if item.enabled else 'disabled'}")
    print(f"Source:     {item.source}")
    print(f"Command:    {item.meta.get('command', '')}")
    args = item.meta.get("args", [])
    if args:
        print(f"Args:       {' '.join(args)}")


def _show_skill(item: Item, body_lines: int | None) -> None:
    print(f"\n[ Skill: {item.name} ]")
    print(f"Provider:    {item.provider}")
    print(f"Trigger:     {item.meta.get('trigger') or '(auto)'}")
    print(f"Source:      {item.source}")
    desc = item.meta.get("description", "")
    if desc:
        print("Description:")
        for line in desc.splitlines() or [desc]:
            print(f"  {line}")
    body = _read_skill_body(item.source, body_lines)
    if body.strip():
        if body_lines is None:
            print("\nBody (full):")
        else:
            print(f"\nBody preview (first {body_lines} lines):")
        for line in body.splitlines():
            print(f"  {line}")


def _show_plugin(item: Item) -> None:
    print(f"\n[ Plugin: {item.name} ]")
    print(f"Provider:      {item.provider}")
    print(f"Version:       {item.meta.get('version', '')}")
    print(f"Scope:         {item.meta.get('scope', '')}")
    print(f"Source:        {item.source}")
    ip = item.meta.get("install_path", "")
    if ip:
        print(f"Install path:  {ip}")
    pp = item.meta.get("project_path", "")
    if pp:
        print(f"Project path:  {pp}")
    sha = item.meta.get("git_commit_sha", "")
    if sha:
        print(f"Git SHA:       {sha}")
    inst = item.meta.get("installed_at", "")
    if inst:
        print(f"Installed at:  {inst}")
    upd = item.meta.get("last_updated", "")
    if upd:
        print(f"Last updated:  {upd}")


def _show(item: Item, body_lines: int | None) -> None:
    if item.kind == "mcp":
        _show_mcp(item)
    elif item.kind == "skill":
        _show_skill(item, body_lines)
    elif item.kind == "plugin":
        _show_plugin(item)
    else:
        # fallback — 알 수 없는 kind
        print(f"\n[ {item.kind}: {item.name} ]")
        print(f"Provider:  {item.provider}")
        print(f"Source:    {item.source}")
        for k, v in item.meta.items():
            print(f"{k}: {v}")


def _item_to_dict(item: Item) -> dict:
    return {
        "name": item.name,
        "provider": item.provider,
        "kind": item.kind,
        "enabled": item.enabled,
        "source": item.source,
        "meta": item.meta,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="아티팩트 한 건의 상세 정보 출력",
    )
    ap.add_argument("name", help="조회할 아티팩트 이름")
    providers = _available_providers()
    if providers:
        ap.add_argument(
            "--provider",
            default=None,
            choices=providers,
            help="특정 provider 만 필터",
        )
    else:
        # driver 가 하나도 없으면 choices 생략 (argparse가 empty list 거부)
        ap.add_argument("--provider", default=None, help="특정 provider 만 필터")
    ap.add_argument("--kind", default=None, choices=KINDS, help="특정 종류 만 필터")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    # skill 본문 출력 분량 제어 — 둘 다 안 주면 기본 20줄
    body_group = ap.add_mutually_exclusive_group()
    body_group.add_argument(
        "--full",
        action="store_true",
        help="skill 본문 전체 출력 (기본: 앞 20줄)",
    )
    body_group.add_argument(
        "--lines",
        type=int,
        default=None,
        metavar="N",
        help="skill 본문 N줄까지 출력",
    )
    args = ap.parse_args()

    # body 라인 수 결정: --full > --lines > 기본값
    if args.full:
        body_lines = None
    elif args.lines is not None:
        body_lines = max(0, args.lines)
    else:
        body_lines = DEFAULT_PREVIEW_LINES

    # 1단계: provider/kind 필터로 후보 좁히기
    candidates = list_all(kind=args.kind, provider=args.provider)
    matches = [it for it in candidates if it.name == args.name]

    # 매치 0개
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
        # 유사 후보 힌트 — 같은 이름 일부 매치
        all_items = list_all()
        similar = [it for it in all_items if args.name.lower() in it.name.lower()]
        if similar:
            print("\n유사 후보:", file=sys.stderr)
            for it in similar[:10]:
                print(
                    f"  {it.name}  (provider={it.provider}, kind={it.kind})",
                    file=sys.stderr,
                )
        return 1

    # 매치 2개 이상 — disambiguation 안내
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

    # 정확히 1개
    item = matches[0]
    if args.json:
        print(json.dumps(_item_to_dict(item), indent=2, ensure_ascii=False))
    else:
        _show(item, body_lines)
    return 0


if __name__ == "__main__":
    sys.exit(main())
