"""Compose entry 단위 CRUD — 순수 함수 (mutate on Compose).

routes 가 호출. 각 op 후 compose_writer.write_compose 로 file 동기화.
"""
from __future__ import annotations

from typing import Optional

from lib.compose import Compose, ComposeEntry


class ComposeOpError(ValueError):
    """compose op 입력 오류."""


_KNOWN_DOMAINS = {"cognition", "state", "action", "guard", "observe"}


def _validate_domain_section(domain: str, section: str) -> None:
    if domain not in _KNOWN_DOMAINS:
        raise ComposeOpError(f"unknown domain: {domain}")
    if not section or section.startswith(".") or section.endswith("."):
        raise ComposeOpError(f"invalid section: {section!r}")


def add_entry(
    compose: Compose,
    *,
    domain: str,
    section: str,
    id_: str,
    role: Optional[str] = None,
    extras: Optional[dict] = None,
    after_index: Optional[int] = None,
) -> int:
    """compose.entries 에 새 entry 추가. 추가된 index 반환.

    after_index 미지정 시 같은 (domain, section) 의 마지막 다음 위치에.
    """
    _validate_domain_section(domain, section)
    if not id_:
        raise ComposeOpError("id_ 가 비어있음")

    new = ComposeEntry(
        id=id_,
        role=role,
        domain=domain,
        section=section,
        extras=dict(extras or {}),
    )

    if after_index is not None:
        if not (-1 <= after_index < len(compose.entries)):
            raise ComposeOpError(f"after_index out of range: {after_index}")
        insert_at = after_index + 1
    else:
        # 같은 (domain, section) 의 마지막 다음
        last = -1
        for i, e in enumerate(compose.entries):
            if e.domain == domain and e.section == section:
                last = i
        insert_at = last + 1 if last >= 0 else len(compose.entries)

    compose.entries.insert(insert_at, new)
    return insert_at


def remove_entry(compose: Compose, index: int) -> ComposeEntry:
    """index 위치 entry 제거. 제거된 entry 반환."""
    if not (0 <= index < len(compose.entries)):
        raise ComposeOpError(f"entry index out of range: {index}")
    return compose.entries.pop(index)


def update_entry(
    compose: Compose,
    index: int,
    *,
    role: Optional[str] = None,
    extras: Optional[dict] = None,
    clear_role: bool = False,
) -> ComposeEntry:
    """index 위치 entry 의 role / extras 갱신. id/domain/section 변경은 별 op.

    role=None 이고 clear_role=False 면 role 미변경.
    clear_role=True 면 role 을 None 으로 명시적 set.
    extras=None 이면 미변경.
    """
    if not (0 <= index < len(compose.entries)):
        raise ComposeOpError(f"entry index out of range: {index}")
    e = compose.entries[index]
    new_role = None if clear_role else (role if role is not None else e.role)
    new_extras = dict(extras) if extras is not None else dict(e.extras)
    compose.entries[index] = ComposeEntry(
        id=e.id,
        role=new_role,
        domain=e.domain,
        section=e.section,
        extras=new_extras,
    )
    return compose.entries[index]
