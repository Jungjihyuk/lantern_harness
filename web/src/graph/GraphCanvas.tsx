import { useEffect, useMemo } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  Edge,
  MarkerType,
  Node,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { useComposeStore } from '../state/composeStore';
import { autoLayout, domainAtX } from './layout';
import { nodeTypes } from './nodeTypes';

const ARROW = { type: MarkerType.ArrowClosed, color: '#666', width: 18, height: 18 };
const EDGE_STYLE = { stroke: '#666', strokeWidth: 1.5 };

export function GraphCanvas() {
  const graph = useComposeStore((s) => s.graph);
  const loadAll = useComposeStore((s) => s.loadAll);
  const selectNode = useComposeStore((s) => s.selectNode);
  const moveEntry = useComposeStore((s) => s.moveEntry);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const onNodeDragStop = (_: any, n: Node) => {
    const node = graph?.nodes.find((g) => g.id === n.id);
    if (!node) return;
    const newDomain = domainAtX(n.position.x);
    if (newDomain && newDomain !== node.domain) {
      // hooks 메커니즘이라면 section 도 'hooks' 로 유지. context.* 는 cognition 도메인 전용.
      const newSection = node.section.startsWith('context.')
        ? node.section          // context.* 는 cognition 안에서만 의미. 도메인 바꿀 시 경고는 backend 가 validation 으로.
        : node.section;
      moveEntry(node.entry_index, { new_domain: newDomain, new_section: newSection });
    }
  };

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
        onNodeDragStop={onNodeDragStop}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </ReactFlowProvider>
  );
}
