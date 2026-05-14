import { useEffect, useMemo } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  Edge,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { useComposeStore } from '../state/composeStore';
import { autoLayout } from './layout';
import { nodeTypes } from './nodeTypes';

const ARROW = { type: MarkerType.ArrowClosed, color: '#666', width: 18, height: 18 };
const EDGE_STYLE = { stroke: '#666', strokeWidth: 1.5 };

export function GraphCanvas() {
  const graph = useComposeStore((s) => s.graph);
  const loadAll = useComposeStore((s) => s.loadAll);
  const selectNode = useComposeStore((s) => s.selectNode);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const rfNodes = useMemo(() => {
    if (!graph) return [];
    return autoLayout(graph.nodes, graph.clusters);
  }, [graph]);

  const rfEdges: Edge[] = useMemo(() => {
    if (!graph) return [];
    return graph.edges.map((e, i) => ({
      id: `e${i}`,
      source: e.source,
      target: e.target,
      type: 'smoothstep',
      animated: false,
      style: EDGE_STYLE,
      markerEnd: ARROW,
    }));
  }, [graph]);

  if (!graph) {
    return <div style={{ padding: 24 }}>Loading graph...</div>;
  }

  return (
    <ReactFlowProvider>
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, n) => selectNode(n.id)}
        onPaneClick={() => selectNode(null)}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </ReactFlowProvider>
  );
}
