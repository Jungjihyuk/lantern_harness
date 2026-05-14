"""Compose + Resolver → Node / Edge / Cluster DTO 변환.

노드 = compose entry 1 개 (artifact 아님). 같은 hook 이 여러 role 로 등장하면
별개 노드. 엣지는 3 종류 — 시간 순서 / artifact 공유 / context 의존.
"""
from __future__ import annotations

from typing import Optional

from lib.compose import Compose, ComposeEntry
from lib.manifest import Manifest, parse_manifest
from lib.resolver import IdNotFound, Resolver

from lib.dashboard.schema import ClusterDTO, EdgeDTO, GraphDTO, NodeDTO


DOMAIN_COLORS = {
    "cognition": "#3b82f6",   # 파랑
    "state":     "#10b981",   # 초록
    "action":    "#f59e0b",   # 주황
    "guard":     "#ef4444",   # 빨강
    "observe":   "#8b5cf6",   # 보라
}

# 시간 순서 엣지: hook event 순. compose 의 cognition/state/action/guard/observe
# 도메인을 가로지르더라도 같은 hook event 끼리는 묶고, event 끼리는 chronological.
HOOK_EVENT_ORDER = [
    "session_start",
    "pre_tool_use",
    "post_tool_use",
    "post_tool_use_failure",
    "post_tool_batch",
    "permission_request",
    "stop",
]


def _node_id(entry: ComposeEntry, index: int) -> str:
    role = entry.role or "_"
    return f"{entry.domain}.{entry.section}.{entry.id}.{role}.{index}"


def build_graph(compose: Compose, resolver: Resolver) -> GraphDTO:
    """Compose → GraphDTO. 엣지 = hook 실행 시간 순서 (time_order) 만."""
    nodes: list[NodeDTO] = []
    by_domain: dict[str, list[str]] = {d: [] for d in DOMAIN_COLORS}
    # entry.id (hook event) → compose 등장 순으로 [node_id ...]
    hook_event_nodes: dict[str, list[str]] = {}

    for idx, entry in enumerate(compose.entries):
        nid = _node_id(entry, idx)
        manifest, _err = _try_resolve(resolver, entry.id)
        badges = _build_badges(entry, manifest)

        nodes.append(NodeDTO(
            id=nid,
            entry_index=idx,
            artifact_id=entry.id,
            role=entry.role,
            domain=entry.domain,
            section=entry.section,
            extras=entry.extras,
            manifest_found=(manifest is not None),
            manifest_purpose=(manifest.purpose if manifest else None),
            badges=badges,
        ))
        by_domain.setdefault(entry.domain, []).append(nid)

        if entry.section == "hooks" and entry.id in HOOK_EVENT_ORDER:
            hook_event_nodes.setdefault(entry.id, []).append(nid)

    # time_order — event 간 chronological + event 안 compose 등장 순.
    edges: list[EdgeDTO] = []
    prev_last: Optional[str] = None
    for event in HOOK_EVENT_ORDER:
        members = hook_event_nodes.get(event, [])
        if not members:
            continue
        for a, b in zip(members, members[1:]):
            edges.append(EdgeDTO(source=a, target=b, kind="time_order"))
        if prev_last is not None:
            edges.append(EdgeDTO(source=prev_last, target=members[0], kind="time_order"))
        prev_last = members[-1]

    clusters = [
        ClusterDTO(id=d, label=d, color=DOMAIN_COLORS[d], node_ids=by_domain.get(d, []))
        for d in DOMAIN_COLORS
    ]
    return GraphDTO(nodes=nodes, edges=edges, clusters=clusters)


def _try_resolve(resolver: Resolver, artifact_id: str) -> tuple[Optional[Manifest], Optional[str]]:
    try:
        path = resolver.resolve(artifact_id)
    except IdNotFound as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)
    try:
        return parse_manifest(path), None
    except Exception as e:
        return None, str(e)


def _build_badges(entry: ComposeEntry, manifest: Optional[Manifest]) -> list[str]:
    badges = []
    if manifest is None:
        badges.append("manifest_missing")
        return badges
    if entry.role is None and len(manifest.roles) > 1:
        badges.append("role_missing")
    if entry.role == "hard_rule" or "hard_rule" in (manifest.roles or []):
        badges.append("hard_rule")
    if manifest.provenance == "external":
        badges.append("external")
    return badges
