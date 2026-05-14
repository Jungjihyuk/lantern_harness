"""compose entry CRUD endpoints.

- GET    /api/compose                — 전체
- GET    /api/compose/graph          — React Flow 용
- POST   /api/compose/entries        — entry 추가
- PATCH  /api/compose/entries/{idx}  — role / extras 갱신
- DELETE /api/compose/entries/{idx}  — 제거

mutation 응답에 compose + graph + validate 임베드 → UI 가 한 번에 반영.
"""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException

from lib.compose import ComposeError, parse_compose
from lib.resolver import Resolver
from lib.roles_registry import RolesRegistryError, load_roles
from lib.validator import validate_compose

from lib.dashboard.compose_ops import ComposeOpError, add_entry, remove_entry, update_entry
from lib.dashboard.compose_writer import write_compose
from lib.dashboard.context import DashboardContext
from lib.dashboard.graph import build_graph
from lib.dashboard.schema import (
    ComposeDTO,
    ComposeEntryDTO,
    EntryCreateRequest,
    EntryUpdateRequest,
    GraphDTO,
    MutationResponse,
    ValidateDTO,
)

router = APIRouter(prefix="/api/compose", tags=["compose"])


def get_context() -> DashboardContext:
    return DashboardContext.discover()


# ───────────── helpers ─────────────

def _load(ctx: DashboardContext):
    try:
        compose = parse_compose(ctx.compose_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ComposeError as e:
        raise HTTPException(status_code=400, detail=f"compose 파싱 실패: {e}")
    return compose


def _compose_to_dto(compose) -> ComposeDTO:
    return ComposeDTO(
        version=compose.version,
        entries=[
            ComposeEntryDTO(id=e.id, role=e.role, domain=e.domain, section=e.section, extras=e.extras)
            for e in compose.entries
        ],
        policies=compose.policies,
        memory=compose.memory,
        source_path=str(compose.source_path) if compose.source_path else None,
    )


def _build_validate(ctx: DashboardContext, compose) -> ValidateDTO:
    resolver = Resolver(standard_root=ctx.standard_root, know_how_root=ctx.know_how_root)
    try:
        roles_registry = load_roles(ctx.standard_root, ctx.know_how_root)
    except (RolesRegistryError, FileNotFoundError) as e:
        return ValidateDTO(ok=False, errors=[f"roles.yaml 로드 실패: {e}"])
    errors = validate_compose(compose, resolver, roles_registry)
    counts = Counter(e.domain for e in compose.entries)
    return ValidateDTO(ok=(not errors), errors=errors, entry_count_by_domain=dict(counts))


def _build_graph_dto(ctx: DashboardContext, compose) -> GraphDTO:
    resolver = Resolver(standard_root=ctx.standard_root, know_how_root=ctx.know_how_root)
    return build_graph(compose, resolver)


def _mutation_response(
    ctx: DashboardContext, compose, affected_index: int | None = None
) -> MutationResponse:
    return MutationResponse(
        compose=_compose_to_dto(compose),
        graph=_build_graph_dto(ctx, compose),
        validation=_build_validate(ctx, compose),
        affected_index=affected_index,
    )


def _find_index_after_write(
    compose,
    *,
    domain: str,
    section: str,
    id_: str,
    role: str | None,
) -> int | None:
    """write 후 fresh parse 한 compose 에서 (domain, section, id, role) 매칭 마지막 index.

    add 후 file 에서 다시 parse 한 entries 의 새 위치를 찾기 위함.
    같은 키가 여러 개일 수 있으므로 마지막 occurrence 반환.
    """
    found = None
    for i, e in enumerate(compose.entries):
        if (e.domain == domain and e.section == section
                and e.id == id_ and e.role == role):
            found = i
    return found


# ───────────── GET ─────────────

@router.get("", response_model=ComposeDTO)
def read_compose(ctx: DashboardContext = Depends(get_context)) -> ComposeDTO:
    return _compose_to_dto(_load(ctx))


@router.get("/graph", response_model=GraphDTO)
def read_graph(ctx: DashboardContext = Depends(get_context)) -> GraphDTO:
    return _build_graph_dto(ctx, _load(ctx))


# ───────────── mutation ─────────────

@router.post("/entries", response_model=MutationResponse, status_code=201)
def create_entry(
    req: EntryCreateRequest, ctx: DashboardContext = Depends(get_context)
) -> MutationResponse:
    compose = _load(ctx)
    try:
        add_entry(
            compose,
            domain=req.domain,
            section=req.section,
            id_=req.id,
            role=req.role,
            extras=dict(req.extras),
            after_index=req.after_index,
        )
    except ComposeOpError as e:
        raise HTTPException(status_code=400, detail=str(e))
    write_compose(compose, ctx.compose_path)
    # write 후 fresh parse — entries 순서가 file 순서와 일치하도록
    fresh = parse_compose(ctx.compose_path)
    affected = _find_index_after_write(
        fresh, domain=req.domain, section=req.section, id_=req.id, role=req.role
    )
    return _mutation_response(ctx, fresh, affected_index=affected)


@router.patch("/entries/{index}", response_model=MutationResponse)
def patch_entry(
    index: int,
    req: EntryUpdateRequest,
    ctx: DashboardContext = Depends(get_context),
) -> MutationResponse:
    compose = _load(ctx)
    try:
        updated = update_entry(
            compose,
            index,
            role=req.role,
            extras=req.extras,
            clear_role=req.clear_role,
        )
    except ComposeOpError as e:
        raise HTTPException(status_code=400, detail=str(e))
    write_compose(compose, ctx.compose_path)
    fresh = parse_compose(ctx.compose_path)
    # 패치된 entry 의 새 위치 = 같은 (domain, section, id, role) 의 마지막
    affected = _find_index_after_write(
        fresh,
        domain=updated.domain,
        section=updated.section,
        id_=updated.id,
        role=updated.role,
    )
    return _mutation_response(ctx, fresh, affected_index=affected)


@router.delete("/entries/{index}", response_model=MutationResponse)
def delete_entry(
    index: int, ctx: DashboardContext = Depends(get_context)
) -> MutationResponse:
    compose = _load(ctx)
    try:
        remove_entry(compose, index)
    except ComposeOpError as e:
        raise HTTPException(status_code=400, detail=str(e))
    write_compose(compose, ctx.compose_path)
    fresh = parse_compose(ctx.compose_path)
    return _mutation_response(ctx, fresh, affected_index=None)
