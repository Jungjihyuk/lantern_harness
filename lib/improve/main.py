#!/usr/bin/env python3
"""harness improve — 사용 패턴 분석 + 룰 기반 compose.yaml 조정 제안.

Level 1 (Reporting) + Level 2 (Suggest)만 구현. Level 3 (auto-apply)는 의도적 미구현 — 안전.

사용:
    python3 main.py [--project-root <path>] [--days N] [--format text|json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("Error: PyYAML 필요. pip3 install pyyaml\n")
    sys.exit(1)


# -------------------- 데이터 로드 --------------------

def load_decisions(project_root: Path, since_ts: datetime | None):
    """모든 세션의 decisions.jsonl을 평탄화."""
    sessions_dir = project_root / ".harness" / "runtime" / "sessions"
    if not sessions_dir.is_dir():
        return []
    out = []
    for sd in sessions_dir.iterdir():
        f = sd / "decisions.jsonl"
        if not f.is_file():
            continue
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if since_ts:
                    try:
                        ts = datetime.fromisoformat(d.get("ts", "").replace("Z", "+00:00"))
                        if ts < since_ts:
                            continue
                    except Exception:
                        pass
                d["session_id"] = sd.name
                out.append(d)
    return out


def load_traces(project_root: Path, since_ts: datetime | None):
    traces_dir = project_root / ".harness" / "runtime" / "traces"
    if not traces_dir.is_dir():
        return []
    out = []
    for f in traces_dir.glob("*.jsonl"):
        if since_ts and datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc) < since_ts:
            continue
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def load_eval_results(project_root: Path, last_n: int = 10):
    rd = project_root / ".harness" / "runtime" / "eval-results"
    if not rd.is_dir():
        return []
    files = sorted(rd.glob("*.json"))
    out = []
    for f in files[-last_n:]:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def load_active(project_root: Path):
    p = project_root / ".harness" / "compose.yaml"
    if not p.is_file():
        return None
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


# -------------------- 분석 --------------------

def analyze_decisions(decisions):
    summary = Counter()
    by_category = Counter()
    bypass_count = 0
    deny_by_path: Counter[str] = Counter()
    sessions = set()
    for d in decisions:
        sessions.add(d.get("session_id", "?"))
        summary[d.get("decision", "?")] += 1
        cat = d.get("reason_category", "none")
        if cat != "none":
            by_category[cat] += 1
        ext = d.get("extra") or {}
        if isinstance(ext, dict):
            if ext.get("bypass"):
                bypass_count += 1
            unread = ext.get("unread")
            if unread:
                for p in unread.split(", "):
                    p = p.strip()
                    if p:
                        deny_by_path[p] += 1
            f = ext.get("file")
            if f:
                deny_by_path[f] += 1
    return {
        "total_decisions": len(decisions),
        "summary": dict(summary),
        "by_category": dict(by_category),
        "bypass_count": bypass_count,
        "deny_by_path": dict(deny_by_path.most_common(10)),
        "sessions": len(sessions),
    }


def analyze_traces(traces):
    tools = Counter()
    durations = defaultdict(list)
    sessions = set()
    for ev in traces:
        if ev.get("event_type") != "tool_use":
            continue
        sessions.add(ev.get("session_id", "?"))
        n = ev.get("name", "?")
        tools[n] += 1
        d = ev.get("duration_ms", 0)
        if isinstance(d, (int, float)) and d > 0:
            durations[n].append(int(d))
    return {
        "tool_calls": dict(tools),
        "tool_avg_ms": {k: int(sum(v) / len(v)) for k, v in durations.items() if v},
        "sessions": len(sessions),
    }


def analyze_eval(results):
    if not results:
        return {"runs": 0}
    last = results[-1].get("summary", {})
    pass_rates = []
    for r in results:
        s = r.get("summary", {})
        total = s.get("total", 0)
        if total:
            pass_rates.append(s.get("passed", 0) / total)
    regressions = []
    for i in range(1, len(results)):
        prev_passed = {x["id"] for x in results[i-1].get("results", []) if x.get("passed")}
        curr_failed = {x["id"] for x in results[i].get("results", []) if not x.get("passed") and not x.get("skipped")}
        new_fails = prev_passed & curr_failed
        if new_fails:
            regressions.append({"between": [results[i-1]["ts"], results[i]["ts"]], "newly_failing": list(new_fails)})
    return {
        "runs": len(results),
        "last_summary": last,
        "pass_rate_recent": pass_rates[-5:] if pass_rates else [],
        "regressions": regressions,
    }


# -------------------- 룰 기반 제안 --------------------

def suggest(active: dict, dec: dict, trc: dict, ev: dict):
    suggestions = []

    cg = (active.get("cognitive_guard") or {})
    per_call = (cg.get("per_call") or {})
    cur_max_diff = per_call.get("max_diff_lines", 200)

    by_cat = dec.get("by_category", {})
    bypass = dec.get("bypass_count", 0)

    # Rule 1: cognitive_per_call deny + bypass 빈도 high → 임계값 너무 낮음 가능성
    deny_pc = by_cat.get("cognitive_per_call", 0)
    if deny_pc >= 3 and bypass >= 2:
        suggestions.append({
            "title": f"cognitive_guard.per_call.max_diff_lines (현재 {cur_max_diff})",
            "evidence": f"deny {deny_pc}회 + bypass {bypass}회 → 임계값이 너의 평소 변경 크기에 비해 빡빡함",
            "recommend": f"{int(cur_max_diff * 1.5)}~{int(cur_max_diff * 2)}로 상향 검토",
            "yaml_path": "cognitive_guard.per_call.max_diff_lines",
        })

    # Rule 2: loop_detection 자주 trigger + bypass 자주
    deny_loop = by_cat.get("loop_detection", 0)
    if deny_loop >= 3:
        ld = active.get("loop_detection") or {}
        cur = ld.get("consecutive_same_path", 3)
        suggestions.append({
            "title": f"loop_detection.consecutive_same_path (현재 {cur})",
            "evidence": f"loop_detection 발동 {deny_loop}회 — false positive 의심",
            "recommend": f"{cur+2} 이상으로 상향 검토",
            "yaml_path": "loop_detection.consecutive_same_path",
        })

    # Rule 3: 같은 path가 deny 자주 발생 → prefix 직접 박을지 검토
    deny_paths = dec.get("deny_by_path", {})
    for p, cnt in deny_paths.items():
        if cnt >= 3:
            suggestions.append({
                "title": f"Required Context '{p}' 빈번 deny ({cnt}회)",
                "evidence": "매번 Read 후 진행 — 컨텍스트 자주 압축돼 사라지는 가능성",
                "recommend": "이 path의 핵심 내용을 AGENTS.md(prefix)에 직접 인용 검토 또는 know-how/AGENTS.md로 override",
                "yaml_path": "(수동 — AGENTS.md 또는 know-how)",
            })

    # Rule 4: required_unread deny 절대 수치 기반 — Required 너무 많음 의심
    deny_req = by_cat.get("required_unread", 0)
    rc_paths = (active.get("required_context") or {}).get("paths") or []
    if len(rc_paths) >= 5 and deny_req >= 5:
        suggestions.append({
            "title": f"Required Context 너무 많음 (현재 {len(rc_paths)}개)",
            "evidence": f"deny {deny_req}회 — 매 작업마다 다 읽는 부담",
            "recommend": "정말 매번 필요한 것만 Required로, 나머지는 on_demand_context로 이동",
            "yaml_path": "required_context.paths",
        })

    # Rule 5: Eval regression 감지
    regs = ev.get("regressions", [])
    for r in regs[-3:]:
        suggestions.append({
            "title": f"Eval regression 감지: {', '.join(r['newly_failing'])}",
            "evidence": f"이전 통과했던 케이스가 {r['between'][1][:19]}부터 실패",
            "recommend": "최근 hook·compose.yaml 변경 검토. 'harness eval run <case-id>'로 디버깅",
            "yaml_path": "(N/A)",
        })

    return suggestions


# -------------------- 출력 --------------------

def render_text(report: dict):
    lines = []
    lines.append("=== harness improve 분석 ===\n")

    lines.append("📊 사용 패턴")
    dec = report["decisions"]
    trc = report["traces"]
    lines.append(f"  - 분석 세션: {dec.get('sessions', 0)} (decisions) / {trc.get('sessions', 0)} (traces)")
    lines.append(f"  - 총 결정: {dec.get('total_decisions', 0)}")
    sm = dec.get("summary", {})
    lines.append(f"  - allow: {sm.get('allow', 0)}, deny_self_correct: {sm.get('deny_self_correct', 0)}, deny_hard_stop: {sm.get('deny_hard_stop', 0)}")
    lines.append(f"  - bypass marker 사용: {dec.get('bypass_count', 0)}회")
    lines.append(f"  - deny 카테고리별: {dec.get('by_category', {})}")
    if dec.get("deny_by_path"):
        lines.append(f"  - 자주 deny된 path: {dec['deny_by_path']}")
    lines.append("")

    if trc.get("tool_calls"):
        lines.append("🛠  도구 사용 (총 호출)")
        for k, v in sorted(trc["tool_calls"].items(), key=lambda x: -x[1])[:10]:
            avg = trc.get("tool_avg_ms", {}).get(k, 0)
            lines.append(f"  - {k:<15s} {v:>4d}회  avg {avg}ms")
        lines.append("")

    ev = report["eval"]
    if ev.get("runs"):
        lines.append("📈 Eval 추이")
        ls = ev.get("last_summary", {})
        lines.append(f"  - 최근 결과: {ls.get('passed',0)} passed, {ls.get('failed',0)} failed, {ls.get('skipped',0)} skipped")
        if ev.get("pass_rate_recent"):
            rates = " → ".join(f"{r*100:.0f}%" for r in ev["pass_rate_recent"])
            lines.append(f"  - 최근 5회 통과율: {rates}")
        if ev.get("regressions"):
            lines.append(f"  - regression 감지: {len(ev['regressions'])}건")
        lines.append("")

    sugs = report["suggestions"]
    if sugs:
        lines.append("⚠ 잠재 개선 제안")
        for i, s in enumerate(sugs, 1):
            lines.append(f"\n{i}. {s['title']}")
            lines.append(f"   근거: {s['evidence']}")
            lines.append(f"   권장: {s['recommend']}")
            if s.get("yaml_path"):
                lines.append(f"   위치: {s['yaml_path']}")
    else:
        lines.append("✓ 특이 권고 없음 (데이터 부족 또는 모든 임계값 적정)")

    lines.append("")
    lines.append("ℹ️  자동 적용은 의도적으로 미구현. compose.yaml을 직접 편집하세요.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(prog="harness improve")
    parser.add_argument("--project-root", default=os.getcwd())
    parser.add_argument("--days", type=int, default=7, help="분석 범위 (일수). 0이면 전체.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    since = None
    if args.days > 0:
        since = datetime.now(timezone.utc) - timedelta(days=args.days)

    active = load_active(project_root) or {}
    decisions = load_decisions(project_root, since)
    traces = load_traces(project_root, since)
    eval_results = load_eval_results(project_root)

    dec = analyze_decisions(decisions)
    trc = analyze_traces(traces)
    ev = analyze_eval(eval_results)

    sugs = suggest(active, dec, trc, ev)

    report = {
        "project_root": str(project_root),
        "analyzed_since": since.isoformat() if since else "all-time",
        "decisions": dec,
        "traces": trc,
        "eval": ev,
        "suggestions": sugs,
    }

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))


if __name__ == "__main__":
    main()
