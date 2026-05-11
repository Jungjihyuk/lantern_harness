#!/bin/bash
# harness scaffold <name>... — standard/templates/의 빈 문서를 프로젝트 루트로 복사.
# 자동으로 compose.yaml의 required_context.paths에도 추가 (--no-register로 비활성화).
#
# 옵션:
#   --all                 모든 템플릿 복사
#   --no-register         compose.yaml 자동 갱신 안 함

set -euo pipefail

HARNESS_HOME="$HOME/.harness"
TEMPLATES_DIR="$HARNESS_HOME/standard/templates"
PROJECT_ROOT="$(pwd)"
ACTIVE="$PROJECT_ROOT/.harness/compose.yaml"

REGISTER=1
names=()
for arg in "$@"; do
  case "$arg" in
    --no-register) REGISTER=0 ;;
    --all)
      for f in "$TEMPLATES_DIR"/*.md; do
        [[ -f "$f" ]] || continue
        names+=("$(basename "$f")")
      done
      ;;
    -h|--help|"")
      ;;
    *) names+=("$arg") ;;
  esac
done

if [[ ${#names[@]} -eq 0 ]]; then
  echo "Usage: harness scaffold <name>... | --all  [--no-register]"
  echo ""
  echo "Available templates:"
  for f in "$TEMPLATES_DIR"/*.md; do
    [[ -f "$f" ]] || continue
    name="$(basename "$f")"
    if [[ -e "$PROJECT_ROOT/$name" ]]; then
      echo "  - $name  [exists in project]"
    else
      echo "  - $name"
    fi
  done
  exit 0
fi

# 1) 파일 복사
created=()
for name in "${names[@]}"; do
  src="$TEMPLATES_DIR/$name"
  dst="$PROJECT_ROOT/$name"
  if [[ ! -f "$src" ]]; then
    echo "✗ template 없음: $name" >&2
    continue
  fi
  if [[ -e "$dst" ]]; then
    echo "⊙ 건너뜀 (이미 존재): $name"
    continue
  fi
  cp "$src" "$dst"
  echo "✓ scaffolded: $name"
  created+=("$name")
done

# 2) compose.yaml의 required_context.paths에 추가 (옵션)
if [[ $REGISTER -eq 1 && ${#created[@]} -gt 0 && -f "$ACTIVE" ]]; then
  python3 - "$ACTIVE" "${created[@]}" <<'PY'
import sys, yaml

active_path = sys.argv[1]
files = sys.argv[2:]

# 기본 라벨 매핑 (없으면 파일명에서 .md 제거)
labels = {
    "README.md": "프로젝트 정의",
    "SECURITY.md": "보안 정책",
    "DESIGN.md": "디자인 결정",
    "CONVENTIONS.md": "코딩 컨벤션",
}

# paths 항목만 한 줄 flow style ({path: ..., label: ...})로 출력
class FlowDict(dict):
    pass

def _flow_repr(dumper, data):
    return dumper.represent_mapping("tag:yaml.org,2002:map", data, flow_style=True)

yaml.add_representer(FlowDict, _flow_repr, Dumper=yaml.SafeDumper)

with open(active_path, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f) or {}

rc = cfg.setdefault("required_context", {})
paths = rc.setdefault("paths", []) or []
existing = {p.get("path") for p in paths if isinstance(p, dict)}

added = []
for name in files:
    if name in existing:
        continue
    label = labels.get(name, name.replace(".md", ""))
    paths.append({"path": name, "label": label})
    added.append(name)

# 기존 + 신규 항목 모두 FlowDict로 감싸 flow style 보존
rc["paths"] = [FlowDict(p) if isinstance(p, dict) else p for p in paths]

# trigger_read도 동일 패턴이라 같이 보존
tr = cfg.get("trigger_read")
if isinstance(tr, list):
    cfg["trigger_read"] = [FlowDict(t) if isinstance(t, dict) else t for t in tr]

# on_demand_context.paths도 동일
od = cfg.get("on_demand_context")
if isinstance(od, dict):
    od_paths = od.get("paths")
    if isinstance(od_paths, list):
        od["paths"] = [FlowDict(p) if isinstance(p, dict) else p for p in od_paths]

if added:
    with open(active_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"✓ compose.yaml의 required_context.paths에 추가: {', '.join(added)}")
else:
    print("(compose.yaml 갱신 없음 — 이미 등록된 path들)")
PY
fi

echo ""
echo "참고:"
echo "  - 빡빡하게 강제하고 싶으면 compose.yaml에서 해당 path에 'on_deny: hard_stop' 추가"
echo "  - 자동 등록 안 하려면 --no-register 옵션"
