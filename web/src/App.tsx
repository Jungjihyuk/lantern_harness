import { ArtifactPalette } from './panels/ArtifactPalette';
import { GraphCanvas } from './graph/GraphCanvas';
import { InspectorPanel } from './panels/InspectorPanel';
import { useComposeStore } from './state/composeStore';

export default function App() {
  const validation = useComposeStore((s) => s.validation);
  const graph = useComposeStore((s) => s.graph);
  const error = useComposeStore((s) => s.error);

  return (
    <div className="app-layout">
      <div className="palette-pane">
        <ArtifactPalette />
      </div>
      <div className="graph-pane">
        <div className="toolbar">
          <h1>harness dashboard</h1>
          <div>
            {graph
              ? `${graph.nodes.length} entries · ${graph.edges.length} edges`
              : '로딩 중'}
            {validation && (
              <span
                className={validation.ok ? 'status-ok' : 'status-error'}
                style={{ marginLeft: 8 }}
              >
                {validation.ok ? '✓ valid' : `✗ ${validation.errors.length} error`}
              </span>
            )}
          </div>
          {error && <div className="status-error">Error: {error}</div>}
        </div>
        <GraphCanvas />
      </div>
      <div className="inspector-pane">
        <InspectorPanel />
      </div>
    </div>
  );
}
