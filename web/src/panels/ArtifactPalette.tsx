import { useMemo, useState } from 'react';
import { ArtifactSummaryDTO } from '../api/client';
import { useComposeStore } from '../state/composeStore';

// artifact 의 domain → 추가할 default section.
// (manifest 의 mechanism + domain 으로 어디로 갈지 결정. 단순화 — 사용자가 클릭한 후
//  Inspector 에서 role 을 set 하는 흐름.)
const DEFAULT_SECTION_BY_DOMAIN: Record<string, string> = {
  cognition: 'prefix',
  state: 'hooks',
  action: 'adapters',
  guard: 'hooks',
  observe: 'hooks',
};

function defaultSection(a: ArtifactSummaryDTO): string {
  // context.suggested 같이 cognition 의 context 메커니즘은 manifest 의 mechanism 으로 식별
  if (a.domain === 'cognition' && a.mechanism === 'instructions') return 'prefix';
  if (a.mechanism === 'hooks') return 'hooks';
  if (a.mechanism === 'workflows') return 'workflows';
  if (a.mechanism === 'adapters') return 'adapters';
  return DEFAULT_SECTION_BY_DOMAIN[a.domain] ?? 'hooks';
}

export function ArtifactPalette() {
  const artifacts = useComposeStore((s) => s.artifacts);
  const addEntry = useComposeStore((s) => s.addEntry);
  const [filter, setFilter] = useState('');

  const grouped = useMemo(() => {
    const f = filter.toLowerCase().trim();
    const filtered = !f
      ? artifacts
      : artifacts.filter(
          (a) =>
            a.id.toLowerCase().includes(f) ||
            a.purpose.toLowerCase().includes(f) ||
            a.domain.includes(f),
        );
    const map: Record<string, ArtifactSummaryDTO[]> = {};
    for (const a of filtered) {
      (map[a.domain] ??= []).push(a);
    }
    return map;
  }, [artifacts, filter]);

  const handleAdd = (a: ArtifactSummaryDTO) => {
    addEntry({
      domain: a.domain,
      section: defaultSection(a),
      id: a.id,
      role: a.roles.length === 1 ? a.roles[0] : null,
    });
  };

  return (
    <>
      <h2>Artifacts ({artifacts.length})</h2>
      <input
        className="palette-search"
        type="text"
        placeholder="filter (id / purpose / domain)"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      {['cognition', 'state', 'action', 'guard', 'observe'].map((d) => {
        const items = grouped[d] ?? [];
        if (items.length === 0) return null;
        return (
          <div key={d} className="palette-section">
            <h3>{d}</h3>
            {items.map((a) => (
              <div
                key={`${a.id}@${a.source_path}`}
                className={`palette-row ${a.in_compose ? 'in-compose' : ''}`}
                onClick={() => handleAdd(a)}
                title={`${a.purpose}\n클릭: ${a.domain}.${defaultSection(a)} 에 추가`}
              >
                <div className="palette-id">{a.id}</div>
                <div className="palette-meta">
                  {a.mechanism} · {a.layer}
                  {a.in_compose ? ' · in compose' : ''}
                </div>
              </div>
            ))}
          </div>
        );
      })}
    </>
  );
}
