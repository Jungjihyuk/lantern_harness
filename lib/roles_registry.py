"""Roles registry — standard/roles.yaml + know-how/roles.yaml 병합 (v2).

도메인별 허용 role 사전을 구축. manifest validator 와 compose validator 가
"이 role 이 등록된 거 맞나?" 를 확인할 때 사용.

병합 규칙:
  - standard/roles.yaml — 기본 role 정의 (필수)
  - know-how/roles.yaml — 사용자 확장 role (선택)
  - 같은 도메인의 role 들은 union (중복은 dedup)
  - 도메인 충돌 없음 (다른 도메인 키는 그대로 병합)

사용 예:
    from lib.roles_registry import load_roles
    allowed = load_roles(standard_root=Path("standard"))
    # allowed == {"guard": frozenset({"required_check", "cognitive_guard", ...}), ...}
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from lib.manifest import DOMAINS


ROLES_FILE = "roles.yaml"


class RolesRegistryError(ValueError):
    """roles.yaml 형식 / 내용 오류."""


def load_roles(
    standard_root: Path,
    know_how_root: Optional[Path] = None,
) -> dict[str, frozenset[str]]:
    """standard/ + know-how/ 의 roles.yaml 을 병합해 도메인별 허용 role 사전 반환.

    Args:
        standard_root: standard/ 디렉토리 경로 (필수)
        know_how_root: know-how/ 디렉토리 경로 (선택)

    Returns:
        {domain: frozenset(role_names)}. roles.yaml 에 없는 도메인은 빈 집합 X — key 자체 없음.

    Raises:
        RolesRegistryError: 형식 오류 (도메인 enum 위반, value 가 list 아님 등)
        FileNotFoundError: standard/roles.yaml 이 없음
    """
    merged: dict[str, set[str]] = {}

    # standard 는 필수
    std_path = standard_root / ROLES_FILE
    if not std_path.exists():
        raise FileNotFoundError(f"필수 파일 없음: {std_path}")
    _merge_from_file(std_path, merged)

    # know-how 는 선택
    if know_how_root is not None:
        kh_path = know_how_root / ROLES_FILE
        if kh_path.exists():
            _merge_from_file(kh_path, merged)

    # set → frozenset 으로 불변화
    return {domain: frozenset(roles) for domain, roles in merged.items()}


def _merge_from_file(path: Path, merged: dict[str, set[str]]) -> None:
    """파일 하나 읽어 merged 사전에 union 으로 합침."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise RolesRegistryError(f"{path}: 루트가 dict 가 아님")

    for domain, roles in data.items():
        if domain not in DOMAINS:
            raise RolesRegistryError(
                f"{path}: 도메인 '{domain}' 는 허용되지 않음. "
                f"허용: {sorted(DOMAINS)}"
            )
        if not isinstance(roles, list):
            raise RolesRegistryError(
                f"{path}: domain '{domain}' 의 value 가 list 아님 "
                f"(실제: {type(roles).__name__})"
            )
        bucket = merged.setdefault(domain, set())
        for r in roles:
            if not isinstance(r, str):
                raise RolesRegistryError(
                    f"{path}: domain '{domain}' 안 role 이 문자열 아님: {r!r}"
                )
            if not r.strip():
                raise RolesRegistryError(f"{path}: domain '{domain}' 안 빈 role")
            bucket.add(r.strip())


def is_role_allowed(
    registry: dict[str, frozenset[str]],
    domain: str,
    role: str,
) -> bool:
    """domain 에서 role 이 허용되는지 확인. registry 미존재 도메인 → False."""
    return role in registry.get(domain, frozenset())
