"""GET /api/artifacts — 전체 카탈로그 + 상세 + 파일 본문 (P1 read-only)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from lib.compose import parse_compose
from lib.resolver import IdNotFound, Resolver

from lib.dashboard.artifact_io import (
    ArtifactIOError,
    detect_layer,
    list_artifact_files,
    move_artifact_layer,
    parse_manifest_safe,
    read_artifact_file,
    read_manifest_raw,
    write_artifact_file,
    write_manifest_raw,
)
from lib.dashboard.context import DashboardContext
from lib.dashboard.routes.compose import get_context
from lib.dashboard.schema import (
    ArtifactDetailDTO,
    ArtifactFileDTO,
    ArtifactMoveRequest,
    ArtifactSummaryDTO,
    FileWriteRequest,
    ManifestWriteRequest,
)

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


def _summarize(
    artifact_id: str,
    manifest_path: Path,
    ctx: DashboardContext,
    in_compose_ids: set[str],
) -> ArtifactSummaryDTO | None:
    m = parse_manifest_safe(manifest_path)
    if m is None:
        return None
    layer = detect_layer(manifest_path, ctx.standard_root, ctx.know_how_root)
    return ArtifactSummaryDTO(
        id=m.id,
        domain=m.domain,
        mechanism=m.mechanism,
        purpose=m.purpose,
        roles=list(m.roles),
        provenance=m.provenance,
        source_path=str(manifest_path),
        layer=layer,
        in_compose=(artifact_id in in_compose_ids),
    )


@router.get("", response_model=list[ArtifactSummaryDTO])
def list_artifacts(ctx: DashboardContext = Depends(get_context)) -> list[ArtifactSummaryDTO]:
    resolver = Resolver(standard_root=ctx.standard_root, know_how_root=ctx.know_how_root)
    # in_compose set
    try:
        compose = parse_compose(ctx.compose_path)
        in_compose_ids = {e.id for e in compose.entries}
    except Exception:
        in_compose_ids = set()

    out: list[ArtifactSummaryDTO] = []
    for aid in resolver.all_ids():
        try:
            path = resolver.resolve(aid)
        except Exception:
            continue
        s = _summarize(aid, path, ctx, in_compose_ids)
        if s is not None:
            out.append(s)
    return out


@router.get("/{artifact_id}", response_model=ArtifactDetailDTO)
def show_artifact(
    artifact_id: str, ctx: DashboardContext = Depends(get_context)
) -> ArtifactDetailDTO:
    resolver = Resolver(standard_root=ctx.standard_root, know_how_root=ctx.know_how_root)
    try:
        path = resolver.resolve(artifact_id)
    except IdNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        compose = parse_compose(ctx.compose_path)
        in_compose_ids = {e.id for e in compose.entries}
    except Exception:
        in_compose_ids = set()

    summary = _summarize(artifact_id, path, ctx, in_compose_ids)
    if summary is None:
        raise HTTPException(status_code=400, detail=f"manifest 파싱 실패: {artifact_id}")

    raw = read_manifest_raw(path)
    files = [ArtifactFileDTO(**f) for f in list_artifact_files(path)]
    return ArtifactDetailDTO(summary=summary, manifest=raw, files=files)


@router.get("/{artifact_id}/files", response_class=PlainTextResponse)
def read_artifact_file_route(
    artifact_id: str,
    path: str = Query(..., description="manifest 폴더 내 relative path"),
    ctx: DashboardContext = Depends(get_context),
) -> str:
    resolver = Resolver(standard_root=ctx.standard_root, know_how_root=ctx.know_how_root)
    try:
        manifest_path = resolver.resolve(artifact_id)
    except IdNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        return read_artifact_file(manifest_path, path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ArtifactIOError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ───────────── mutation (P3) ─────────────

@router.put("/{artifact_id}/files")
def write_artifact_file_route(
    artifact_id: str,
    req: FileWriteRequest,
    path: str = Query(..., description="manifest 폴더 내 relative path"),
    ctx: DashboardContext = Depends(get_context),
) -> dict:
    resolver = Resolver(standard_root=ctx.standard_root, know_how_root=ctx.know_how_root)
    try:
        manifest_path = resolver.resolve(artifact_id)
    except IdNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        written = write_artifact_file(manifest_path, path, req.content)
    except (FileNotFoundError, ArtifactIOError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "bytes": written, "path": path}


@router.put("/{artifact_id}", response_model=ArtifactDetailDTO)
def write_manifest_route(
    artifact_id: str,
    req: ManifestWriteRequest,
    ctx: DashboardContext = Depends(get_context),
) -> ArtifactDetailDTO:
    resolver = Resolver(standard_root=ctx.standard_root, know_how_root=ctx.know_how_root)
    try:
        manifest_path = resolver.resolve(artifact_id)
    except IdNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    new_id = req.manifest.get("id")
    if new_id is not None and new_id != artifact_id:
        raise HTTPException(status_code=400, detail="manifest.id 변경은 별 op (move) 필요")
    try:
        write_manifest_raw(manifest_path, req.manifest)
    except ArtifactIOError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # 응답 — 갱신 후 detail 재조회
    return show_artifact(artifact_id, ctx)


@router.post("/{artifact_id}/move", response_model=ArtifactDetailDTO)
def move_artifact_route(
    artifact_id: str,
    req: ArtifactMoveRequest,
    ctx: DashboardContext = Depends(get_context),
) -> ArtifactDetailDTO:
    """artifact 폴더를 standard ↔ know-how 사이 이동."""
    resolver = Resolver(standard_root=ctx.standard_root, know_how_root=ctx.know_how_root)
    try:
        manifest_path = resolver.resolve(artifact_id)
    except IdNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        move_artifact_layer(manifest_path, ctx.standard_root, ctx.know_how_root, req.to)
    except ArtifactIOError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # 새 위치에서 detail 재조회 — Resolver 가 다시 인덱싱 필요
    return show_artifact(artifact_id, ctx)
