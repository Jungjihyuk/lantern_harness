"""Artifact resolver — id → path 매핑 (v2).

compose.yaml 에서 사용하는 id 가 실제로 어느 manifest.yaml 폴더에 있는지 찾기.

규칙 (§8.6.3 결정):
  - standard/ 와 know-how/ 양쪽에서 매니페스트 발견
  - 같은 id 가 양쪽에 동시 존재 시 → IdConflict 에러 (override 의도는 다른 id 로 강제)
  - id 가 어디에도 없음 → IdNotFound 에러

사용 예:
    from lib.resolver import Resolver
    r = Resolver(standard_root=Path("standard"), know_how_root=Path("know-how"))
    path = r.resolve("pre_tool_use")
    # path == Path("standard/hooks/pre_tool_use/manifest.yaml")
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from lib.manifest import Manifest, parse_manifest


MANIFEST_FILE = "manifest.yaml"


class ResolverError(LookupError):
    """resolver 의 모든 에러의 베이스."""


class IdNotFound(ResolverError):
    """id 가 어디에도 없음."""


class IdConflict(ResolverError):
    """같은 id 가 standard + know-how 양쪽에 존재."""


class Resolver:
    """artifact id 를 통해 실제 manifest 파일 위치를 찾는 인덱서.

    초기화 시 standard/ + know-how/ 의 모든 manifest.yaml 을 탐색해 인덱스 구축.
    충돌 (양쪽 같은 id) 있으면 즉시 IdConflict.
    """

    def __init__(
        self,
        standard_root: Path,
        know_how_root: Optional[Path] = None,
    ):
        self.standard_root = standard_root
        self.know_how_root = know_how_root
        self._registry: dict[str, Path] = {}
        self._conflicts: dict[str, list[Path]] = {}
        self._build_index()

    def resolve(self, id: str) -> Path:
        """id 로 manifest.yaml 경로 반환.

        Raises:
            IdConflict: 양쪽에 동시 존재
            IdNotFound: 어디에도 없음
        """
        if id in self._conflicts:
            paths = ", ".join(str(p) for p in self._conflicts[id])
            raise IdConflict(
                f"id '{id}' 가 양쪽에 존재 — override 원하면 know-how 측 id 를 다르게 설정. "
                f"충돌 위치: {paths}"
            )
        if id not in self._registry:
            raise IdNotFound(f"id '{id}' 를 standard/know-how 어디서도 못 찾음")
        return self._registry[id]

    def resolve_manifest(self, id: str) -> Manifest:
        """id 로 Manifest 객체 직접 반환 (resolve + parse_manifest 결합)."""
        return parse_manifest(self.resolve(id))

    def all_ids(self) -> list[str]:
        """현재 인덱스의 모든 id (충돌 항목 제외) 알파벳순."""
        return sorted(self._registry.keys())

    def conflicts(self) -> dict[str, list[Path]]:
        """충돌 id → 양쪽 경로 사본 반환."""
        return {k: list(v) for k, v in self._conflicts.items()}

    # ────────────────────── 내부 ──────────────────────

    def _build_index(self) -> None:
        """standard + know-how 의 manifest 들을 발견해 인덱스 구축."""
        std_ids = self._collect_ids(self.standard_root)
        kh_ids: dict[str, Path] = {}
        if self.know_how_root is not None and self.know_how_root.exists():
            kh_ids = self._collect_ids(self.know_how_root)

        # 충돌 검사
        common = set(std_ids) & set(kh_ids)
        for cid in common:
            self._conflicts[cid] = [std_ids[cid], kh_ids[cid]]

        # 충돌 없는 항목만 registry 에 등록
        for id_, path in std_ids.items():
            if id_ not in common:
                self._registry[id_] = path
        for id_, path in kh_ids.items():
            if id_ not in common:
                self._registry[id_] = path

    def _collect_ids(self, root: Path) -> dict[str, Path]:
        """root 아래 모든 manifest.yaml 을 찾아 id → path 사전 반환.

        한 root 안에서도 같은 id 중복 → 즉시 ResolverError.
        manifest 파싱 실패 → 그 파일만 skip (warning 출력은 caller 가).
        """
        out: dict[str, Path] = {}
        if not root.exists():
            return out
        for path in sorted(root.rglob(MANIFEST_FILE)):
            try:
                m = parse_manifest(path)
            except Exception:
                # 잘못된 manifest 는 일단 skip — Phase C 검증 단계에서 별도 보고
                continue
            if m.id in out:
                raise ResolverError(
                    f"같은 root 안 id 중복: '{m.id}' — {out[m.id]} 와 {path}"
                )
            out[m.id] = path
        return out
