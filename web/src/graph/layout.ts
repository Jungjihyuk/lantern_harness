// Domain 별 column 자동 배치 — n8n 처럼 좌→우 흐름.
// dagre/elk 도입 전 단순 column layout.

import { Node } from '@xyflow/react';
import { ClusterDTO, NodeDTO } from '../api/client';

const DOMAIN_ORDER = ['cognition', 'state', 'action', 'guard', 'observe'];
const COL_WIDTH = 280;
const ROW_HEIGHT = 96;
const COL_GAP = 32;

export function autoLayout(nodes: NodeDTO[], clusters: ClusterDTO[]): Node[] {
  const colIndex: Record<string, number> = {};
  DOMAIN_ORDER.forEach((d, i) => (colIndex[d] = i));

  // domain 별 카운터
  const rowCounter: Record<string, number> = {};

  return nodes.map((n) => {
    const col = colIndex[n.domain] ?? DOMAIN_ORDER.length;
    rowCounter[n.domain] = (rowCounter[n.domain] ?? 0) + 1;
    const row = rowCounter[n.domain] - 1;

    return {
      id: n.id,
      type: 'composeEntry',
      position: { x: col * (COL_WIDTH + COL_GAP) + 80, y: row * ROW_HEIGHT + 80 },
      data: {
        node: n,
        cluster: clusters.find((c) => c.id === n.domain),
      },
    };
  });
}
