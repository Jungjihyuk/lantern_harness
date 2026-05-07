#!/usr/bin/env python3
"""LLM-as-judge — prompt와 응답을 평가해 점수 매김.

활성화: compose.yaml의 llm_judge.enabled: true
필수: 환경변수에 API key (default: ANTHROPIC_API_KEY)

사용:
    python3 main.py run [--session=<id>]            평가 실행 (없으면 미평가 것 모두)
    python3 main.py run --all                        모든 prompt 재평가
    python3 main.py status [<session-id>]            평가 진척

저장: <project>/.harness/runtime/sessions/<id>/judge.jsonl
형식: {prompt_ts, score, feedback, model, evaluated_at, cost_estimate}

비용 안전:
- 호출 전 prompt 개수·예상 비용 표시
- --yes 없으면 confirmation 요구
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("Error: PyYAML 필요\n")
    sys.exit(1)

# 같은 디렉토리의 backends.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backends import BACKENDS, BackendError, evaluate as backend_evaluate  # noqa: E402


def load_active(project_root: Path):
    p = project_root / ".harness" / "compose.yaml"
    if not p.is_file():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def find_sessions(project_root: Path):
    sd = project_root / ".harness" / "runtime" / "sessions"
    if not sd.is_dir():
        return []
    return sorted([d for d in sd.iterdir() if d.is_dir()], key=lambda p: p.name)


def load_prompts(session_dir: Path):
    f = session_dir / "prompts.jsonl"
    if not f.is_file():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def load_judges(session_dir: Path):
    f = session_dir / "judge.jsonl"
    if not f.is_file():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def parse_transcript_responses(transcript_path: Path):
    """claude transcript jsonl을 읽어 [(prompt_ts, response_text)] 추출.
    transcript 파일은 turn 별 메시지 (user/assistant) 누적."""
    if not transcript_path.is_file():
        return []
    pairs = []
    last_user_ts = None
    last_user_text = None
    response_chunks = []
    for line in transcript_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        # 메시지 형식 (claude transcript): {"type": "user|assistant", "message": {...}, ...}
        # 정확한 스키마는 claude 버전마다 다를 수 있음 — 방어적 추출
        mtype = msg.get("type") or msg.get("role")
        # 사용자 prompt
        if mtype in ("user", "human"):
            # 이전 응답 마무리
            if last_user_ts is not None and response_chunks:
                pairs.append({
                    "prompt_ts": last_user_ts,
                    "prompt": last_user_text or "",
                    "response": "\n".join(response_chunks)[:8000],
                })
                response_chunks = []
            content = msg.get("message", {}).get("content") if isinstance(msg.get("message"), dict) else msg.get("content")
            if isinstance(content, list):
                texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                last_user_text = "\n".join(texts)
            else:
                last_user_text = str(content) if content else ""
            last_user_ts = msg.get("timestamp") or msg.get("ts") or ""
        elif mtype in ("assistant", "ai"):
            content = msg.get("message", {}).get("content") if isinstance(msg.get("message"), dict) else msg.get("content")
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        response_chunks.append(c.get("text", ""))
            elif isinstance(content, str):
                response_chunks.append(content)
    # 마지막 페어
    if last_user_ts is not None and response_chunks:
        pairs.append({
            "prompt_ts": last_user_ts,
            "prompt": last_user_text or "",
            "response": "\n".join(response_chunks)[:8000],
        })
    return pairs


def cmd_run(project_root: Path, session_arg: str | None, all_flag: bool, yes: bool):
    cfg = load_active(project_root)
    jcfg = cfg.get("llm_judge") or {}
    if not jcfg.get("enabled"):
        print("llm_judge.enabled가 false. compose.yaml에서 활성화하세요.")
        return 1
    backend_name = jcfg.get("backend", "api")
    if backend_name not in BACKENDS:
        print(f"unknown backend: {backend_name}. 가능: {list(BACKENDS.keys())}")
        return 1

    # 평가 대상 수집
    sessions = find_sessions(project_root)
    if session_arg:
        sessions = [s for s in sessions if s.name == session_arg]
    targets = []  # [(session_dir, prompt_dict)]
    for sd in sessions:
        meta = sd / "meta.json"
        if not meta.is_file():
            continue
        m = json.loads(meta.read_text(encoding="utf-8"))
        tp = m.get("transcript_path")
        if not tp:
            continue
        existing_judges = {j["prompt_ts"] for j in load_judges(sd)} if not all_flag else set()
        try:
            pairs = parse_transcript_responses(Path(tp))
        except Exception as e:
            print(f"  ! transcript 파싱 실패 {sd.name}: {e}")
            continue
        for p in pairs:
            if p["prompt_ts"] in existing_judges:
                continue
            targets.append((sd, p))

    if not targets:
        print("평가할 새 prompt 없음.")
        return 0

    print(f"평가 대상: {len(targets)}개")
    print(f"backend: {backend_name}")
    if backend_name == "claude_cli":
        print("(claude code 구독 활용 — rate limit 소비)")
    elif backend_name == "codex":
        print("(codex CLI 활용 — 구독·rate limit 소비)")
    elif backend_name == "manual":
        print("(직접 채점 — 콘솔 입력 필요)")

    if not yes and backend_name != "manual":
        ans = input("계속? [y/N]: ").strip().lower()
        if ans != "y":
            print("취소")
            return 1

    success = 0
    failed = 0
    for sd, p in targets:
        try:
            parsed = backend_evaluate(p["prompt"], p["response"], jcfg)
        except BackendError as e:
            print(f"  ✗ {p['prompt_ts'][:19]}: {e}")
            failed += 1
            continue
        except Exception as e:
            print(f"  ✗ {p['prompt_ts'][:19]}: 예외 {e}")
            failed += 1
            continue
        record = {
            "prompt_ts": p["prompt_ts"],
            "score": parsed["score"],
            "feedback": parsed["feedback"],
            "model": parsed.get("model", backend_name),
            "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tokens": parsed.get("tokens", {"input": 0, "output": 0}),
        }
        with (sd / "judge.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        success += 1
        print(f"  ✓ {p['prompt_ts'][:19]} score={parsed['score']}")
    print(f"\n{success} 성공, {failed} 실패")


def cmd_status(project_root: Path, session_arg: str | None):
    sessions = find_sessions(project_root)
    if session_arg:
        sessions = [s for s in sessions if s.name == session_arg]
    if not sessions:
        print("(세션 없음)")
        return
    print(f"{'session':<40} {'prompts':>8} {'judged':>8} {'avg_score':>10}")
    for sd in sessions:
        prompts = load_prompts(sd)
        judges = load_judges(sd)
        avg = (sum(j.get("score", 0) for j in judges) / len(judges)) if judges else 0
        print(f"{sd.name:<40} {len(prompts):>8} {len(judges):>8} {avg:>10.1f}")


def main():
    parser = argparse.ArgumentParser(prog="harness judge")
    parser.add_argument("cmd", choices=["run", "status"])
    parser.add_argument("session", nargs="?", default=None)
    parser.add_argument("--project-root", default=os.getcwd())
    parser.add_argument("--all", action="store_true", help="이미 평가된 것도 재평가")
    parser.add_argument("-y", "--yes", action="store_true", help="비용 confirmation 건너뛰기")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    if args.cmd == "run":
        sys.exit(cmd_run(project_root, args.session, args.all, args.yes))
    elif args.cmd == "status":
        cmd_status(project_root, args.session)


if __name__ == "__main__":
    main()
