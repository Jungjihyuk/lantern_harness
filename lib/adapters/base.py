"""Provider 어댑터 공통 인터페이스.

각 provider (Claude Code, Codex, ...) driver는 ProviderDriver를 상속해
list()를 구현. 향후 disable/enable/remove/install 메서드를 점진적으로 추가.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


# 지원하는 아티팩트 종류 — provider별로 부분 지원 가능
KINDS = ("mcp", "skill", "plugin")


@dataclass
class Item:
    """provider에 설치된 아티팩트 한 건의 정규화된 표현.

    name은 provider 내 표시 이름. 같은 name이 (provider, kind) 다른 항목에
    중복될 수 있으므로 unique id가 아님. 정확 지칭이 필요할 때는
    (provider, kind, name) 셋을 함께 사용.
    """

    name: str              # 아티팩트 표시 이름 (provider/kind 안에서만 유효)
    provider: str          # 소속 provider (예: "claude")
    kind: str              # mcp | skill | plugin
    enabled: bool          # 활성 상태
    source: str            # 출처 경로/파일 (예: ~/.claude/mcp.json)
    meta: dict = field(default_factory=dict)  # version, trigger, command 등


class ItemNotFound(LookupError):
    """disable/enable 대상 아이템이 provider 상태에 존재하지 않을 때."""


class ProviderDriver(ABC):
    """provider별 어댑터 베이스 클래스.

    Phase 1: list()
    Phase 2: disable() / enable()
    """

    # provider 식별자 ("claude", "codex", ...). 서브클래스에서 override.
    id: str = ""

    @abstractmethod
    def list(self, kind: Optional[str] = None) -> list[Item]:
        """설치된 아티팩트 목록 반환.

        kind=None 이면 모든 종류, 아니면 해당 kind만.
        disabled 상태인 아이템도 enabled=False 로 함께 반환.
        """
        ...

    @abstractmethod
    def disable(self, kind: str, name: str) -> bool:
        """아이템을 disabled 상태로 전환.

        반환:
          True  — 상태가 실제로 변경됨 (enabled → disabled)
          False — 이미 disabled 상태 (no-op)

        예외:
          ItemNotFound — 해당 (kind, name) 아이템이 존재하지 않음
        """
        ...

    @abstractmethod
    def enable(self, kind: str, name: str) -> bool:
        """아이템을 enabled 상태로 전환.

        반환:
          True  — 상태가 실제로 변경됨 (disabled → enabled)
          False — 이미 enabled 상태 (no-op)

        예외:
          ItemNotFound — 해당 (kind, name) 아이템이 존재하지 않음
        """
        ...
