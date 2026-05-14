"""DashboardContext — project root / standard / know-how / compose 경로 holder.

server startup 시 1회 생성. routes 들이 의존성 주입으로 받음.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DashboardContext:
    project_root: Path           # .harness/ 를 포함하는 dir
    compose_path: Path           # .harness/compose.yaml
    standard_root: Path          # 글로벌 standard/ (~/.harness/standard 또는 dev tree)
    know_how_root: Path          # .harness/know-how/
    runtime_root: Path           # .harness/runtime/

    @classmethod
    def discover(cls, project_root: Optional[Path] = None) -> "DashboardContext":
        """현재 cwd 또는 명시된 path 기준으로 dashboard context 구성."""
        pr = (project_root or Path.cwd()).resolve()
        harness_dir = pr / ".harness"
        if not harness_dir.exists():
            raise FileNotFoundError(
                f".harness/ 없음 — '{pr}' 에서 `harness init` 먼저 실행")

        standard_root = _find_standard_root()
        if standard_root is None:
            raise FileNotFoundError(
                "standard/ 위치 못 찾음. HARNESS_HOME 확인 또는 dev tree 위치 확인")

        return cls(
            project_root=pr,
            compose_path=harness_dir / "compose.yaml",
            standard_root=standard_root,
            know_how_root=harness_dir / "know-how",
            runtime_root=harness_dir / "runtime",
        )


def _find_standard_root() -> Optional[Path]:
    """install 된 ~/.harness/standard 우선, 없으면 dev tree fallback."""
    harness_home = Path(os.environ.get("HARNESS_HOME", Path.home() / ".harness"))
    if (harness_home / "standard").exists():
        return harness_home / "standard"
    # dev tree: 이 파일이 lib/dashboard/context.py 라 가정. ../../standard
    dev = Path(__file__).resolve().parent.parent.parent / "standard"
    if dev.exists():
        return dev
    return None
