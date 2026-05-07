#!/usr/bin/env python3
"""prompt 헤맴 추적 — UserPromptSubmit 후 발생한 활동을 묶어 점수화.

데이터:
- runtime/sessions/<id>/prompts.jsonl    (user_prompt_submit hook이 기록)
- runtime/sessions/<id>/decisions.jsonl  (pre_tool_use hook이 기록)
- runtime/traces/<id>.jsonl              (post_tool_use·stop hook이 기록)

연결 방법:
- 시간 윈도우. prompt P (ts=t1), 다음 prompt P' (ts=t2). [t1, t2) 사이 이벤트가 P 소속.

점수:
  struggle_score = denies × 2 + retries × 3 + duration_s/10 + bypass × 1

사용:
    python3 main.py [--project-root <path>] [--limit N] [--format text|json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def parse_ts(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def load_session_prompts(session_dir: Path):
    f = session_dir / "prompts.jsonl"
    if not f.is_file():
        return []
    out = []
    with f.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                d["_ts"] = parse_ts(d.get("ts", ""))
                out.append(d)
            except json.JSONDecodeError:
                continue
    return [d for d in out if d.get("_ts")]


def load_session_decisions(session_dir: Path):
    f = session_dir / "decisions.jsonl"
    if not f.is_file():
        return []
    out = []
    with f.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                d["_ts"] = parse_ts(d.get("ts", ""))
                out.append(d)
            except json.JSONDecodeError:
                continue
    return [d for d in out if d.get("_ts")]


def load_session_traces(project_root: Path, session_id: str):
    f = project_root / ".harness" / "runtime" / "traces" / f"{session_id}.jsonl"
    if not f.is_file():
        return []
    out = []
    with f.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                d["_ts"] = parse_ts(d.get("ts", ""))
                out.append(d)
            except json.JSONDecodeError:
                continue
    return [d for d in out if d.get("_ts")]


def aggregate_for_prompt(prompt, next_prompt_ts, decisions, traces):
    start_ts = prompt["_ts"]
    end_ts = next_prompt_ts  # None이면 무한대

    def in_window(ev):
        ts = ev.get("_ts")
        if ts is None or ts < start_ts:
            return False
        if end_ts is not None and ts >= end_ts:
            return False
        return True

    win_decisions = [d for d in decisions if in_window(d)]
    win_traces = [t for t in traces if in_window(t)]

    denies = sum(1 for d in win_decisions if d.get("decision", "").startswith("deny"))
    bypass = sum(1 for d in win_decisions if (d.get("extra") or {}).get("bypass") if isinstance(d.get("extra"), dict))
    tool_calls = sum(1 for t in win_traces if t.get("event_type") == "tool_use")
    stops = sum(1 for t in win_traces if t.get("event_type") == "stop")
    # retries = stop이 여러 번 fire되면 verify 실패로 재시도된 것
    retries = max(0, stops - 1) if stops else 0

    # 도구 호출 첫·마지막 시간으로 duration
    last_event_ts = None
    for t in reversed(win_traces):
        if t.get("event_type") in ("tool_use", "stop"):
            last_event_ts = t.get("_ts")
            break
    if last_event_ts:
        duration_s = (last_event_ts - start_ts).total_seconds()
    else:
        duration_s = 0.0

    deny_categories = {}
    for d in win_decisions:
        if d.get("decision", "").startswith("deny"):
            cat = d.get("reason_category", "?")
            deny_categories[cat] = deny_categories.get(cat, 0) + 1

    score = denies * 2 + retries * 3 + duration_s / 10 + bypass * 1

    return {
        "tool_calls": tool_calls,
        "denies": denies,
        "deny_categories": deny_categories,
        "bypass": bypass,
        "retries": retries,
        "duration_s": round(duration_s, 1),
        "struggle_score": round(score, 1),
    }


def load_session_judges(session_dir: Path):
    f = session_dir / "judge.jsonl"
    if not f.is_file():
        return {}
    out = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            out[d.get("prompt_ts", "")] = d
        except json.JSONDecodeError:
            continue
    return out


def collect(project_root: Path):
    sessions_dir = project_root / ".harness" / "runtime" / "sessions"
    if not sessions_dir.is_dir():
        return []
    rows = []
    for sd in sessions_dir.iterdir():
        if not sd.is_dir():
            continue
        sid = sd.name
        prompts = load_session_prompts(sd)
        if not prompts:
            continue
        decisions = load_session_decisions(sd)
        traces = load_session_traces(project_root, sid)
        judges = load_session_judges(sd)
        prompts.sort(key=lambda p: p["_ts"])
        for i, p in enumerate(prompts):
            next_ts = prompts[i + 1]["_ts"] if i + 1 < len(prompts) else None
            agg = aggregate_for_prompt(p, next_ts, decisions, traces)
            judge = judges.get(p.get("ts", ""))
            row = {
                "session_id": sid,
                "ts": p["ts"],
                "prompt": p.get("prompt", ""),
                **agg,
            }
            if judge:
                row["judge_score"] = judge.get("score")
                row["judge_feedback"] = judge.get("feedback")
            rows.append(row)
    return rows


def render_text(rows):
    if not rows:
        return "(prompt 데이터 없음 — UserPromptSubmit hook이 fire한 후에 데이터 쌓임)"
    out = []
    out.append(f"{'ts':<20} {'tool':>5} {'deny':>5} {'retry':>5} {'bypass':>6} {'dur(s)':>7} {'score':>6}  prompt")
    out.append("-" * 110)
    for r in sorted(rows, key=lambda x: -x["struggle_score"])[:20]:
        prompt = r["prompt"][:50].replace("\n", " ")
        out.append(
            f"{r['ts'][:19]:<20} "
            f"{r['tool_calls']:>5} {r['denies']:>5} {r['retries']:>5} "
            f"{r['bypass']:>6} {r['duration_s']:>7} {r['struggle_score']:>6}  "
            f"{prompt}"
        )
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(prog="harness viz prompts (헤맴)")
    parser.add_argument("--project-root", default=os.getcwd())
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    rows = collect(project_root)
    if args.format == "json":
        # 각 row에서 datetime 객체 빼고 직렬화
        out_rows = []
        for r in rows:
            out_rows.append({k: v for k, v in r.items() if not k.startswith("_")})
        print(json.dumps({"rows": out_rows}, ensure_ascii=False, indent=2))
    else:
        print(render_text(rows))


if __name__ == "__main__":
    main()
