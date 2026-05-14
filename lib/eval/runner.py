#!/usr/bin/env python3
"""harness eval — manifest 기반 case 실행 (회귀 안전판).

본 명령의 의도: 하네스 시스템 (hook / policy / decision 로직) 의
메커니즘이 의도대로 작동하는지 회귀 테스트. LLM 응답 품질 평가가 아님
— 그건 별도 `judge` 명령.

case 구조 (standard/evals/cases/<id>/case.yaml):
  setup:
    init_harness: true
    files: [{path: README.md, content: "..."}]
    compose_overrides: { ... }                   # init 후 compose 에 deep merge
    pre_calls:
      - {hook: session_start, input: {hook_type: session_start}}
  hook: pre_tool_use                              # target hook (또는 case 의 input.hook_type)
  input: { ... }                                  # hook 에 보낼 envelope
  expect:
    decision: allow | self_correct | hard_stop | block
    reason_contains: "..."                        # 옵션

사용:
    python3 -m lib.eval.runner list
    python3 -m lib.eval.runner run [<case-id>...]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("Error: PyYAML 필요. pip3 install pyyaml\n")
    sys.exit(1)


def find_harness_root() -> Path:
    """이 파일이 dev tree 안이면 dev 우선; 아니면 HARNESS_HOME / ~/.harness."""
    dev = Path(__file__).resolve().parent.parent.parent
    if (dev / "standard").exists() and (dev / "bin" / "harness").exists():
        return dev
    return Path(os.environ.get("HARNESS_HOME", Path.home() / ".harness"))


def find_cases(harness_root: Path) -> dict[str, Path]:
    """standard/evals/cases/<id>/case.yaml 검색."""
    cases_dir = harness_root / "standard" / "evals" / "cases"
    out: dict[str, Path] = {}
    if not cases_dir.exists():
        return out
    for sub in sorted(cases_dir.iterdir()):
        if not sub.is_dir():
            continue
        case_file = sub / "case.yaml"
        if case_file.exists():
            out[sub.name] = case_file
    return out


def deep_merge(base: dict, overlay: dict) -> dict:
    """overlay 를 base 에 깊은 merge (dict 만)."""
    out = dict(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def setup_tmp(tmp: Path, harness_root: Path, setup: dict) -> None:
    """tmp dir 안에 .harness 초기화 + files + compose_overrides 적용."""
    if setup.get("init_harness"):
        init_sh = harness_root / "bin" / "cmd" / "init.sh"
        env = {**os.environ, "HARNESS_HOME": str(harness_root)}
        subprocess.run(["bash", str(init_sh)], cwd=str(tmp),
                       capture_output=True, env=env, check=False)

    # 사용자 파일 생성
    for f in setup.get("files", []) or []:
        if not isinstance(f, dict) or "path" not in f:
            continue
        fp = tmp / f["path"]
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(f.get("content", ""), encoding="utf-8")

    # compose_overrides 깊은 merge
    overrides = setup.get("compose_overrides")
    if overrides:
        compose_path = tmp / ".harness" / "compose.yaml"
        if compose_path.exists():
            cfg = yaml.safe_load(compose_path.read_text()) or {}
        else:
            cfg = {"version": 2}
        cfg = deep_merge(cfg, overrides)
        compose_path.parent.mkdir(parents=True, exist_ok=True)
        compose_path.write_text(
            yaml.safe_dump(cfg, default_flow_style=False,
                           allow_unicode=True, sort_keys=False)
        )


def invoke_hook(harness_root: Path, tmp: Path, hook_id: str, input_data: dict) -> dict:
    """hook handler.sh 호출, stdout JSON 반환."""
    handler = harness_root / "standard" / "hooks" / hook_id / "handler.sh"
    if not handler.exists():
        return {"decision": "error", "reason": f"handler 없음: {hook_id}"}

    envelope = {**input_data, "project_root": str(tmp)}
    envelope.setdefault("session_id", "eval_session")
    envelope.setdefault("hook_type", hook_id)

    env = {**os.environ, "HARNESS_HOME": str(harness_root)}
    r = subprocess.run(
        ["bash", str(handler)],
        input=json.dumps(envelope),
        capture_output=True, text=True, timeout=30,
        env=env, check=False,
    )
    try:
        return json.loads(r.stdout.strip())
    except Exception:
        return {"decision": "error",
                "reason": f"stdout 파싱 실패: {r.stdout[:120]} | stderr: {r.stderr[:200]}"}


def run_case(case_id: str, case: dict, harness_root: Path) -> tuple[bool, str]:
    """case 한 개 실행. (passed, message) 반환."""
    setup = case.get("setup", {}) or {}
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        try:
            setup_tmp(tmp, harness_root, setup)
        except Exception as e:
            return False, f"setup 실패: {e}"

        # pre_calls
        for pc in setup.get("pre_calls", []) or []:
            if not isinstance(pc, dict):
                continue
            invoke_hook(harness_root, tmp, pc.get("hook", ""), pc.get("input", {}) or {})

        # target hook
        target = case.get("hook") or (case.get("input") or {}).get("hook_type", "")
        if not target:
            return False, "target hook 미지정 (case.hook 또는 input.hook_type 필요)"

        result = invoke_hook(harness_root, tmp, target, case.get("input", {}) or {})

    expect = case.get("expect", {}) or {}
    exp_decision = expect.get("decision")
    if exp_decision and result.get("decision") != exp_decision:
        return False, (f"decision: expected={exp_decision} actual={result.get('decision')} "
                       f"reason={result.get('reason', '')}")

    exp_reason = expect.get("reason_contains")
    if exp_reason and exp_reason not in (result.get("reason") or ""):
        return False, f"reason_contains 미매칭: '{exp_reason}' not in '{result.get('reason', '')}'"

    return True, "ok"


def cmd_list(harness_root: Path) -> int:
    cases = find_cases(harness_root)
    if not cases:
        print("(case 없음)")
        return 0
    for cid in cases:
        print(f"  {cid}")
    return 0


def cmd_run(harness_root: Path, ids: list[str]) -> int:
    cases = find_cases(harness_root)
    if not cases:
        print("(case 없음 — standard/evals/cases/ 비어있음)")
        return 0

    targets = ids or list(cases.keys())
    total, passed = 0, 0
    for cid in targets:
        if cid not in cases:
            print(f"  ⊙ skip (없음): {cid}")
            continue
        try:
            data = yaml.safe_load(cases[cid].read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ✗ {cid}: yaml 파싱 실패 — {e}")
            total += 1
            continue
        ok, msg = run_case(cid, data, harness_root)
        total += 1
        if ok:
            passed += 1
            print(f"  ✓ {cid}")
        else:
            print(f"  ✗ {cid}: {msg}")

    print()
    print(f"{passed}/{total} passed")
    return 0 if passed == total else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="harness eval — 시스템 메커니즘 회귀 안전판")
    ap.add_argument("subcommand", nargs="?", default="list",
                    choices=["list", "run"])
    ap.add_argument("ids", nargs="*", help="run 시 case id (없으면 모두)")
    args = ap.parse_args()

    harness_root = find_harness_root()
    if args.subcommand == "list":
        return cmd_list(harness_root)
    return cmd_run(harness_root, args.ids)


if __name__ == "__main__":
    sys.exit(main())
