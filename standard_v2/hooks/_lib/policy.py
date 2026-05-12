#!/usr/bin/env python3
"""policy.py — compose.yaml로부터 정책 데이터 추출 및 AGENTS.md 생성.

compose.yaml이 SSOT (Single Source of Truth).
AGENTS.md는 derived artifact — 매 세션 시작 시 자동 생성.

사용:
    python3 policy.py generate-agents-md <compose.yaml>           # AGENTS.md 본문 stdout 출력
    python3 policy.py init-status <compose.yaml>                  # required-status.json (객체) stdout 출력
    python3 policy.py default-on-deny <compose.yaml>              # 기본 정책값 출력
"""
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write(
        "Error: PyYAML 필요. 설치:  pip3 install pyyaml\n"
        "또는 시스템 패키지 매니저 사용.\n"
    )
    sys.exit(1)


def load_active(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def generate_agents_md(active):
    """compose.yaml로부터 AGENTS.md 본문 생성. severity tag 없음 (LLM은 모름)."""
    rc = active.get("required_context", {}) or {}
    od = active.get("on_demand_context", {}) or {}
    tr = active.get("trigger_read", []) or []
    hr = active.get("hard_rules", []) or []

    lines = [
        "# AGENTS.md",
        "",
        "> 작업 시작 전 Required Context를 모두 읽으세요.",
        "> Required를 읽지 않은 채 코드 변경 금지 (hook이 강제).",
        "",
        "## Required Context",
    ]
    paths = (rc.get("paths") or [])
    if paths:
        for item in paths:
            label = item.get("label", "")
            path = item.get("path", "")
            if label:
                lines.append(f"- {label}: {path}")
            else:
                lines.append(f"- {path}")
    else:
        lines.append("<!-- 비어있음 — compose.yaml의 required_context.paths 채우기 -->")

    lines += ["", "## On-Demand Context"]
    od_paths = (od.get("paths") or [])
    if od_paths:
        for item in od_paths:
            label = item.get("label", "")
            path = item.get("path", "")
            if label:
                lines.append(f"- {label}: {path}")
            else:
                lines.append(f"- {path}")
    else:
        lines.append("<!-- 비어있음 -->")

    lines += ["", "## Trigger → Read"]
    if tr:
        for rule in tr:
            cond = rule.get("condition", "")
            req = rule.get("require", "")
            lines.append(f"- {cond} → {req} 먼저")
    else:
        lines.append("<!-- 비어있음 -->")

    lines += ["", "## Hard Rules"]
    if hr:
        for i, r in enumerate(hr, 1):
            lines.append(f"{i}. {r}")
    else:
        lines += [
            "1. Required Context를 읽지 않은 채 코드 변경 금지",
            "2. Trigger 매칭 시 해당 문서를 먼저 읽고 작업",
        ]

    return "\n".join(lines) + "\n"


def init_status(active):
    """required-status.json 초기 객체 생성.
    {path: {status: unread, on_deny: <self_correct|hard_stop>}}"""
    rc = active.get("required_context", {}) or {}
    default = rc.get("default_on_deny", "self_correct")
    paths = (rc.get("paths") or [])
    out = {}
    for item in paths:
        p = item.get("path")
        if not p:
            continue
        on_deny = item.get("on_deny", default)
        out[p] = {"status": "unread", "on_deny": on_deny}
    return out


def match_triggers(active, file_path: str):
    """compose.yaml의 trigger_read 룰들 중 file_path와 매칭하는 것 반환.
    Glob 규칙:
      - `*` = 임의 문자(/ 제외)
      - `**` = 임의 path (/ 포함, root-level도 매칭)
      - `?` = 임의 한 글자
    """
    import re

    rules = active.get("trigger_read", []) or []
    matches = []
    norm_path = file_path.replace("\\", "/")
    if norm_path.startswith("./"):
        norm_path = norm_path[2:]
    for r in rules:
        if not isinstance(r, dict):
            continue
        pat = r.get("match_path", "")
        req = r.get("require", "")
        on_deny = r.get("on_deny", "self_correct")
        if not pat or not req:
            continue

        # `**` 를 sentinel로 보존 후 정규식 변환
        regex = re.escape(pat)
        # \\*\\* → DEEPSTAR_TOKEN
        regex = regex.replace(r"\*\*", "__DEEPSTAR__")
        regex = regex.replace(r"\*", "[^/]*")
        regex = regex.replace(r"\?", "[^/]")
        # __DEEPSTAR__/ → (?:.*/)?  (optional 디렉토리 포함)
        regex = regex.replace("__DEEPSTAR__/", "(?:.*/)?")
        # 남은 단독 __DEEPSTAR__ → .*
        regex = regex.replace("__DEEPSTAR__", ".*")

        if re.fullmatch(regex, norm_path):
            matches.append({"require": req, "on_deny": on_deny})
    return matches


def main():
    if len(sys.argv) < 3:
        sys.stderr.write(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    active_path = sys.argv[2]
    if not Path(active_path).is_file():
        sys.stderr.write(f"Error: not a file: {active_path}\n")
        sys.exit(1)
    active = load_active(active_path)

    if cmd == "generate-agents-md":
        sys.stdout.write(generate_agents_md(active))
    elif cmd == "init-status":
        json.dump(init_status(active), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    elif cmd == "default-on-deny":
        rc = active.get("required_context", {}) or {}
        sys.stdout.write(rc.get("default_on_deny", "self_correct"))
    elif cmd == "match-triggers":
        # 추가 인자: file_path
        if len(sys.argv) < 4:
            sys.stderr.write("Usage: policy.py match-triggers <compose.yaml> <file_path>\n")
            sys.exit(1)
        file_path = sys.argv[3]
        json.dump(match_triggers(active, file_path), sys.stdout, ensure_ascii=False)
    else:
        sys.stderr.write(f"Unknown command: {cmd}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
