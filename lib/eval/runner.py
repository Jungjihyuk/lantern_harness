#!/usr/bin/env python3
"""harness eval — case 실행 + 결과 누적.

지원 type:
- hook_unit: hook 스크립트를 mock 입력으로 직접 호출 (claude 호출 X)
  → 빠르고 결정론적. CI 친화.

사용:
    python3 runner.py run [<case-id>...]      모든 케이스 또는 특정 케이스 실행
    python3 runner.py report                   누적 결과 표시
    python3 runner.py list                     사용 가능한 케이스 나열
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("Error: PyYAML 필요. pip3 install pyyaml\n")
    sys.exit(1)


HARNESS_HOME = Path.home() / ".harness"
GLOBAL_CASES = HARNESS_HOME / "standard" / "eval" / "cases"


def find_cases(project_root: Path | None = None):
    """글로벌 + 프로젝트 know-how/eval/cases 검색."""
    cases = {}
    for src in [GLOBAL_CASES] + ([project_root / ".harness" / "know-how" / "eval" / "cases"] if project_root else []):
        if not src.is_dir():
            continue
        for f in src.glob("*.yaml"):
            cid = f.stem
            cases[cid] = f
    return cases


def load_case(path: Path):
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_temp_project(case: dict, tmpdir: Path):
    """case의 setup 섹션을 따라 임시 프로젝트 구성."""
    setup = case.get("setup", {}) or {}

    if setup.get("init_harness"):
        # Minimal harness init (직접 — harness CLI 안 거침, 외부 의존 줄이려)
        h = tmpdir / ".harness"
        (h / "standard").mkdir(parents=True, exist_ok=True)
        (h / "know-how").mkdir(exist_ok=True)
        (h / "runtime").mkdir(exist_ok=True)
        (h / "evolution").mkdir(exist_ok=True)
        # standard/AGENTS.md symlink
        try:
            (h / "standard" / "AGENTS.md").symlink_to(HARNESS_HOME / "standard" / "AGENTS.md")
        except FileExistsError:
            pass
        # default compose.yaml
        default_active = {
            "mode": "human-gated",
            "prefix": ["AGENTS.md"],
            "plugins": ["hooks"],
            "hooks": {h: "enabled" for h in ("session_start","user_prompt_submit","pre_tool_use","post_tool_use","stop")},
            "required_context": {"default_on_deny": "self_correct", "paths": []},
            "on_demand_context": {"paths": []},
            "trigger_read": [],
            "hard_rules": [],
            "cognitive_guard": {
                "enabled": True,
                "per_call": {"max_diff_lines": 200, "max_new_files": 3},
                "per_session": {"max_changed_files": 10, "max_diff_lines": 1000},
                "on_breach": "ask_human",
                "bypass_marker": "@harness allow-large",
            },
            "loop_detection": {"enabled": True, "consecutive_same_path": 3, "on_loop": "self_correct"},
        }
        # active_yaml_overrides
        overrides = setup.get("active_yaml_overrides", {}) or {}
        active = _deep_merge(default_active, overrides)
        with (h / "compose.yaml").open("w", encoding="utf-8") as f:
            yaml.safe_dump(active, f, allow_unicode=True, sort_keys=False)

    # files
    for entry in setup.get("files", []) or []:
        p = tmpdir / entry["path"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(entry.get("content", ""), encoding="utf-8")

    # 사전에 hook 호출 (e.g. before_agent 또는 미리 Read 처리)
    for pre in setup.get("pre_calls", []) or []:
        _call_hook(pre.get("hook"), pre.get("input"), tmpdir)


def _deep_merge(a: dict, b: dict):
    out = dict(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _call_hook(hook_name: str, input_obj: dict, project_root: Path):
    """Hook 스크립트를 직접 호출."""
    hook_path = HARNESS_HOME / "standard" / "hooks" / f"{hook_name}.sh"
    if not hook_path.is_file():
        return None
    inp = dict(input_obj or {})
    inp.setdefault("project_root", str(project_root))
    if "session_id" not in inp:
        inp["session_id"] = "eval-session"
    proc = subprocess.run(
        [str(hook_path)],
        input=json.dumps(inp).encode("utf-8"),
        capture_output=True,
        timeout=30,
    )
    return proc


def run_case(case_path: Path):
    case = load_case(case_path)
    cid = case.get("id", case_path.stem)
    desc = case.get("description", "")
    htype = case.get("type", "hook_unit")
    hook = case.get("hook")
    expected = case.get("expect", {}) or {}

    if htype != "hook_unit":
        return {"id": cid, "passed": False, "skipped": True, "reason": f"type={htype} 미지원"}

    if not hook:
        return {"id": cid, "passed": False, "reason": "case에 hook 키 없음"}

    started = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        setup_temp_project(case, tmp)
        # input의 project_root 자동 채움
        inp = dict(case.get("input") or {})
        inp.setdefault("project_root", str(tmp))
        inp.setdefault("session_id", "eval-session")
        proc = _call_hook(hook, inp, tmp)

    duration_ms = int((time.time() - started) * 1000)
    if proc is None:
        return {"id": cid, "passed": False, "reason": f"hook script 없음: {hook}"}

    rc = proc.returncode
    stdout = proc.stdout.decode("utf-8", errors="replace") if proc.stdout else ""
    stderr = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""

    failures = []
    if "exit_code" in expected:
        if rc != expected["exit_code"]:
            failures.append(f"exit_code={rc} != expected {expected['exit_code']}")
    if "stderr_contains" in expected:
        if expected["stderr_contains"] not in stderr:
            failures.append(f"stderr no '{expected['stderr_contains']}' (got: {stderr[:120]!r})")
    if "stderr_not_contains" in expected:
        if expected["stderr_not_contains"] in stderr:
            failures.append(f"stderr should not contain '{expected['stderr_not_contains']}'")
    if "stdout_contains" in expected:
        if expected["stdout_contains"] not in stdout:
            failures.append(f"stdout no '{expected['stdout_contains']}'")

    return {
        "id": cid,
        "description": desc,
        "passed": not failures,
        "failures": failures,
        "duration_ms": duration_ms,
        "exit_code": rc,
        "stderr": stderr.strip()[:300],
    }


def cmd_list(project_root: Path):
    cases = find_cases(project_root)
    if not cases:
        print("(케이스 없음)")
        return
    for cid, p in sorted(cases.items()):
        case = load_case(p)
        desc = case.get("description", "")
        print(f"  {cid:30s} {desc}")


def cmd_run(project_root: Path, ids: list[str]):
    cases = find_cases(project_root)
    if ids:
        cases = {k: v for k, v in cases.items() if k in ids}
    if not cases:
        print("(실행할 케이스 없음)")
        return 1
    results = []
    for cid in sorted(cases):
        r = run_case(cases[cid])
        results.append(r)
        sym = "✓" if r["passed"] else ("⊙" if r.get("skipped") else "✗")
        print(f"  {sym} {cid:30s} {r.get('description','')[:50]:50s} ({r.get('duration_ms', 0)}ms)")
        for fl in r.get("failures", []):
            print(f"      → {fl}")

    passed = sum(1 for r in results if r["passed"])
    skipped = sum(1 for r in results if r.get("skipped"))
    failed = len(results) - passed - skipped
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped (총 {len(results)})")

    # 결과 누적
    out_dir = project_root / ".harness" / "runtime" / "eval-results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    out_path.write_text(json.dumps({
        "ts": datetime.utcnow().isoformat() + "Z",
        "summary": {"passed": passed, "failed": failed, "skipped": skipped, "total": len(results)},
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"기록: {out_path}")
    return 0 if failed == 0 else 1


def cmd_report(project_root: Path):
    out_dir = project_root / ".harness" / "runtime" / "eval-results"
    if not out_dir.is_dir():
        print("(결과 없음 — 'harness eval run' 먼저 실행)")
        return
    files = sorted(out_dir.glob("*.json"))
    if not files:
        print("(결과 없음)")
        return
    print(f"{'timestamp':<22} {'passed':>7} {'failed':>7} {'skipped':>8} {'total':>6}")
    print("-" * 55)
    for f in files[-20:]:
        d = json.loads(f.read_text(encoding="utf-8"))
        s = d["summary"]
        print(f"{d['ts'][:19]:<22} {s['passed']:>7} {s['failed']:>7} {s['skipped']:>8} {s['total']:>6}")


def main():
    parser = argparse.ArgumentParser(prog="harness eval")
    parser.add_argument("cmd", choices=["run", "list", "report"])
    parser.add_argument("ids", nargs="*", help="실행할 case id (run일 때)")
    parser.add_argument("--project-root", default=os.getcwd())
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()

    if args.cmd == "list":
        cmd_list(project_root)
    elif args.cmd == "run":
        sys.exit(cmd_run(project_root, args.ids))
    elif args.cmd == "report":
        cmd_report(project_root)


if __name__ == "__main__":
    main()
