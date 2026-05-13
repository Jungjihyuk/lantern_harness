#!/bin/bash
# harness scaffold <name>... — standard/instructions/templates/ 의 빈 문서를 프로젝트 루트로 복사.
#
# 각 template 은 artifact 구조 — standard/instructions/templates/<name>/manifest.yaml + .md
# scaffold 는 .md 본문만 프로젝트 루트에 복사하고, compose.yaml 의 cognition.context.required
# 에 새 entry 자동 등록 (--no-register 로 비활성화).
#
# 옵션:
#   --all                 모든 template 복사
#   --no-register         compose.yaml 자동 갱신 안 함

set -euo pipefail

HARNESS_HOME="$HOME/.harness"
TEMPLATES_DIR="$HARNESS_HOME/standard/instructions/templates"

# dev repo fallback
if [[ ! -d "$TEMPLATES_DIR" ]]; then
  DEV_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
  if [[ -d "$DEV_ROOT/standard/instructions/templates" ]]; then
    TEMPLATES_DIR="$DEV_ROOT/standard/instructions/templates"
  fi
fi

PROJECT_ROOT="$(pwd)"
COMPOSE="$PROJECT_ROOT/.harness/compose.yaml"

if [[ ! -d "$TEMPLATES_DIR" ]]; then
  echo "Error: templates 디렉토리 없음 ($TEMPLATES_DIR)" >&2
  exit 1
fi

# template 폴더 (이름 = sub-folder basename) 목록
all_template_names() {
  for d in "$TEMPLATES_DIR"/*/; do
    [[ -d "$d" ]] || continue
    basename "$d"
  done
}

REGISTER=1
names=()
for arg in "$@"; do
  case "$arg" in
    --no-register) REGISTER=0 ;;
    --all)
      while IFS= read -r n; do names+=("$n"); done < <(all_template_names)
      ;;
    -h|--help|"") ;;
    *) names+=("$arg") ;;
  esac
done

if [[ ${#names[@]} -eq 0 ]]; then
  echo "Usage: harness scaffold <name>... | --all  [--no-register]"
  echo ""
  echo "Available templates:"
  while IFS= read -r n; do
    # entry 파일명 추정 — manifest 의 entry 값
    entry="$(grep -E '^entry:' "$TEMPLATES_DIR/$n/manifest.yaml" 2>/dev/null | sed -E 's/^entry: *\.\///; s/^entry: *//' | tr -d '"' | tr -d "'")"
    [[ -z "$entry" ]] && entry="(unknown)"
    if [[ -e "$PROJECT_ROOT/$entry" ]]; then
      echo "  - $n  →  $entry  [exists in project]"
    else
      echo "  - $n  →  $entry"
    fi
  done < <(all_template_names)
  exit 0
fi

# 1) entry .md 본문을 프로젝트 루트로 복사
declare -a copied_pairs   # "<name>|<basename>" 페어
for name in "${names[@]}"; do
  manifest="$TEMPLATES_DIR/$name/manifest.yaml"
  if [[ ! -f "$manifest" ]]; then
    echo "✗ template 없음: $name" >&2
    continue
  fi

  # entry 파일명 (예: ./README.md → README.md)
  entry="$(grep -E '^entry:' "$manifest" | sed -E 's/^entry: *\.\///; s/^entry: *//' | tr -d '"' | tr -d "'")"
  if [[ -z "$entry" ]]; then
    echo "✗ $name: manifest 의 entry 필드 비어있음" >&2
    continue
  fi

  src="$TEMPLATES_DIR/$name/$entry"
  dst="$PROJECT_ROOT/$entry"

  if [[ ! -f "$src" ]]; then
    echo "✗ template 본문 없음: $src" >&2
    continue
  fi

  if [[ -e "$dst" ]]; then
    echo "⊙ 건너뜀 (이미 존재): $entry"
    continue
  fi

  cp "$src" "$dst"
  echo "✓ scaffolded: $entry"
  copied_pairs+=("$name|$entry")
done

# 2) compose.yaml 의 cognition.context.required 에 entry 자동 등록
if [[ $REGISTER -eq 1 && ${#copied_pairs[@]} -gt 0 && -f "$COMPOSE" ]]; then
  python3 - "$COMPOSE" "${copied_pairs[@]}" <<'PY'
import sys, yaml

compose_path = sys.argv[1]
pairs = sys.argv[2:]  # "<name>|<entry>"

# template name → (id, label) 기본 매핑
defaults = {
    "readme":      ("project_readme",      "프로젝트 정의"),
    "design":      ("project_design",      "디자인 결정"),
    "conventions": ("project_conventions", "코딩 컨벤션"),
    "security":    ("project_security",    "보안 정책"),
}

class FlowDict(dict):
    pass

def _flow_repr(dumper, data):
    return dumper.represent_mapping("tag:yaml.org,2002:map", data, flow_style=True)

yaml.add_representer(FlowDict, _flow_repr, Dumper=yaml.SafeDumper)

with open(compose_path, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f) or {}

cog = cfg.setdefault("cognition", {})
ctx = cog.setdefault("context", {})
required = ctx.get("required") or []

# 기존 entry 의 src_path 또는 id set
existing_paths = {e.get("src_path") for e in required if isinstance(e, dict)}
existing_ids = {e.get("id") for e in required if isinstance(e, dict)}

added = []
for pair in pairs:
    name, entry = pair.split("|", 1)
    eid, label = defaults.get(name, (f"project_{name}", name))
    if entry in existing_paths or eid in existing_ids:
        continue
    required.append({"id": eid, "src_path": entry, "label": label})
    added.append(entry)

# flow style 보존
ctx["required"] = [FlowDict(e) if isinstance(e, dict) else e for e in required]

if added:
    with open(compose_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"✓ compose.yaml cognition.context.required 에 추가: {', '.join(added)}")
else:
    print("(compose.yaml 갱신 없음 — 이미 등록된 entry)")
PY
fi

echo ""
echo "참고:"
echo "  - 강제력은 cognition.context.required entry 에 on_deny: hard_stop 추가 (기본은 self_correct)"
echo "  - 자동 등록 끄려면 --no-register"
