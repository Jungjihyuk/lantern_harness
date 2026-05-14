import { useEffect, useState } from 'react';
import { useComposeStore } from '../state/composeStore';
import { api } from '../api/client';

export function InspectorPanel() {
  const selectedNodeId = useComposeStore((s) => s.selectedNodeId);
  const graph = useComposeStore((s) => s.graph);
  const detail = useComposeStore((s) => s.selectedArtifact);
  const [openFile, setOpenFile] = useState<string | null>(null);
  const [fileBody, setFileBody] = useState<string>('');

  useEffect(() => {
    setOpenFile(null);
    setFileBody('');
  }, [selectedNodeId]);

  useEffect(() => {
    if (!detail || !openFile) return;
    api
      .artifactFile(detail.summary.id, openFile)
      .then(setFileBody)
      .catch((e) => setFileBody(`(read failed: ${e.message})`));
  }, [detail, openFile]);

  if (!selectedNodeId) {
    return <div className="inspector-empty">노드를 클릭해 상세를 보세요.</div>;
  }

  const node = graph?.nodes.find((n) => n.id === selectedNodeId);

  return (
    <div>
      <h2>{node?.artifact_id ?? selectedNodeId}</h2>
      <div style={{ color: '#666', fontSize: 12 }}>
        {node?.domain}.{node?.section}
        {node?.role ? ` · ${node.role}` : ''}
      </div>

      {!detail && <div style={{ color: '#999', marginTop: 12 }}>Loading...</div>}

      {detail && (
        <>
          <h3>Purpose</h3>
          <div>{detail.summary.purpose}</div>

          <h3>Roles</h3>
          <div>{detail.summary.roles.join(', ') || '(없음)'}</div>

          <h3>Layer / Provenance</h3>
          <div>
            {detail.summary.layer} · {detail.summary.provenance}
            {detail.summary.in_compose ? ' · in compose' : ''}
          </div>

          <h3>Manifest (raw)</h3>
          <pre>{JSON.stringify(detail.manifest, null, 2)}</pre>

          <h3>Files</h3>
          {detail.files.length === 0 && <div style={{ color: '#999' }}>(없음)</div>}
          {detail.files.map((f) => (
            <div
              key={f.path}
              className="file-row"
              style={{ cursor: f.is_binary ? 'default' : 'pointer' }}
              onClick={() => !f.is_binary && setOpenFile(f.path)}
            >
              <span>{f.path}</span>
              <span style={{ color: '#999' }}>{f.size}b</span>
            </div>
          ))}

          {openFile && (
            <>
              <h3>{openFile}</h3>
              <pre style={{ maxHeight: 240, overflow: 'auto' }}>{fileBody}</pre>
            </>
          )}
        </>
      )}
    </div>
  );
}
