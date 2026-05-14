import { create } from 'zustand';
import {
  api,
  ArtifactDetailDTO,
  ArtifactSummaryDTO,
  ComposeDTO,
  EntryCreateRequest,
  EntryUpdateRequest,
  GraphDTO,
  MutationResponse,
  NodeDTO,
  ValidateDTO,
} from '../api/client';

interface ComposeStore {
  compose: ComposeDTO | null;
  graph: GraphDTO | null;
  validation: ValidateDTO | null;
  artifacts: ArtifactSummaryDTO[];
  selectedNodeId: string | null;
  selectedArtifact: ArtifactDetailDTO | null;
  error: string | null;
  loading: boolean;

  loadAll: () => Promise<void>;
  selectNode: (nodeId: string | null) => Promise<void>;

  addEntry:    (req: EntryCreateRequest) => Promise<void>;
  patchEntry:  (entryIndex: number, req: EntryUpdateRequest) => Promise<void>;
  deleteEntry: (entryIndex: number) => Promise<void>;
}

function nodeIdForEntry(graph: GraphDTO | null, entryIndex: number): string | null {
  if (!graph) return null;
  return graph.nodes.find((n) => n.entry_index === entryIndex)?.id ?? null;
}

export const useComposeStore = create<ComposeStore>((set, get) => ({
  compose: null,
  graph: null,
  validation: null,
  artifacts: [],
  selectedNodeId: null,
  selectedArtifact: null,
  error: null,
  loading: false,

  async loadAll() {
    set({ loading: true, error: null });
    try {
      const [compose, graph, validation, artifacts] = await Promise.all([
        api.compose(),
        api.graph(),
        api.validate(),
        api.artifacts(),
      ]);
      set({ compose, graph, validation, artifacts, loading: false });
    } catch (e: any) {
      set({ error: String(e.message ?? e), loading: false });
    }
  },

  async selectNode(nodeId) {
    set({ selectedNodeId: nodeId, selectedArtifact: null });
    if (!nodeId) return;
    const node = get().graph?.nodes.find((n) => n.id === nodeId);
    if (!node) return;
    try {
      const detail = await api.artifact(node.artifact_id);
      set({ selectedArtifact: detail });
    } catch (e: any) {
      set({ error: String(e.message ?? e) });
    }
  },

  async addEntry(req) {
    try {
      const m = await api.addEntry(req);
      applyMutation(set, get, m);
      // 추가된 노드 자동 선택
      if (m.affected_index != null) {
        const nid = nodeIdForEntry(m.graph, m.affected_index);
        if (nid) await get().selectNode(nid);
      }
    } catch (e: any) {
      set({ error: String(e.message ?? e) });
    }
  },

  async patchEntry(entryIndex, req) {
    try {
      const m = await api.patchEntry(entryIndex, req);
      applyMutation(set, get, m);
      if (m.affected_index != null) {
        const nid = nodeIdForEntry(m.graph, m.affected_index);
        if (nid) await get().selectNode(nid);
      }
    } catch (e: any) {
      set({ error: String(e.message ?? e) });
    }
  },

  async deleteEntry(entryIndex) {
    try {
      const m = await api.deleteEntry(entryIndex);
      applyMutation(set, get, m);
      set({ selectedNodeId: null, selectedArtifact: null });
    } catch (e: any) {
      set({ error: String(e.message ?? e) });
    }
  },
}));

function applyMutation(
  set: (s: Partial<ComposeStore>) => void,
  _get: () => ComposeStore,
  m: MutationResponse,
) {
  set({
    compose: m.compose,
    graph: m.graph,
    validation: m.validation,
    error: null,
  });
  // artifacts 의 in_compose 가 바뀔 수 있어 재로드
  api.artifacts().then((artifacts) => set({ artifacts })).catch(() => {});
}

export type SelectedNode = NodeDTO | null;
