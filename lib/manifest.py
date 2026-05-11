"""Manifest dataclass + parser + validator (v2).

각 artifact 폴더 안의 manifest.yaml 을 읽어 Manifest dataclass 로 표현.
schema 는 docs/architecture-v2-schema.md §5 (A-4) 기준.

사용 예:
    from lib.manifest import parse_manifest, validate_manifest

    m = parse_manifest(Path("standard/hooks/pre_tool_use/manifest.yaml"))
    errors = validate_manifest(m, allowed_roles=role_set)
    if errors:
        raise ValueError(errors)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


# v2 enum — 변경 시 schema 문서와 동기
DOMAINS = frozenset(("cognition", "state", "action", "guard", "observe"))
MECHANISMS = frozenset((
    "instructions",
    "hooks",
    "tools",
    "adapters",
    "workflows",
    "traces",
    "evals",
))


class ManifestError(ValueError):
    """manifest 검증 실패. 메시지에 구체 원인."""


@dataclass
class Manifest:
    """artifact 의 정규화된 메타 표현.

    필수 필드 (id/domain/mechanism/purpose/roles) 가 모두 채워져야 valid.
    선택 필드는 None / 빈 컨테이너 기본값.
    """

    # 필수
    id: str
    domain: str          # cognition / state / action / guard / observe
    mechanism: str       # instructions / hooks / tools / adapters / workflows / traces / evals
    purpose: str
    roles: list[str]     # 이 artifact 가 만족시킬 수 있는 role 목록

    # 선택
    provenance: str = "local"            # local | external
    origin: Optional[str] = None         # external 일 때 원본 경로/URL
    inputs: dict = field(default_factory=dict)
    outputs: list = field(default_factory=list)
    provides: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)

    # mechanism 별 추가 필드 (옵션)
    entry: Optional[str] = None          # hooks/tools/workflows — 실행 파일 경로
    event: Optional[str] = None          # hooks — 시점 (pre_tool_use 등)

    # 메타 — 원본 파일 경로 (resolver/디버깅용)
    source_path: Optional[Path] = None


def parse_manifest(path: Path) -> Manifest:
    """manifest.yaml 파일을 읽어 Manifest 반환.

    raises:
        FileNotFoundError — path 없음
        ManifestError — 필수 필드 누락
    """
    if not path.exists():
        raise FileNotFoundError(f"manifest 없음: {path}")

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ManifestError(f"{path}: manifest 루트가 dict 가 아님")

    return _from_dict(data, source_path=path)


def _from_dict(data: dict, source_path: Optional[Path] = None) -> Manifest:
    """dict → Manifest. 필수 필드 즉시 검사."""
    required = ("id", "domain", "mechanism", "purpose", "roles")
    missing = [k for k in required if k not in data]
    if missing:
        loc = f" ({source_path})" if source_path else ""
        raise ManifestError(f"필수 필드 누락{loc}: {', '.join(missing)}")

    roles = data["roles"]
    if not isinstance(roles, list):
        raise ManifestError(f"roles 는 list 여야 함 (실제: {type(roles).__name__})")

    return Manifest(
        id=str(data["id"]),
        domain=str(data["domain"]),
        mechanism=str(data["mechanism"]),
        purpose=str(data["purpose"]),
        roles=[str(r) for r in roles],
        provenance=str(data.get("provenance", "local")),
        origin=data.get("origin"),
        inputs=data.get("inputs") or {},
        outputs=data.get("outputs") or [],
        provides=data.get("provides") or [],
        requires=data.get("requires") or [],
        entry=data.get("entry"),
        event=data.get("event"),
        source_path=source_path,
    )


def validate_manifest(
    m: Manifest,
    allowed_roles: Optional[dict[str, frozenset[str]]] = None,
) -> list[str]:
    """Manifest 의 의미 검증. 발견된 에러 메시지 리스트 반환 (빈 리스트 = OK).

    Args:
        m: 검증 대상
        allowed_roles: 도메인별 허용 role enum. None 이면 role 검증 스킵.
            예: {"guard": frozenset({"required_check", ...}), ...}
    """
    errors: list[str] = []
    where = f"({m.source_path}) " if m.source_path else ""

    # id 형식
    if not m.id:
        errors.append(f"{where}id 가 비어있음")
    elif not _is_snake_case_id(m.id):
        errors.append(f"{where}id '{m.id}' 가 snake_case 권장 형식 아님")

    # domain enum
    if m.domain not in DOMAINS:
        errors.append(
            f"{where}domain '{m.domain}' 는 허용되지 않음. "
            f"허용: {sorted(DOMAINS)}"
        )

    # mechanism enum
    if m.mechanism not in MECHANISMS:
        errors.append(
            f"{where}mechanism '{m.mechanism}' 는 허용되지 않음. "
            f"허용: {sorted(MECHANISMS)}"
        )

    # provenance enum
    if m.provenance not in ("local", "external"):
        errors.append(f"{where}provenance '{m.provenance}' 는 local|external 만 허용")

    # roles 비어있지 않은지
    if not m.roles:
        errors.append(f"{where}roles 가 비어있음 — 최소 1개 필요")

    # roles enum (allowed_roles 제공 시)
    if allowed_roles is not None and m.domain in DOMAINS:
        domain_roles = allowed_roles.get(m.domain, frozenset())
        for r in m.roles:
            if r not in domain_roles:
                errors.append(
                    f"{where}role '{r}' 가 domain '{m.domain}' 의 roles.yaml 에 미등록"
                )

    return errors


def _is_snake_case_id(s: str) -> bool:
    """snake_case 권장 형식 검증 — 알파벳 소문자/숫자/언더스코어/하이픈만, 글자로 시작."""
    if not s:
        return False
    if not s[0].isalpha():
        return False
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_-@.")
    # @ 와 . 는 plugin id (예: "context-mode@context-mode") 허용
    return all(ch in allowed for ch in s)
