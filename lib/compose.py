"""compose.yaml v2 파서 — 5 도메인 × entry 구조 정규화 (v2).

v2 schema 는 docs/architecture-v2-schema.md §6 (A-5) 기준.

특징:
  - 5 도메인 최상위 키 (cognition / state / action / guard / observe)
  - 각 도메인 안에 메커니즘별 entry 리스트 (`hooks: [...]`, `tools: [...]`, etc.)
  - entry 는 단순 string id 또는 {id, role} dict
  - 같은 id 가 여러 도메인에 다른 role 로 등장 가능 (N:N)

사용 예:
    from lib.compose import parse_compose
    c = parse_compose(Path(".harness/compose.yaml"))
    for e in c.entries:
        print(e.domain, e.section, e.id, e.role)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from lib.manifest import DOMAINS


# 도메인 안에서 entry-리스트를 가질 수 있는 표준 키들 (참고용 — 실제 파싱은 모든 list-of-string|dict 를 받음)
ENTRY_SECTIONS = (
    "instructions",
    "rules",
    "hooks",
    "workflows",
    "tools",
    "adapters",
    "evals",
    "traces",
)


class ComposeError(ValueError):
    """compose.yaml 형식 / 내용 오류."""


@dataclass
class ComposeEntry:
    """compose.yaml 의 한 entry — `{id, role}` 또는 단순 `id` 의 정규화 표현."""

    id: str
    role: Optional[str]          # 없으면 None (manifest 의 첫/단일 role 가정)
    domain: str                  # cognition / state / action / guard / observe
    section: str                 # 'hooks', 'rules', 'context.required', etc.
    extras: dict = field(default_factory=dict)  # when, source 등 추가 옵션


@dataclass
class Compose:
    """compose.yaml 한 파일의 정규화 표현."""

    version: int
    entries: list[ComposeEntry] = field(default_factory=list)
    policies: dict = field(default_factory=dict)   # guard.policies 등 — flat 결합
    memory: dict = field(default_factory=dict)     # state.memory 같은 dict 설정
    raw: dict = field(default_factory=dict)        # 원본 dict (디버그용)
    source_path: Optional[Path] = None


def parse_compose(path: Path) -> Compose:
    """compose.yaml 파일을 읽어 Compose 반환.

    Raises:
        FileNotFoundError, ComposeError
    """
    if not path.exists():
        raise FileNotFoundError(f"compose.yaml 없음: {path}")

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return _from_dict(data, source_path=path)


def _from_dict(data: dict, source_path: Optional[Path] = None) -> Compose:
    if not isinstance(data, dict):
        raise ComposeError("compose.yaml 루트가 dict 가 아님")

    version = data.get("version", 1)
    if version != 2:
        raise ComposeError(f"v2 파서가 v{version} 처리 시도 — version: 2 필요")

    compose = Compose(version=2, raw=data, source_path=source_path)

    for domain in DOMAINS:
        if domain not in data:
            continue
        block = data[domain]
        if not isinstance(block, dict):
            raise ComposeError(f"domain '{domain}' 는 dict 여야 함")
        _parse_domain_block(compose, domain, block)

    return compose


def _parse_domain_block(compose: Compose, domain: str, block: dict) -> None:
    """한 도메인 dict 를 순회해 entries / policies / memory 등 분류."""
    for key, value in block.items():
        if key == "policies":
            # 모든 도메인에서 .policies 는 flat dict 로 결합
            if not isinstance(value, dict):
                raise ComposeError(f"{domain}.policies 는 dict 여야 함")
            compose.policies.update(value)
            continue

        if key == "memory" and domain == "state":
            if not isinstance(value, dict):
                raise ComposeError(f"state.memory 는 dict 여야 함")
            compose.memory.update(value)
            continue

        if key == "context" and domain == "cognition":
            # cognition.context.{required, triggered, suggested}
            if not isinstance(value, dict):
                raise ComposeError(f"cognition.context 는 dict 여야 함")
            for sub_key, sub_list in value.items():
                section = f"context.{sub_key}"
                _ingest_entry_list(compose, domain, section, sub_list)
            continue

        # 그 외는 entry 리스트로 간주
        _ingest_entry_list(compose, domain, key, value)


def _ingest_entry_list(
    compose: Compose,
    domain: str,
    section: str,
    raw_list: Any,
) -> None:
    """entry-list 한 묶음을 파싱해 compose.entries 에 추가."""
    if raw_list is None:
        return
    if not isinstance(raw_list, list):
        raise ComposeError(
            f"{domain}.{section} 은 list 여야 함 (실제: {type(raw_list).__name__})"
        )
    for raw in raw_list:
        entry = _parse_entry(raw, domain=domain, section=section)
        compose.entries.append(entry)


def _parse_entry(raw: Any, domain: str, section: str) -> ComposeEntry:
    """단일 entry 를 ComposeEntry 로. string 또는 dict 둘 다 지원."""
    if isinstance(raw, str):
        return ComposeEntry(id=raw, role=None, domain=domain, section=section)
    if isinstance(raw, dict):
        if "id" not in raw:
            raise ComposeError(f"{domain}.{section} entry 에 'id' 누락: {raw!r}")
        id_ = str(raw["id"])
        role = raw.get("role")
        extras = {k: v for k, v in raw.items() if k not in ("id", "role")}
        return ComposeEntry(
            id=id_,
            role=str(role) if role is not None else None,
            domain=domain,
            section=section,
            extras=extras,
        )
    raise ComposeError(
        f"{domain}.{section} entry 형식 오류 — string 또는 dict 만 허용. 실제: {raw!r}"
    )
