import { create } from 'zustand';
import { api, GraphDTO, ArtifactDetailDTO, ValidateDTO } from '../api/client';

interface ComposeStore {
  graph: GraphDTO | null;
  validate: ValidateDTO | null;
  selectedNodeId: string | null;
  selectedArtifact: ArtifactDetailDTO | null;
  error: string | null;
  loading: boolean;

  loadGraph: () => Promise<void>;
  loadValidate: () => Promise<void>;
  selectNode: (nodeId: string | null) => Promise<void>;
}

export const useComposeStore = create<ComposeStore>((set, get) => ({
  graph: null,
  validate: null,
  selectedNodeId: null,
  selectedArtifact: null,
  error: null,
  loading: false,

  async loadGraph() {
    set({ loading: true, error: null });
    try {
      const graph = await api.graph();
      set({ graph, loading: false });
    } catch (e: any) {
      set({ error: String(e.message ?? e), loading: false });
    }
  },

  async loadValidate() {
    try {
      const v = await api.validate();
      set({ validate: v });
    } catch {
      // 무시 (graph 가 있으면 충분)
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
}));
