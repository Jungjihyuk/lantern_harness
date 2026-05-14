// Backend API client (P1 read-only).

export interface ComposeEntryDTO {
  id: string;
  role: string | null;
  domain: string;
  section: string;
  extras: Record<string, unknown>;
}

export interface ComposeDTO {
  version: number;
  entries: ComposeEntryDTO[];
  policies: Record<string, unknown>;
  memory: Record<string, unknown>;
  source_path: string | null;
}

export interface NodeDTO {
  id: string;
  entry_index: number;
  artifact_id: string;
  role: string | null;
  domain: string;
  section: string;
  extras: Record<string, unknown>;
  manifest_found: boolean;
  manifest_purpose: string | null;
  badges: string[];
}

export interface EdgeDTO {
  source: string;
  target: string;
  kind: 'time_order' | 'artifact_share' | 'context_dep';
}

export interface ClusterDTO {
  id: string;
  label: string;
  color: string;
  node_ids: string[];
}

export interface GraphDTO {
  nodes: NodeDTO[];
  edges: EdgeDTO[];
  clusters: ClusterDTO[];
}

export interface ArtifactSummaryDTO {
  id: string;
  domain: string;
  mechanism: string;
  purpose: string;
  roles: string[];
  provenance: string;
  source_path: string;
  layer: 'standard' | 'know-how' | 'unknown';
  in_compose: boolean;
}

export interface ArtifactFileDTO {
  path: string;
  size: number;
  is_binary: boolean;
}

export interface ArtifactDetailDTO {
  summary: ArtifactSummaryDTO;
  manifest: Record<string, unknown>;
  files: ArtifactFileDTO[];
}

export interface ValidateDTO {
  ok: boolean;
  errors: string[];
  entry_count_by_domain: Record<string, number>;
}

async function getJSON<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) {
    throw new Error(`${path}: ${r.status} ${await r.text()}`);
  }
  return r.json();
}

async function getText(path: string): Promise<string> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.text();
}

export const api = {
  health:      () => getJSON<{ ok: boolean; version: string }>('/api/health'),
  compose:     () => getJSON<ComposeDTO>('/api/compose'),
  graph:       () => getJSON<GraphDTO>('/api/compose/graph'),
  artifacts:   () => getJSON<ArtifactSummaryDTO[]>('/api/artifacts'),
  artifact:    (id: string) => getJSON<ArtifactDetailDTO>(`/api/artifacts/${encodeURIComponent(id)}`),
  artifactFile:(id: string, path: string) =>
    getText(`/api/artifacts/${encodeURIComponent(id)}/files?path=${encodeURIComponent(path)}`),
  validate:    () => getJSON<ValidateDTO>('/api/validate'),
};
