"""Provider driver 자동 발견 + dispatch.

standard/adapters/<provider>/driver.py 파일을 발견해 ProviderDriver
서브클래스를 찾아 인스턴스화한다.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Optional

from lib.adapters.base import Item, ProviderDriver


def _adapters_root() -> Path:
    """provider artifact (claude/, codex/, ...) 가 위치한 디렉토리.

    HARNESS_HOME 환경변수가 있으면 그 기준, 없으면 이 파일 기준 ../../standard/adapters.
    """
    home = os.environ.get("HARNESS_HOME")
    if home:
        return Path(home) / "standard" / "adapters"
    return Path(__file__).resolve().parent.parent.parent / "standard" / "adapters"


_ADAPTERS_DIR = _adapters_root()


def _load_driver(provider_dir: Path) -> Optional[ProviderDriver]:
    """provider_dir/driver.py 에서 ProviderDriver 서브클래스 인스턴스 1개를 반환."""
    driver_path = provider_dir / "driver.py"
    if not driver_path.exists():
        return None

    mod_name = f"_harness_provider_{provider_dir.name}"
    spec = importlib.util.spec_from_file_location(mod_name, driver_path)
    if not spec or not spec.loader:
        return None

    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        # driver 로드 실패는 silent (해당 provider만 스킵)
        return None

    for name in dir(mod):
        obj = getattr(mod, name)
        if (
            isinstance(obj, type)
            and issubclass(obj, ProviderDriver)
            and obj is not ProviderDriver
        ):
            return obj()
    return None


def discover_drivers() -> list[ProviderDriver]:
    """adapters/*/driver.py 발견 + 인스턴스화."""
    drivers: list[ProviderDriver] = []
    for entry in sorted(_ADAPTERS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        driver = _load_driver(entry)
        if driver is not None:
            drivers.append(driver)
    return drivers


def list_all(
    kind: Optional[str] = None,
    provider: Optional[str] = None,
) -> list[Item]:
    """모든 (또는 특정) provider의 아이템 통합 리스트."""
    items: list[Item] = []
    for driver in discover_drivers():
        if provider is not None and driver.id != provider:
            continue
        try:
            items.extend(driver.list(kind))
        except Exception:
            # 한 driver 실패가 전체를 막지 않도록 skip
            continue
    return items


def get_driver(provider_id: str) -> Optional[ProviderDriver]:
    """provider id 로 driver 인스턴스 조회. 없으면 None."""
    for driver in discover_drivers():
        if driver.id == provider_id:
            return driver
    return None
