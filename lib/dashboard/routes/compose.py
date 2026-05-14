"""GET /api/compose, GET /api/compose/graph — P1 read-only."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from lib.compose import ComposeError, parse_compose
from lib.resolver import Resolver

from lib.dashboard.context import DashboardContext
from lib.dashboard.graph import build_graph
from lib.dashboard.schema import ComposeDTO, ComposeEntryDTO, GraphDTO

router = APIRouter(prefix="/api/compose", tags=["compose"])


def get_context() -> DashboardContext:
    return DashboardContext.discover()


@router.get("", response_model=ComposeDTO)
def read_compose(ctx: DashboardContext = Depends(get_context)) -> ComposeDTO:
    try:
        compose = parse_compose(ctx.compose_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ComposeError as e:
        raise HTTPException(status_code=400, detail=f"compose 파싱 실패: {e}")

    entries = [
        ComposeEntryDTO(
            id=e.id, role=e.role, domain=e.domain, section=e.section, extras=e.extras
        )
        for e in compose.entries
    ]
    return ComposeDTO(
        version=compose.version,
        entries=entries,
        policies=compose.policies,
        memory=compose.memory,
        source_path=str(compose.source_path) if compose.source_path else None,
    )


@router.get("/graph", response_model=GraphDTO)
def read_graph(ctx: DashboardContext = Depends(get_context)) -> GraphDTO:
    try:
        compose = parse_compose(ctx.compose_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ComposeError as e:
        raise HTTPException(status_code=400, detail=f"compose 파싱 실패: {e}")

    resolver = Resolver(standard_root=ctx.standard_root, know_how_root=ctx.know_how_root)
    return build_graph(compose, resolver)
