import { useEffect, useMemo } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { useComposeStore } from '../state/composeStore';
import { autoLayout } from './layout';
import { nodeTypes } from './nodeTypes';

const EDGE_STYLE = {
  time_order:     { stroke: '#666', strokeWidth: 1.5 },
  artifact_share: { stroke: '#aaa', strokeDasharray: '4 4' },
  context_dep:    { stroke: '#f59e0b', strokeDasharray: '2 4' },
};

export function GraphCanvas() {
  const graph = useComposeStore((s) => s.graph);
  const loadGraph = useComposeStore((s) => s.loadGraph);
  const loadValidate = useComposeStore((s) => s.loadValidate);
  const selectNode = useComposeStore((s) => s.selectNode);

  useEffect(() => {
    loadGraph();
    loadValidate();
  }, [loadGraph, loadValidate]);

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
      animated: false,
      style: EDGE_STYLE[e.kind],
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
