"""Pydantic v2 모델 — REST API request/response 스키마.

P1 은 read-only 라 응답 모델 위주.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ───────────── compose ─────────────

class ComposeEntryDTO(BaseModel):
    """compose entry 평면 표현."""
    id: str
    role: Optional[str] = None
    domain: str
    section: str
    extras: dict = Field(default_factory=dict)


class ComposeDTO(BaseModel):
    version: int = 2
    entries: list[ComposeEntryDTO]
    policies: dict = Field(default_factory=dict)
    memory: dict = Field(default_factory=dict)
    source_path: Optional[str] = None


# ───────────── graph ─────────────

class NodeDTO(BaseModel):
    """노드 = compose entry 1 개. UI 가 React Flow 노드로 렌더."""
    id: str                       # entry index 기반 unique key (예: "cognition.hooks.session_start.prefix_injection.0")
    entry_index: int              # compose.entries 안의 index
    artifact_id: str              # entry.id
    role: Optional[str]
    domain: str
    section: str
    extras: dict = Field(default_factory=dict)
    # 표시용 메타
    manifest_found: bool = True
    manifest_purpose: Optional[str] = None
    badges: list[str] = Field(default_factory=list)   # hard_rule / external / role_missing / validate_error


class EdgeDTO(BaseModel):
    source: str                    # NodeDTO.id
    target: str
    kind: str                      # "time_order" | "artifact_share" | "context_dep"


class ClusterDTO(BaseModel):
    """domain 클러스터 메타."""
    id: str                        # "cognition" 등
    label: str
    color: str
    node_ids: list[str]


class GraphDTO(BaseModel):
    nodes: list[NodeDTO]
    edges: list[EdgeDTO]
    clusters: list[ClusterDTO]


# ───────────── artifacts ─────────────

class ArtifactSummaryDTO(BaseModel):
    """artifact 카탈로그 한 항목."""
    id: str
    domain: str
    mechanism: str
    purpose: str
    roles: list[str]
    provenance: str = "local"
    source_path: str
    layer: str                     # "standard" | "know-how"
    in_compose: bool               # 현재 compose 에 등장 여부


class ArtifactFileDTO(BaseModel):
    path: str                      # manifest 폴더 내 relative path
    size: int
    is_binary: bool = False


class ArtifactDetailDTO(BaseModel):
    summary: ArtifactSummaryDTO
    manifest: dict                 # parsed manifest yaml (raw dict, UI 가 보고 편집)
    files: list[ArtifactFileDTO]


# ───────────── validate ─────────────

class ValidateDTO(BaseModel):
    ok: bool
    errors: list[str] = Field(default_factory=list)
    entry_count_by_domain: dict[str, int] = Field(default_factory=dict)


# ───────────── mutation request/response ─────────────

class EntryCreateRequest(BaseModel):
    domain: str
    section: str
    id: str
    role: Optional[str] = None
    extras: dict = Field(default_factory=dict)
    after_index: Optional[int] = None


class EntryUpdateRequest(BaseModel):
    role: Optional[str] = None
    extras: Optional[dict] = None
    clear_role: bool = False


class EntryMoveRequest(BaseModel):
    """drag&drop 결과 — domain / section / after_index 중 변경할 것만 지정."""
    new_domain: Optional[str] = None
    new_section: Optional[str] = None
    after_index: Optional[int] = None


class FileWriteRequest(BaseModel):
    content: str


class ManifestWriteRequest(BaseModel):
    manifest: dict


class ArtifactMoveRequest(BaseModel):
    to: str                        # "standard" | "know-how"


class MutationResponse(BaseModel):
    """모든 mutation 응답: 새 compose + validate 결과 임베드."""
    compose: ComposeDTO
    graph: GraphDTO
    validation: ValidateDTO
    affected_index: Optional[int] = None


# ───────────── error envelope ─────────────

class APIError(BaseModel):
    detail: str
    code: Optional[str] = None
    context: dict[str, Any] = Field(default_factory=dict)
