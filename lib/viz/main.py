#!/usr/bin/env python3
"""harness viz — 워크플로우/서브에이전트/병목 시각화.

사용:
    python3 main.py <type> [options]

types:
    workflow    [--live]       워크플로우 다이어그램 (mermaid)
    subagents                  서브에이전트 호출 sequence diagram
    bottleneck                 가장 느린 hook/도구/서브에이전트

options:
    --project-root <path>      .harness/ 위치 (default: $PWD)
    --session <id>             특정 세션 (default: 가장 최근)
    --format <terminal|mermaid|html|json>   default: terminal
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


# -------------------- 데이터 로드 --------------------

def load_session_events(project_root: Path, session_id: str | None = None):
    """세션의 trace 이벤트 로드. (events, session_id, path) 반환."""
    traces_dir = project_root / ".harness" / "runtime" / "traces"
    if not traces_dir.is_dir():
        return [], None, None

    if session_id:
        f = traces_dir / f"{session_id}.jsonl"
        if not f.is_file():
            return [], session_id, None
    else:
        files = sorted(
            traces_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not files:
            return [], None, None
        f = files[0]
        session_id = f.stem

    events = []
    with f.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events, session_id, str(f)


def list_sessions(project_root: Path):
    traces_dir = project_root / ".harness" / "runtime" / "traces"
    if not traces_dir.is_dir():
        return []
    return sorted(
        [(f.stem, f.stat().st_mtime) for f in traces_dir.glob("*.jsonl")],
        key=lambda x: x[1],
        reverse=True,
    )


# -------------------- 워크플로우 viz --------------------

def _read_hook_states(project_root):
    """compose.yaml의 hooks 토글 + plugins 활성화 상태 읽음."""
    if project_root is None:
        return {}, []
    try:
        import yaml
        ap = Path(project_root) / ".harness" / "compose.yaml"
        if not ap.is_file():
            return {}, []
        cfg = yaml.safe_load(ap.read_text(encoding="utf-8")) or {}
        return (cfg.get("hooks") or {}), (cfg.get("plugins") or [])
    except Exception:
        return {}, []


def viz_workflow(events, live: bool, project_root=None) -> dict:
    """workflow 다이어그램. 색·실선/점선·compose.yaml 토글 반영.

    Node id에 'n_' prefix — mermaid 예약어 회피.
    실선(-->) = 정상 흐름, 점선(-.->) = 예외·재시도 흐름.
    disabled hook은 회색·점선 테두리로 표시."""

    hook_states, plugins = _read_hook_states(project_root)
    hooks_plugin_active = "hooks" in plugins  # plugin 자체 비활성이면 모든 hook X

    # hook 이름 → 노드 id
    hook_node_map = {
        "session_start":      "n_ba",
        "user_prompt_submit": "n_guard",
        "pre_tool_use":       "n_gate",
        "post_tool_use":      "n_post",
        "stop":               "n_verify",
    }

    def is_disabled(hook_name):
        if not hooks_plugin_active:
            return True  # plugin 자체 꺼짐 → 모든 hook disabled
        state = hook_states.get(hook_name, "enabled")
        return state == "disabled" or state is False

    disabled_nodes = {nid for hn, nid in hook_node_map.items() if is_disabled(hn)}

    # (id, label, shape, class)
    # class: lifecycle | hook | idle | agent | work | disabled
    base_nodes = [
        ("n_start", "Session Start",                     "circle", "lifecycle"),
        ("n_ba",    "session_start\\nAGENTS.md 주입",    "rect",   "hook"),
        ("n_idle",  "대기",                               "round",  "idle"),
        ("n_guard", "user_prompt_submit\\n가드레일",       "rect",   "hook"),
        ("n_agent", "claude 응답 생성",                   "rect",   "agent"),
        ("n_gate",  "pre_tool_use\\n게이트",              "rect",   "hook"),
        ("n_exec",  "Tool 실행",                          "rect",   "work"),
        ("n_post",  "post_tool_use\\n추적·로깅",          "rect",   "hook"),
        ("n_verify","stop\\n작업 검증",                   "rect",   "hook"),
        ("n_end",   "Session End",                       "circle", "lifecycle"),
    ]
    # disabled 노드는 class를 'disabled'로 + label에 (off) 표시
    nodes = []
    for nid, label, shape, cls in base_nodes:
        if nid in disabled_nodes:
            label = f"{label}\\n(off)"
            cls = "disabled"
        nodes.append((nid, label, shape, cls))
    # (src, dst, label, kind: solid | dashed)
    edges = [
        # 진입
        ("n_start",  "n_ba",     "",                       "solid"),
        ("n_ba",     "n_idle",   "",                       "solid"),
        # Prompt 사이클
        ("n_idle",   "n_guard",  "사용자 prompt",          "solid"),
        ("n_guard",  "n_agent",  "통과",                   "solid"),
        ("n_guard",  "n_idle",   "차단",                   "dashed"),
        # Tool 사이클
        ("n_agent",  "n_gate",   "도구 호출",              "solid"),
        ("n_gate",   "n_exec",   "allow",                  "solid"),
        ("n_exec",   "n_post",   "",                       "solid"),
        ("n_post",   "n_agent",  "",                       "solid"),
        ("n_gate",   "n_agent",  "self_correct",           "dashed"),
        ("n_gate",   "n_verify", "hard_stop",              "dashed"),
        # 응답 종료
        ("n_agent",  "n_verify", "응답 완료",              "solid"),
        ("n_verify", "n_idle",   "verify pass",            "solid"),
        ("n_verify", "n_agent",  "verify fail · 재시도",   "dashed"),
        # 세션 종료
        ("n_idle",   "n_end",    "사용자 종료",            "solid"),
    ]

    # live counts
    counts = Counter()
    if live and events:
        for ev in events:
            t = ev.get("event_type", "")
            if t == "session_start":
                counts["ba"] += 1
            elif t == "tool_use":
                counts["agent"] += 1
                counts["gate"] += 1
                counts["exec"] += 1
                counts["post"] += 1
            elif t == "stop":
                counts["verify"] += 1
            elif t == "user_prompt_submit":
                counts["guard"] += 1

    # mermaid 생성
    shape = {
        "circle": ("([\"", "\"])"),
        "rect":   ("[\"", "\"]"),
        "round":  ("([\"", "\"])"),     # 둥근 모서리 (idle도 circle처럼)
    }
    lines = ["flowchart TD"]
    for nid, label, sh, cls in nodes:
        op, cl = shape[sh]
        count_key = nid[2:] if nid.startswith("n_") else nid
        if live and counts.get(count_key):
            label_full = f"{label}\\n×{counts[count_key]}"
        else:
            label_full = label
        label_full = label_full.replace('"', '\\"')
        lines.append(f"  {nid}{op}{label_full}{cl}:::{cls}")

    for src, dst, lbl, kind in edges:
        arrow = "-->" if kind == "solid" else "-.->"
        if lbl:
            safe = lbl.replace("(", "[").replace(")", "]").replace("|", "／")
            lines.append(f"  {src} {arrow}|{safe}| {dst}")
        else:
            lines.append(f"  {src} {arrow} {dst}")

    # 색 클래스 정의 (역할별 그룹핑)
    lines.extend([
        "  classDef lifecycle fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20",
        "  classDef hook      fill:#e3f2fd,stroke:#1565c0,color:#0d47a1",
        "  classDef idle      fill:#fff3e0,stroke:#e65100,color:#bf360c",
        "  classDef agent     fill:#f3e5f5,stroke:#6a1b9a,color:#4a148c",
        "  classDef work      fill:#fafafa,stroke:#424242,color:#212121",
        "  classDef disabled  fill:#f5f5f5,stroke:#9e9e9e,color:#9e9e9e,stroke-dasharray: 5 5",
    ])

    return {
        "mermaid": "\n".join(lines),
        "counts": dict(counts),
        "live": live,
    }


# -------------------- 서브에이전트 viz --------------------

def viz_subagents(events) -> dict:
    """Task 도구 호출 = 서브에이전트. sequence diagram."""
    calls = []
    for ev in events:
        if ev.get("event_type") == "tool_use" and ev.get("name") == "Task":
            calls.append({
                "ts": ev.get("ts", ""),
                "duration_ms": ev.get("duration_ms", 0),
                "subagent_type": (ev.get("metadata") or {}).get("subagent_type", "?"),
                "description": (ev.get("metadata") or {}).get("description", "?"),
            })

    # mermaid sequence
    if not calls:
        mermaid = "sequenceDiagram\n  Main->>Main: (서브에이전트 호출 없음)"
    else:
        lines = ["sequenceDiagram", "  participant Main"]
        for c in calls:
            sa = c["subagent_type"]
            desc = (c["description"][:50] or "...")
            ms = c["duration_ms"]
            lines.append(f"  Main->>{sa}: {desc}")
            lines.append(f"  {sa}-->>Main: ({ms}ms)")
        mermaid = "\n".join(lines)

    return {"mermaid": mermaid, "calls": calls}


# -------------------- 병목 viz --------------------

def viz_eval(project_root) -> dict:
    """eval-results를 추이로 표시. mermaid + 테이블 데이터."""
    rd = project_root / ".harness" / "runtime" / "eval-results"
    if not rd.is_dir():
        return {"mermaid": "", "runs": [], "no_data": True}
    files = sorted(rd.glob("*.json"))
    runs = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            s = data.get("summary", {})
            runs.append({
                "ts": data.get("ts", "")[:19],
                "passed": s.get("passed", 0),
                "failed": s.get("failed", 0),
                "skipped": s.get("skipped", 0),
                "total": s.get("total", 0),
                "results": data.get("results", []),
            })
        except Exception:
            continue

    # Mermaid: 통과율 추이 시각화 (간단한 이벤트 시퀀스 다이어그램으로 표현 어려움 → table만)
    # Mermaid의 line chart는 v10+ 지원하지만 호환 위해 안 씀
    # 대신 간단한 flowchart로 최근 5회 추이 표시
    recent = runs[-5:]
    if recent:
        lines = ["flowchart LR"]
        prev = None
        for i, r in enumerate(recent):
            rate = (r["passed"] / r["total"] * 100) if r["total"] else 0
            label = f"{r['ts'][5:16]}\\n{r['passed']}/{r['total']} ({rate:.0f}%)"
            color_class = "pass" if r["failed"] == 0 else "fail"
            nid = f"r{i}"
            lines.append(f'  {nid}["{label}"]:::{color_class}')
            if prev:
                lines.append(f"  {prev} --> {nid}")
            prev = nid
        lines.append("  classDef pass fill:#d4edda,stroke:#155724")
        lines.append("  classDef fail fill:#f8d7da,stroke:#721c24")
        mermaid = "\n".join(lines)
    else:
        mermaid = "flowchart LR\n  empty[\"(eval 결과 없음)\"]"

    # Regression 감지
    regressions = []
    for i in range(1, len(runs)):
        prev_passed = {x["id"] for x in runs[i-1]["results"] if x.get("passed")}
        curr_failed = {x["id"] for x in runs[i]["results"] if not x.get("passed") and not x.get("skipped")}
        new_fails = prev_passed & curr_failed
        if new_fails:
            regressions.append({"between": [runs[i-1]["ts"], runs[i]["ts"]], "newly_failing": list(new_fails)})

    return {
        "mermaid": mermaid,
        "runs": runs[-10:],  # 최근 10개
        "regressions": regressions,
    }


def viz_prompts(project_root) -> dict:
    """prompt 헤맴 추적. lib/prompts/main.py 재사용."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "prompts"))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("prompts_main", str(Path(__file__).parent.parent / "prompts" / "main.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rows = mod.collect(project_root)
        # _ts 같은 datetime 제거
        clean = []
        for r in rows:
            clean.append({k: v for k, v in r.items() if not k.startswith("_")})
        return {"mermaid": "", "rows": clean}
    except Exception as e:
        return {"mermaid": "", "error": str(e)}


def viz_improve(project_root) -> dict:
    """improve 분석 결과 그대로 반환. mermaid는 빈 값 (텍스트 위주)."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "improve"))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("improve_main", str(Path(__file__).parent.parent / "improve" / "main.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        active = mod.load_active(project_root) or {}
        decisions = mod.load_decisions(project_root, None)
        traces = mod.load_traces(project_root, None)
        eval_results = mod.load_eval_results(project_root)
        dec = mod.analyze_decisions(decisions)
        trc = mod.analyze_traces(traces)
        ev = mod.analyze_eval(eval_results)
        sugs = mod.suggest(active, dec, trc, ev)
        return {
            "mermaid": "",
            "summary": {
                "decisions": dec,
                "traces": trc,
                "eval": ev,
            },
            "suggestions": sugs,
        }
    except Exception as e:
        return {"mermaid": "", "error": str(e)}


def viz_bottleneck(events) -> dict:
    """가장 느린 이벤트 정렬."""
    by_name = defaultdict(lambda: {"count": 0, "total_ms": 0, "max_ms": 0})
    for ev in events:
        if ev.get("event_type") != "tool_use":
            continue
        name = ev.get("name", "?")
        d = ev.get("duration_ms", 0)
        if not isinstance(d, (int, float)):
            continue
        b = by_name[name]
        b["count"] += 1
        b["total_ms"] += int(d)
        if d > b["max_ms"]:
            b["max_ms"] = int(d)

    rows = []
    for name, b in by_name.items():
        avg = b["total_ms"] // b["count"] if b["count"] else 0
        rows.append({
            "name": name,
            "calls": b["count"],
            "total_ms": b["total_ms"],
            "avg_ms": avg,
            "max_ms": b["max_ms"],
        })
    rows.sort(key=lambda r: r["total_ms"], reverse=True)
    return {"rows": rows}


# -------------------- 출력 포맷터 --------------------

def render_terminal(viz_type, data, session_id):
    out = []
    out.append(f"=== harness viz: {viz_type} (session: {session_id or 'N/A'}) ===\n")

    if viz_type == "workflow":
        out.append(data["mermaid"])
        if data.get("live"):
            out.append("\n\n[Live counts]")
            for k, v in data["counts"].items():
                out.append(f"  {k}: {v}")

    elif viz_type == "subagents":
        out.append(data["mermaid"])
        if data["calls"]:
            out.append(f"\n\nTotal: {len(data['calls'])} subagent invocations")
        else:
            out.append("\n\n(no subagent calls in trace)")

    elif viz_type == "bottleneck":
        rows = data["rows"]
        if not rows:
            out.append("(no tool_use events in trace)")
        else:
            out.append(f"{'tool':<20} {'calls':>6} {'total ms':>10} {'avg ms':>8} {'max ms':>8}")
            out.append("-" * 60)
            for r in rows:
                out.append(
                    f"{r['name']:<20} {r['calls']:>6} {r['total_ms']:>10} {r['avg_ms']:>8} {r['max_ms']:>8}"
                )

    elif viz_type == "eval":
        if data.get("no_data"):
            out.append("(eval 결과 없음)")
        else:
            if data.get("regressions"):
                out.append("⚠ Regression 감지:")
                for r in data["regressions"]:
                    out.append(f"  {r['between'][0][:19]} → {r['between'][1][:19]}: {', '.join(r['newly_failing'])}")
                out.append("")
            out.append(f"{'timestamp':<22} {'passed':>7} {'failed':>7} {'total':>6}")
            out.append("-" * 50)
            for r in data.get("runs", []):
                out.append(f"{r['ts']:<22} {r['passed']:>7} {r['failed']:>7} {r['total']:>6}")

    elif viz_type == "improve":
        if data.get("error"):
            out.append(f"분석 실패: {data['error']}")
        else:
            sugs = data.get("suggestions", [])
            if not sugs:
                out.append("✓ 특이 권고 없음")
            else:
                for i, s in enumerate(sugs, 1):
                    out.append(f"{i}. {s['title']}")
                    out.append(f"   근거: {s['evidence']}")
                    out.append(f"   권장: {s['recommend']}")

    elif viz_type == "prompts":
        if data.get("error"):
            out.append(f"분석 실패: {data['error']}")
        else:
            rows = data.get("rows", [])
            if not rows:
                out.append("(prompt 데이터 없음 — user_prompt_submit hook이 fire한 후 쌓임)")
            else:
                out.append(f"{'ts':<20} {'struggle':>8} {'judge':>5} {'tool':>5} {'deny':>5} {'retry':>5} {'bypass':>6} {'dur(s)':>7}  prompt")
                out.append("-" * 120)
                for r in sorted(rows, key=lambda x: -x.get("struggle_score", 0))[:20]:
                    p = (r.get("prompt", "") or "")[:50].replace("\n", " ")
                    j = r.get("judge_score")
                    j_str = f"{j:.0f}" if isinstance(j, (int, float)) else "-"
                    out.append(
                        f"{r.get('ts','')[:19]:<20} "
                        f"{r.get('struggle_score',0):>8} {j_str:>5} "
                        f"{r.get('tool_calls',0):>5} {r.get('denies',0):>5} {r.get('retries',0):>5} "
                        f"{r.get('bypass',0):>6} {r.get('duration_s',0):>7}  "
                        f"{p}"
                    )

    return "\n".join(out)


def render_mermaid(viz_type, data):
    return data.get("mermaid", "")


def render_json(viz_type, data, session_id):
    return json.dumps(
        {"viz_type": viz_type, "session_id": session_id, "data": data},
        ensure_ascii=False,
        indent=2,
    )


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>harness viz — {viz_type}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <style>
    body {{ font-family: -apple-system, Helvetica, sans-serif; max-width: 900px; margin: 2em auto; padding: 0 1em; color: #222; }}
    h1 {{ border-bottom: 2px solid #eee; padding-bottom: 0.3em; }}
    .meta {{ color: #777; font-size: 0.9em; margin-bottom: 1em; }}
    pre.mermaid {{ background: #fafafa; padding: 1em; border-radius: 6px; border: 1px solid #eee; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1em; }}
    th, td {{ border: 1px solid #e0e0e0; padding: 0.5em; text-align: left; }}
    th {{ background: #f4f4f4; }}
    td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  </style>
</head>
<body>
  <h1>harness viz — {viz_type}</h1>
  <div class="meta">session: {session_id} · generated: {ts}</div>
  <pre class="mermaid">{mermaid}</pre>
  {extra}
  <script>mermaid.initialize({{ startOnLoad: true, theme: 'default' }});</script>
</body>
</html>
"""


def render_html(viz_type, data, session_id):
    extra = ""
    if viz_type == "bottleneck":
        rows = data["rows"]
        if rows:
            tr = "".join(
                f"<tr><td>{r['name']}</td><td class='num'>{r['calls']}</td>"
                f"<td class='num'>{r['total_ms']}</td><td class='num'>{r['avg_ms']}</td>"
                f"<td class='num'>{r['max_ms']}</td></tr>"
                for r in rows
            )
            extra = (
                "<table><thead><tr><th>tool</th><th>calls</th>"
                "<th>total ms</th><th>avg ms</th><th>max ms</th></tr></thead>"
                f"<tbody>{tr}</tbody></table>"
            )
    elif viz_type == "subagents" and data.get("calls"):
        tr = "".join(
            f"<tr><td>{c['ts']}</td><td>{c['subagent_type']}</td>"
            f"<td>{c['description']}</td><td class='num'>{c['duration_ms']}</td></tr>"
            for c in data["calls"]
        )
        extra = (
            "<table><thead><tr><th>ts</th><th>subagent</th>"
            "<th>description</th><th>duration ms</th></tr></thead>"
            f"<tbody>{tr}</tbody></table>"
        )

    return HTML_TEMPLATE.format(
        viz_type=viz_type,
        session_id=session_id or "N/A",
        ts=datetime.utcnow().isoformat() + "Z",
        mermaid=data.get("mermaid", ""),
        extra=extra,
    )


# -------------------- main --------------------

def main():
    parser = argparse.ArgumentParser(prog="harness viz", description=__doc__)
    parser.add_argument("type", choices=["workflow", "subagents", "bottleneck", "eval", "improve", "prompts"])
    parser.add_argument("--live", action="store_true", help="(workflow only) trace 기반 통계 포함")
    parser.add_argument("--project-root", default=os.getcwd())
    parser.add_argument("--session", default=None, help="세션 ID. default: 가장 최근")
    parser.add_argument("--format", choices=["terminal", "mermaid", "html", "json"], default="terminal")
    parser.add_argument("--no-open", action="store_true", help="HTML 출력 시 브라우저 자동 안 열기")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    events, session_id, _ = load_session_events(project_root, args.session)

    if args.type == "workflow":
        data = viz_workflow(events, live=args.live, project_root=project_root)
    elif args.type == "subagents":
        data = viz_subagents(events)
    elif args.type == "bottleneck":
        data = viz_bottleneck(events)
    elif args.type == "eval":
        data = viz_eval(project_root)
    elif args.type == "improve":
        data = viz_improve(project_root)
    elif args.type == "prompts":
        data = viz_prompts(project_root)
    else:
        sys.exit(1)

    if args.format == "terminal":
        print(render_terminal(args.type, data, session_id))
    elif args.format == "mermaid":
        print(render_mermaid(args.type, data))
    elif args.format == "json":
        print(render_json(args.type, data, session_id))
    elif args.format == "html":
        html = render_html(args.type, data, session_id)
        viz_dir = project_root / ".harness" / "runtime" / "viz"
        viz_dir.mkdir(parents=True, exist_ok=True)
        out_path = viz_dir / f"{args.type}-{datetime.now().strftime('%Y%m%dT%H%M%S')}.html"
        out_path.write_text(html, encoding="utf-8")
        print(f"✓ {out_path}")
        if not args.no_open:
            webbrowser.open(out_path.as_uri())


if __name__ == "__main__":
    main()
