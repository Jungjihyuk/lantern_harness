"""Compose → compose.yaml 직렬화. flow style 보존.

parse_compose 의 역방향. raw dict 에서 policies / memory 같은 비-entry 영역은
그대로 보존하고, entries 가 들어있던 모든 (domain, section) 위치를 새 list 로 갱신.
"""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

from lib.compose import Compose, ComposeEntry


# ───────────── flow style 보존 ─────────────

class _FlowDict(dict):
    """yaml.safe_dump 시 한 줄 dict (예: `{id: foo, role: bar}`) 로 출력."""
    pass


def _flow_repr(dumper, data):
    return dumper.represent_mapping("tag:yaml.org,2002:map", data, flow_style=True)


yaml.add_representer(_FlowDict, _flow_repr, Dumper=yaml.SafeDumper)


def _entry_to_yaml(e: ComposeEntry):
    """ComposeEntry → yaml 입력 형태.

    role/extras 없음 → bare string id. 그 외 → {id, role, **extras} flow dict.
    """
    if e.role is None and not e.extras:
        return e.id
    d: dict = {"id": e.id}
    if e.role is not None:
        d["role"] = e.role
    d.update(e.extras)
    return _FlowDict(d)


# ───────────── raw dict 위치 헬퍼 ─────────────

def _scan_entry_sections(raw: dict) -> set[tuple[str, str]]:
    """raw 에서 entry-list 가 들어있을 수 있는 (domain, section) 모두.

    parse_compose 의 분류 기준과 같음:
    - 'policies', 'memory' 는 skip
    - 'context' (cognition) → 'context.<sub>' 형식으로 각 sub 추가
    """
    out: set[tuple[str, str]] = set()
    for domain, block in raw.items():
        if not isinstance(block, dict):
            continue
        for key, value in block.items():
            if key == "policies":
                continue
            if key == "memory" and domain == "state":
                continue
            if key == "context" and domain == "cognition":
                if isinstance(value, dict):
                    for sub in value.keys():
                        out.add((domain, f"context.{sub}"))
                continue
            out.add((domain, key))
    return out


def _set_at(raw: dict, domain: str, section: str, items: list) -> None:
    """raw[domain][section] = items. dotted section 처리."""
    domain_block = raw.setdefault(domain, {})
    if "." in section:
        parts = section.split(".")
        cur = domain_block
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = items
    else:
        domain_block[section] = items


# ───────────── 메인 ─────────────

def dump_compose(compose: Compose) -> str:
    """Compose → yaml text. write 안 함."""
    raw = copy.deepcopy(compose.raw) if compose.raw else {"version": compose.version}

    grouped: dict[tuple[str, str], list] = {}
    for e in compose.entries:
        grouped.setdefault((e.domain, e.section), []).append(_entry_to_yaml(e))

    # 기존 raw 의 모든 entry-list 위치 + 신규 위치 union
    all_locations = _scan_entry_sections(raw) | set(grouped.keys())
    for (domain, section) in all_locations:
        _set_at(raw, domain, section, grouped.get((domain, section), []))

    return yaml.safe_dump(
        raw, default_flow_style=False, allow_unicode=True, sort_keys=False
    )


def write_compose(compose: Compose, path: Path) -> None:
    """compose.yaml 파일에 기록 (atomic: tmp + rename)."""
    text = dump_compose(compose)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
