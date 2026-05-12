"""compose.yaml v1 → v2 변환기.

기존 v1 형식의 compose.yaml 을 v2 형식으로 변환.

핵심 결정 사항:
  - hook 의 (도메인, role) 매핑은 hardcode 하지 않고 standard_v2 의 manifest + roles.yaml 에서
    동적으로 계산. 새 role 추가 시 자동 반영.
  - path → id 변환은 basename 기반 자동 (사용자 후수정 권장).
  - hard_rules 는 일단 string 리스트 그대로 (rule artifact 화는 추후 단계).

사용 예:
    python -m lib.migrate_compose --input old.yaml --output new.yaml --standard standard_v2
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from lib.manifest import parse_manifest
from lib.resolver import Resolver
from lib.roles_registry import load_roles


# ───────────────────── 헬퍼 ─────────────────────


def _path_to_id(path: str) -> str:
    """경로 → id. basename 의 모든 특수문자를 _ 로 (확장자 포함).

    예:
      AGENTS.md            → agents_md
      README.md            → readme_md
      docs/api-spec.md     → api_spec_md
      docs/system-design.md → system_design_md

    standard_v2 의 manifest id 컨벤션(`agents_md` 등)과 일치하도록 확장자도 포함.
    """
    name = Path(path).name
    return name.lower().replace(".", "_").replace("-", "_").replace(" ", "_")


def _build_role_to_domain(standard_root: Path) -> dict[str, str]:
    """role 이름 → domain 역인덱스. roles.yaml 기반.

    예: {"prefix_injection": "cognition", "required_check": "guard", ...}
    """
    roles = load_roles(standard_root)
    out: dict[str, str] = {}
    for domain, role_set in roles.items():
        for r in role_set:
            out[r] = domain
    return out


def _build_hook_routing(
    standard_root: Path,
    role_to_domain: dict[str, str],
) -> dict[str, list[tuple[str, str]]]:
    """hook id → [(domain, role), ...] 매핑.

    standard_v2/hooks/<id>/manifest.yaml 의 roles 를 roles.yaml 의 도메인 enum 으로 분류.
    """
    hooks_dir = standard_root / "hooks"
    out: dict[str, list[tuple[str, str]]] = {}
    if not hooks_dir.exists():
        return out
    for entry in sorted(hooks_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        manifest_path = entry / "manifest.yaml"
        if not manifest_path.exists():
            continue
        try:
            m = parse_manifest(manifest_path)
        except Exception:
            continue
        pairs: list[tuple[str, str]] = []
        for role in m.roles:
            domain = role_to_domain.get(role)
            if domain is not None:
                pairs.append((domain, role))
        if pairs:
            out[m.id] = pairs
    return out


# ───────────────────── 변환 본체 ─────────────────────


def convert(
    v1: dict,
    hook_routing: dict[str, list[tuple[str, str]]],
    know_how_root: Optional[Path] = None,
    known_ids: Optional[set[str]] = None,
) -> dict:
    """v1 dict → v2 dict.

    Args:
        hook_routing: _build_hook_routing 의 결과
        know_how_root: 사용자 path/rule artifact 를 자동 생성할 know-how 디렉토리. None 이면 emit 안 함.
        known_ids: 이미 standard 에 존재하는 id 집합. 중복 emit 방지.

    artifact 자동 생성 (know_how_root 주어진 경우):
        - 사용자 path → know-how/instructions/<id>/manifest.yaml (entry 는 원본 path 가리킴)
        - hard_rules 의 각 string → know-how/instructions/rules/<rule_id>/manifest.yaml + .md
        - 이미 standard 에 있는 id (예: agents_md) 는 skip
    """
    v2: dict[str, Any] = {"version": 2}
    emitted: list[Path] = []
    known = known_ids or set()

    _convert_cognition(v1, v2, know_how_root, emitted, known)
    _convert_hooks(v1, v2, hook_routing)
    _convert_guard_policies(v1, v2)
    _convert_state_workflows(v1, v2)
    _convert_observe_evals(v1, v2)

    if know_how_root is not None and emitted:
        v2["_meta"] = {"emitted_artifacts": [str(p) for p in emitted]}

    return v2


def _convert_cognition(
    v1: dict,
    v2: dict,
    know_how_root: Optional[Path],
    emitted: list[Path],
    known: set[str],
) -> None:
    cog: dict[str, Any] = {}

    # prefix → instructions
    prefix = v1.get("prefix") or []
    if prefix:
        ids = []
        for p in prefix:
            pid = _path_to_id(p)
            ids.append(pid)
            _maybe_emit_path_artifact(know_how_root, pid, p, "prefix_injection", emitted, known)
        cog["instructions"] = ids

    # context: required / suggested / triggered
    ctx: dict[str, Any] = {}

    rc = v1.get("required_context") or {}
    rc_paths = rc.get("paths") or []
    if rc_paths:
        ctx["required"] = [
            _convert_path_item(p, default_on_deny=rc.get("default_on_deny"),
                                know_how_root=know_how_root, role="prefix_injection",
                                emitted=emitted, known=known)
            for p in rc_paths
        ]

    od = v1.get("on_demand_context") or {}
    od_paths = od.get("paths") or []
    if od_paths:
        ctx["suggested"] = [
            _convert_path_item(p, know_how_root=know_how_root, role="on_demand_hint",
                                emitted=emitted, known=known)
            for p in od_paths
        ]

    tr = v1.get("trigger_read") or []
    if tr:
        ctx["triggered"] = [
            _convert_trigger_item(t, know_how_root=know_how_root, emitted=emitted, known=known)
            for t in tr
        ]

    if ctx:
        cog["context"] = ctx

    # hard_rules → rules (각 rule 을 instructions artifact 화)
    rules = v1.get("hard_rules") or []
    if rules:
        rule_ids = []
        for idx, rule_text in enumerate(rules, start=1):
            rid = f"rule_{idx:02d}"
            rule_ids.append(rid)
            _maybe_emit_rule_artifact(know_how_root, rid, rule_text, emitted, known)
        cog["rules"] = rule_ids

    if cog:
        v2["cognition"] = cog


def _convert_path_item(
    item: Any,
    default_on_deny: Optional[str] = None,
    know_how_root: Optional[Path] = None,
    role: str = "prefix_injection",
    emitted: Optional[list[Path]] = None,
    known: Optional[set[str]] = None,
) -> dict:
    """{path, label, on_deny?} → {id, label?, on_deny?, src_path}."""
    if not isinstance(item, dict):
        path = str(item)
        pid = _path_to_id(path)
        _maybe_emit_path_artifact(know_how_root, pid, path, role, emitted, known)
        return {"id": pid, "src_path": path}
    path = item.get("path", "")
    pid = _path_to_id(path)
    _maybe_emit_path_artifact(know_how_root, pid, path, role, emitted, known)
    out = {"id": pid, "src_path": path}
    if "label" in item:
        out["label"] = item["label"]
    on_deny = item.get("on_deny") or default_on_deny
    if on_deny:
        out["on_deny"] = on_deny
    return out


def _convert_trigger_item(
    item: Any,
    know_how_root: Optional[Path] = None,
    emitted: Optional[list[Path]] = None,
    known: Optional[set[str]] = None,
) -> dict:
    """{match_path, require, on_deny?} → {id, when, src_path, on_deny?}."""
    if not isinstance(item, dict):
        return {}
    path = item.get("require", "")
    pid = _path_to_id(path)
    _maybe_emit_path_artifact(know_how_root, pid, path, "trigger_match", emitted, known)
    out = {
        "id": pid,
        "when": item.get("match_path"),
        "src_path": path,
    }
    if "on_deny" in item:
        out["on_deny"] = item["on_deny"]
    return out


# ───────────────────── know-how artifact 자동 생성 ─────────────────────


def _maybe_emit_path_artifact(
    know_how_root: Optional[Path],
    artifact_id: str,
    src_path: str,
    role: str,
    emitted: Optional[list[Path]],
    known: Optional[set[str]] = None,
) -> None:
    """사용자 path 를 know-how/instructions/<id>/manifest.yaml 로 자동 등록.

    know_how_root 가 None 이거나 src_path 가 빈 문자열이면 emit 안 함.
    known (이미 standard 에 있는 id 집합) 에 있으면 skip.
    """
    if know_how_root is None or not src_path:
        return
    if known and artifact_id in known:
        return  # 이미 standard 에 존재 — 중복 emit 방지
    target_dir = know_how_root / "instructions" / artifact_id
    manifest_path = target_dir / "manifest.yaml"
    if manifest_path.exists():
        # 이미 있으면 덮어쓰지 않음 (사용자 수정 보존)
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": artifact_id,
        "domain": "cognition",
        "mechanism": "instructions",
        "purpose": f"v1 path '{src_path}' 자동 변환 — 사용자 자산",
        "roles": [role],
        "entry": src_path,   # 원본 path (project-relative). 자산은 그 자리에 그대로.
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    if emitted is not None:
        emitted.append(manifest_path)


def _maybe_emit_rule_artifact(
    know_how_root: Optional[Path],
    rule_id: str,
    rule_text: str,
    emitted: Optional[list[Path]],
    known: Optional[set[str]] = None,
) -> None:
    """hard_rule text 를 know-how/instructions/rules/<id>/ artifact 로 등록.

    manifest.yaml + rule.md (본문) 두 파일 생성.
    """
    if know_how_root is None:
        return
    if known and rule_id in known:
        return
    target_dir = know_how_root / "instructions" / "rules" / rule_id
    manifest_path = target_dir / "manifest.yaml"
    rule_path = target_dir / "rule.md"
    if manifest_path.exists():
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": rule_id,
        "domain": "cognition",
        "mechanism": "instructions",
        "purpose": rule_text[:80],
        "roles": ["rule_reminder"],
        "entry": "./rule.md",
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    rule_path.write_text(f"# {rule_id}\n\n{rule_text}\n", encoding="utf-8")
    if emitted is not None:
        emitted.append(manifest_path)
        emitted.append(rule_path)


def _convert_hooks(
    v1: dict,
    v2: dict,
    hook_routing: dict[str, list[tuple[str, str]]],
) -> None:
    """v1 hooks.<name>.enabled 를 도메인별 hooks entries 로 분산."""
    hooks = v1.get("hooks") or {}
    for hook_name, status in hooks.items():
        if status != "enabled":
            continue
        routing = hook_routing.get(hook_name)
        if not routing:
            # standard_v2 에 해당 hook manifest 없음 → 주석 형태로 메모만
            continue
        for domain, role in routing:
            domain_block = v2.setdefault(domain, {})
            hook_list = domain_block.setdefault("hooks", [])
            hook_list.append({"id": hook_name, "role": role})


def _convert_guard_policies(v1: dict, v2: dict) -> None:
    """cognitive_guard / loop_detection / stop_validation → guard.policies."""
    policies: dict[str, Any] = {}
    for key in ("cognitive_guard", "loop_detection", "stop_validation"):
        val = v1.get(key)
        if val:
            policies[key] = val
    if policies:
        guard = v2.setdefault("guard", {})
        guard["policies"] = policies


def _convert_state_workflows(v1: dict, v2: dict) -> None:
    """ralph 가 v1 에 있으면 state.workflows 에 등록 + state.policies.ralph."""
    ralph = v1.get("ralph")
    if ralph:
        state = v2.setdefault("state", {})
        state["workflows"] = ["ralph"]
        state.setdefault("policies", {})["ralph"] = ralph


def _convert_observe_evals(v1: dict, v2: dict) -> None:
    """llm_judge → observe.policies.llm_judge (eval artifact 자체는 미생성 — 추후 단계)."""
    judge = v1.get("llm_judge")
    if judge:
        observe = v2.setdefault("observe", {})
        observe.setdefault("policies", {})["llm_judge"] = judge


# ───────────────────── CLI ─────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description="compose.yaml v1 → v2 변환")
    ap.add_argument("--input", type=Path, default=Path(".harness/compose.yaml"))
    ap.add_argument("--output", type=Path, default=None,
                    help="기본: input 파일명 + .v2.yaml")
    ap.add_argument("--standard", type=Path, default=Path("standard_v2"),
                    help="hook routing 추출 기준 standard 루트")
    ap.add_argument("--know-how", type=Path, default=None,
                    help="사용자 path/rule artifact 자동 생성할 know-how 루트. "
                         "지정하면 새 manifest 들이 그 안에 생성됨.")
    ap.add_argument("--dry-run", action="store_true",
                    help="실제 파일 생성 없이 변환 결과만 출력")
    args = ap.parse_args()

    if not args.input.exists():
        print(f"✗ input 없음: {args.input}", file=sys.stderr)
        return 2

    with open(args.input, encoding="utf-8") as f:
        v1 = yaml.safe_load(f) or {}

    if v1.get("version") == 2:
        print(f"⚠ 이미 v2 형식: {args.input}", file=sys.stderr)
        return 1

    # hook routing + known ids (standard 에 이미 있는 id 집합)
    try:
        role_to_domain = _build_role_to_domain(args.standard)
        hook_routing = _build_hook_routing(args.standard, role_to_domain)
        resolver = Resolver(args.standard, None)
        known_ids = set(resolver.all_ids())
    except FileNotFoundError as e:
        print(f"✗ standard 정보 누락 — {e}", file=sys.stderr)
        return 2

    # dry-run 일 때는 know-how 에 파일 안 만들도록 None 전달
    know_how_arg = None if args.dry_run else args.know_how

    v2 = convert(
        v1,
        hook_routing,
        know_how_root=know_how_arg,
        known_ids=known_ids,
    )
    out_text = yaml.safe_dump(v2, allow_unicode=True, sort_keys=False, default_flow_style=False)

    if args.dry_run:
        print(out_text)
        return 0

    output = args.output or args.input.with_name(args.input.stem + ".v2.yaml")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(out_text, encoding="utf-8")
    print(f"✓ {output} 생성")
    if args.know_how and v2.get("_meta", {}).get("emitted_artifacts"):
        print(f"  + know-how artifact {len(v2['_meta']['emitted_artifacts'])}개 생성: {args.know_how}")
    print(f"  검증: harness validate --compose {output} --standard {args.standard} --know-how {args.know_how or '<none>'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
