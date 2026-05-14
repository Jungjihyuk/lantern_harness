# Dashboard 수동 테스트 시나리오

P1 (read-only viewer) 의 demoable 확인. 자동 회귀는 backend TestClient + `lib/eval/runner.py` 가 담당.

## 사전 준비

```bash
# 백엔드 deps (1회)
pip3 install --user fastapi 'uvicorn[standard]' 'pydantic>=2'

# 프론트엔드 빌드 (변경 시마다)
cd web && npm install && npm run build
```

`npm run build` 가 `dist/` 를 만든 뒤 `postbuild` 가 자동으로 `lib/dashboard/static/` 에 복사.

## 시나리오

### 1. 빈 프로젝트에서 dashboard 띄우기

```bash
mkdir /tmp/h-demo && cd /tmp/h-demo
harness init                    # 또는 dev: HARNESS_HOME=... bash bin/cmd/init.sh
harness dashboard --port 8766
```

브라우저 자동 오픈. 화면:
- 좌측: 5 도메인 cluster (cognition/state/action/guard/observe) 별로 노드 분포
- 우측: "노드를 클릭해 상세를 보세요." placeholder
- 상단 toolbar: `N entries · M edges` + `✓ valid` 배지

### 2. 노드 클릭 → manifest preview

`session_start` 노드 클릭. 우측 InspectorPanel 에:
- Purpose
- Roles (manifest.roles)
- Layer (`standard`) · Provenance (`local`)
- Manifest (raw JSON)
- Files (handler.sh 등). 클릭하면 본문 inline 표시.

### 3. 같은 hook 의 다중 role 시각화

`pre_tool_use` 가 `cognition.context_gating`, `guard.required_check`, `guard.cognitive_guard`, `guard.path_blocklist`, `observe.trace_log` 등 여러 entry 로 표시되는지 확인.
같은 artifact_id (`pre_tool_use`) 끼리 점선 (`artifact_share`) 으로 이어짐.

### 4. validate 결과 즉시 반영

`.harness/compose.yaml` 을 vim 으로 열어 의도적 에러 (예: 존재하지 않는 id) 추가 후 저장. 브라우저 새로고침 → toolbar 가 `✗ N error` 로 바뀜.

### 5. 외부 standard 자산 (Karpathy) 클릭

`agents_md_karpathy` 노드 (cognition.prefix 안) 클릭 → 우측에 `provenance: external` + 점선 테두리 노드 / Manifest 의 `source` URL 확인.

### 6. API 직접 호출

`http://127.0.0.1:8766/docs` — FastAPI Swagger UI. 모든 GET endpoint 인터랙티브 실행.

## 개발 모드

```bash
# 터미널 1: backend (reload)
harness dashboard --port 8766 --reload --no-open

# 터미널 2: frontend dev (hot reload, proxy 자동)
cd web && npm run dev
# → http://localhost:5173 자동 오픈
```

`vite.config.ts` 가 `/api/*` 를 `8766` 로 proxy.

## P1 범위 밖

P1 은 read-only. 이하 동작 X (P2/P3 에서 추가):
- 노드 드래그로 도메인간 이동
- entry 추가 / 제거 클릭
- manifest / handler.sh 인라인 편집
- 실시간 sync (외부 vim 편집 자동 감지)
