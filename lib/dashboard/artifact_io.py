"""Artifact (manifest + 본문 파일) read/write.

P1 은 read 만. write 는 P2/P3.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from lib.manifest import Manifest, parse_manifest

_BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".tar", ".gz"}
_MAX_READ_BYTES = 1_000_000      # 1MB text 상한


class ArtifactIOError(ValueError):
    """artifact_io 작업 오류."""


def list_artifact_files(manifest_path: Path) -> list[dict]:
    """manifest.yaml 이 있는 폴더의 모든 파일 메타 (recursive).

    Returns: [{path, size, is_binary}, ...]
    """
    root = manifest_path.parent
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p == manifest_path:
            # manifest 자체는 별개 항목으로 노출 (raw dict 형태)
            continue
        rel = p.relative_to(root).as_posix()
        is_bin = p.suffix.lower() in _BINARY_EXT
        out.append({"path": rel, "size": p.stat().st_size, "is_binary": is_bin})
    return out


def read_manifest_raw(manifest_path: Path) -> dict:
    """manifest.yaml 의 원본 dict (Manifest dataclass 가 아닌 raw)."""
    with open(manifest_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ArtifactIOError(f"{manifest_path}: manifest 루트가 dict 가 아님")
    return data


def read_artifact_file(manifest_path: Path, rel_path: str) -> str:
    """artifact 폴더 안의 파일 본문 read (text only).

    path traversal 차단 — rel_path 가 manifest 디렉토리 안에 머무름 검증.
    """
    root = manifest_path.parent.resolve()
    target = (root / rel_path).resolve()
    if not str(target).startswith(str(root) + "/") and target != root:
        raise ArtifactIOError(f"path traversal 시도: {rel_path}")
    if not target.exists():
        raise FileNotFoundError(f"파일 없음: {rel_path}")
    if not target.is_file():
        raise ArtifactIOError(f"파일 아님: {rel_path}")
    if target.suffix.lower() in _BINARY_EXT:
        raise ArtifactIOError(f"binary 파일은 본 API 로 read 불가: {rel_path}")
    if target.stat().st_size > _MAX_READ_BYTES:
        raise ArtifactIOError(f"파일 너무 큼 ({target.stat().st_size} bytes): {rel_path}")
    return target.read_text(encoding="utf-8")


def detect_layer(manifest_path: Path, standard_root: Path, know_how_root: Path) -> str:
    """manifest 가 standard/ 인지 know-how/ 인지 판별."""
    m = manifest_path.resolve()
    if str(m).startswith(str(standard_root.resolve()) + "/"):
        return "standard"
    if str(m).startswith(str(know_how_root.resolve()) + "/"):
        return "know-how"
    return "unknown"


def parse_manifest_safe(manifest_path: Path) -> Manifest | None:
    """parse_manifest 의 안전 래퍼 — 실패 시 None."""
    try:
        return parse_manifest(manifest_path)
    except Exception:
        return None


# ───────────── write ─────────────

def write_artifact_file(manifest_path: Path, rel_path: str, content: str) -> int:
    """artifact 폴더 안의 파일 본문 write. text only.

    path traversal 차단. binary 확장자 차단. 1MB 상한.
    return: written bytes.
    """
    root = manifest_path.parent.resolve()
    target = (root / rel_path).resolve()
    if not str(target).startswith(str(root) + "/") and target != root:
        raise ArtifactIOError(f"path traversal 시도: {rel_path}")
    if target.suffix.lower() in _BINARY_EXT:
        raise ArtifactIOError(f"binary 파일은 본 API 로 write 불가: {rel_path}")
    encoded = content.encode("utf-8")
    if len(encoded) > _MAX_READ_BYTES:
        raise ArtifactIOError(
            f"파일 너무 큼 ({len(encoded)} bytes, max {_MAX_READ_BYTES})"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(target)
    return len(encoded)


def write_manifest_raw(manifest_path: Path, data: dict) -> None:
    """manifest.yaml 갱신. 필수 필드 검증 통과 후 atomic write."""
    if not isinstance(data, dict):
        raise ArtifactIOError("manifest 는 dict 여야 함")
    required = ("id", "domain", "mechanism", "purpose", "roles")
    missing = [k for k in required if k not in data]
    if missing:
        raise ArtifactIOError(f"manifest 필수 필드 누락: {missing}")
    tmp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    tmp.write_text(
        yaml.safe_dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    tmp.replace(manifest_path)


def move_artifact_layer(
    manifest_path: Path,
    standard_root: Path,
    know_how_root: Path,
    to_layer: str,
) -> Path:
    """artifact 를 standard ↔ know-how 사이 이동.

    `<source_root>/<mechanism>/<id>/...` 전체 폴더를
    `<target_root>/<mechanism>/<id>/...` 로 이동.
    return: 새 manifest path.
    """
    if to_layer not in ("standard", "know-how"):
        raise ArtifactIOError(f"to_layer must be 'standard' or 'know-how', got {to_layer!r}")

    src_layer = detect_layer(manifest_path, standard_root, know_how_root)
    if src_layer == to_layer:
        raise ArtifactIOError(f"이미 {to_layer} 에 있음")
    if src_layer == "unknown":
        raise ArtifactIOError(f"layer 식별 불가: {manifest_path}")

    src_root = standard_root if src_layer == "standard" else know_how_root
    dst_root = standard_root if to_layer == "standard" else know_how_root

    artifact_dir = manifest_path.parent.resolve()
    rel = artifact_dir.relative_to(src_root.resolve())
    dst = (dst_root / rel).resolve()
    if dst.exists():
        raise ArtifactIOError(f"대상 위치 이미 존재: {dst}")

    import shutil
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(artifact_dir), str(dst))
    return dst / manifest_path.name
