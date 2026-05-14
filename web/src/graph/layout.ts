// Domain 별 column 자동 배치 — n8n 처럼 좌→우 흐름.

import { Node } from '@xyflow/react';
import { ClusterDTO, NodeDTO } from '../api/client';

export const DOMAIN_ORDER = ['cognition', 'state', 'action', 'guard', 'observe'];
export const COL_WIDTH = 280;
export const ROW_HEIGHT = 96;
export const COL_GAP = 32;
export const COL_LEFT_PAD = 80;

export function colXFor(domain: string): number {
  const idx = DOMAIN_ORDER.indexOf(domain);
  const col = idx === -1 ? DOMAIN_ORDER.length : idx;
  return col * (COL_WIDTH + COL_GAP) + COL_LEFT_PAD;
}

export function domainAtX(x: number): string {
  // 가장 가까운 column 의 도메인.
  let best = DOMAIN_ORDER[0];
  let bestDist = Infinity;
  for (const d of DOMAIN_ORDER) {
    const cx = colXFor(d) + COL_WIDTH / 2;
    const dist = Math.abs(cx - x);
    if (dist < bestDist) {
      bestDist = dist;
      best = d;
    }
  }
  return best;
}

export function autoLayout(nodes: NodeDTO[], clusters: ClusterDTO[]): Node[] {
  const rowCounter: Record<string, number> = {};

  return nodes.map((n) => {
    rowCounter[n.domain] = (rowCounter[n.domain] ?? 0) + 1;
    const row = rowCounter[n.domain] - 1;

    return {
      id: n.id,
      type: 'composeEntry',
      position: { x: colXFor(n.domain), y: row * ROW_HEIGHT + 80 },
      data: {
        node: n,
        cluster: clusters.find((c) => c.id === n.domain),
      },
    };
  });
}
