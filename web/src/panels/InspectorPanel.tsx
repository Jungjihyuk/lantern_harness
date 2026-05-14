import { useEffect, useState } from 'react';
import { useComposeStore } from '../state/composeStore';
import { api, NodeDTO } from '../api/client';

export function InspectorPanel() {
  const selectedNodeId = useComposeStore((s) => s.selectedNodeId);
  const graph = useComposeStore((s) => s.graph);
  const detail = useComposeStore((s) => s.selectedArtifact);
  const patchEntry = useComposeStore((s) => s.patchEntry);
  const deleteEntry = useComposeStore((s) => s.deleteEntry);
  const writeArtifactFile = useComposeStore((s) => s.writeArtifactFile);
  const writeManifest = useComposeStore((s) => s.writeManifest);
  const moveArtifact = useComposeStore((s) => s.moveArtifact);

  const [openFile, setOpenFile] = useState<string | null>(null);
  const [fileBody, setFileBody] = useState<string>('');
  const [fileDirty, setFileDirty] = useState(false);
  const [manifestDraft, setManifestDraft] = useState<string>('');
  const [manifestDirty, setManifestDirty] = useState(false);
  const [manifestError, setManifestError] = useState<string | null>(null);

  // 선택 노드 변경 시 reset
  useEffect(() => {
    setOpenFile(null);
    setFileBody('');
    setFileDirty(false);
    setManifestError(null);
  }, [selectedNodeId]);

  // detail 변경 시 manifest draft 동기화
  useEffect(() => {
    if (detail) {
      setManifestDraft(JSON.stringify(detail.manifest, null, 2));
      setManifestDirty(false);
    }
  }, [detail]);

  // openFile 변경 시 본문 로드
  useEffect(() => {
    if (!detail || !openFile) return;
    setFileDirty(false);
    api
      .artifactFile(detail.summary.id, openFile)
      .then((t) => {
        setFileBody(t);
      })
      .catch((e) => setFileBody(`(read failed: ${e.message})`));
  }, [detail, openFile]);

  if (!selectedNodeId) {
    return <div className="inspector-empty">노드를 클릭해 상세를 보세요.</div>;
  }

  const node: NodeDTO | undefined = graph?.nodes.find((n) => n.id === selectedNodeId);
  if (!node) {
    return <div className="inspector-empty">노드 정보가 없습니다.</div>;
  }

  const onRoleChange = (newRole: string) => {
    if (newRole === '') {
      patchEntry(node.entry_index, { clear_role: true });
    } else {
      patchEntry(node.entry_index, { role: newRole });
    }
  };

  const onDelete = () => {
    if (!confirm(`Remove "${node.artifact_id}" from ${node.domain}.${node.section}?`)) return;
    deleteEntry(node.entry_index);
  };

  const onSaveFile = () => {
    if (!detail || !openFile) return;
    writeArtifactFile(detail.summary.id, openFile, fileBody).then(() => setFileDirty(false));
  };

  const onSaveManifest = () => {
    if (!detail) return;
    try {
      const parsed = JSON.parse(manifestDraft);
      if (typeof parsed !== 'object' || parsed === null) {
        setManifestError('manifest 는 object 여야 함');
        return;
      }
      setManifestError(null);
      writeManifest(detail.summary.id, parsed).then(() => setManifestDirty(false));
    } catch (e: any) {
      setManifestError(`JSON parse: ${e.message}`);
    }
  };

  const onMoveLayer = () => {
    if (!detail) return;
    const target = detail.summary.layer === 'standard' ? 'know-how' : 'standard';
    if (!confirm(`Move "${detail.summary.id}" to ${target}?`)) return;
    moveArtifact(detail.summary.id, target);
  };

  return (
    <div>
      <h2>{node.artifact_id}</h2>
      <div style={{ color: '#666', fontSize: 12 }}>
        {node.domain}.{node.section}
        {node.role ? ` · ${node.role}` : ''}
      </div>

      <div className="inspector-actions">
        <button className="delete-btn" onClick={onDelete}>
          Remove from compose
        </button>
      </div>

      {!detail && <div style={{ color: '#999', marginTop: 12 }}>Loading...</div>}

      {detail && (
        <>
          <h3>Role</h3>
          <select
            className="role-select"
            value={node.role ?? ''}
            onChange={(e) => onRoleChange(e.target.value)}
          >
            <option value="">(none — manifest 첫 role)</option>
            {detail.summary.roles.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>

          <h3>Purpose</h3>
          <div>{detail.summary.purpose}</div>

          <h3>Layer</h3>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>
              {detail.summary.layer} · {detail.summary.provenance}
            </span>
            <button onClick={onMoveLayer}>
              → {detail.summary.layer === 'standard' ? 'know-how' : 'standard'}
            </button>
          </div>

          <h3>Manifest (편집 가능, JSON)</h3>
          <textarea
            className="code-textarea"
            value={manifestDraft}
            onChange={(e) => {
              setManifestDraft(e.target.value);
              setManifestDirty(true);
              setManifestError(null);
            }}
            rows={10}
            spellCheck={false}
          />
          {manifestError && <div className="status-error">{manifestError}</div>}
          {manifestDirty && (
            <div className="inspector-actions">
              <button onClick={onSaveManifest}>Save manifest</button>
            </div>
          )}

          <h3>Files</h3>
          {detail.files.length === 0 && <div style={{ color: '#999' }}>(없음)</div>}
          {detail.files.map((f) => (
            <div
              key={f.path}
              className={`file-row ${openFile === f.path ? 'active' : ''}`}
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
              <textarea
                className="code-textarea"
                value={fileBody}
                onChange={(e) => {
                  setFileBody(e.target.value);
                  setFileDirty(true);
                }}
                rows={16}
                spellCheck={false}
              />
              {fileDirty && (
                <div className="inspector-actions">
                  <button onClick={onSaveFile}>Save file</button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
