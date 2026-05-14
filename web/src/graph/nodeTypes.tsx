import { Handle, Position, NodeProps } from '@xyflow/react';
import { ClusterDTO, NodeDTO } from '../api/client';

interface ComposeEntryNodeData {
  node: NodeDTO;
  cluster?: ClusterDTO;
}

export function ComposeEntryNode({ data, selected }: NodeProps) {
  const { node, cluster } = data as unknown as ComposeEntryNodeData;
  const borderColor = cluster?.color ?? '#ccc';
  const hardRule = node.badges.includes('hard_rule');
  const external = node.badges.includes('external');

  return (
    <div
      className="node-card"
      style={{
        borderColor: hardRule ? '#ef4444' : borderColor,
        borderStyle: external ? 'dashed' : 'solid',
        outline: selected ? '2px solid #3b82f6' : 'none',
      }}
    >
      <Handle type="target" position={Position.Left} />
      <div className="node-id">{node.artifact_id}</div>
      <div className="node-role">
        {node.domain}.{node.section}
        {node.role ? ` · ${node.role}` : ''}
      </div>
      <div>
        {node.badges.map((b) => (
          <span key={b} className={`badge badge-${b}`}>
            {b}
          </span>
        ))}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export const nodeTypes = {
  composeEntry: ComposeEntryNode,
};
