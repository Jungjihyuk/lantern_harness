"""GET /api/validate — 현재 compose 검증 JSON."""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException

from lib.compose import ComposeError, parse_compose
from lib.resolver import Resolver
from lib.roles_registry import load_roles
from lib.validator import validate_compose

from lib.dashboard.context import DashboardContext
from lib.dashboard.routes.compose import get_context
from lib.dashboard.schema import ValidateDTO

router = APIRouter(prefix="/api/validate", tags=["validate"])


@router.get("", response_model=ValidateDTO)
def run_validate(ctx: DashboardContext = Depends(get_context)) -> ValidateDTO:
    try:
        compose = parse_compose(ctx.compose_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ComposeError as e:
        return ValidateDTO(ok=False, errors=[f"compose 파싱 실패: {e}"])

    resolver = Resolver(standard_root=ctx.standard_root, know_how_root=ctx.know_how_root)
    try:
        roles_registry = load_roles(ctx.standard_root, ctx.know_how_root)
    except Exception as e:
        return ValidateDTO(ok=False, errors=[f"roles.yaml 로드 실패: {e}"])

    errors = validate_compose(compose, resolver, roles_registry)
    counts = Counter(e.domain for e in compose.entries)
    return ValidateDTO(ok=(not errors), errors=errors, entry_count_by_domain=dict(counts))
