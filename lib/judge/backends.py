"""Judge backend 추상화. 3종 backend + 공통 인터페이스.

각 backend는 evaluate(prompt, response, cfg) → {score, feedback, tokens?, model}.
실패 시 BackendError 발생.
"""
from __future__ import annotations

import json
import re
import subprocess


class BackendError(Exception):
    pass


JUDGE_PROMPT_DEFAULT = """\
사용자의 요청과 그에 대한 어시스턴트 응답을 평가하세요.

== 사용자 요청 ==
{prompt}

== 어시스턴트 응답 (요약) ==
{response}

== 평가 기준 ==
1. 요청 충족도 (의도 정확히 이해·해결)
2. 정확성·논리성
3. 효율성 (불필요한 헤맴 X)

JSON으로만 응답:
{{"score": <0-10>, "feedback": "<2-3 문장 한국어>"}}
"""


def parse_judge_text(text: str):
    """LLM 응답에서 {score, feedback} 추출."""
    m = re.search(r"\{[\s\S]*?\}", text)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        return {
            "score": float(d.get("score", 0)),
            "feedback": str(d.get("feedback", "")),
        }
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


# -------------------- Backend: claude_cli --------------------

def backend_claude_cli(prompt: str, response: str, cfg: dict) -> dict:
    """`claude -p "<prompt>"` 사용. claude code 구독 활용 (별도 API key X)."""
    template = cfg.get("prompt_template", JUDGE_PROMPT_DEFAULT)
    text_in = template.format(prompt=prompt[:2000], response=response[:4000])
    try:
        proc = subprocess.run(
            ["claude", "-p", text_in],
            capture_output=True, text=True, timeout=120,
        )
    except FileNotFoundError:
        raise BackendError("claude CLI 없음. 설치 후 PATH에 추가하세요.")
    except subprocess.TimeoutExpired:
        raise BackendError("claude CLI 타임아웃 (>120s)")
    if proc.returncode != 0:
        raise BackendError(f"claude CLI 실패 (rc={proc.returncode}): {proc.stderr[:200]}")
    parsed = parse_judge_text(proc.stdout)
    if parsed is None:
        raise BackendError(f"JSON 파싱 실패: {proc.stdout[:200]}")
    parsed["model"] = "claude-cli"
    parsed["tokens"] = {"input": 0, "output": 0}  # CLI는 token 정보 안 줌
    return parsed


# -------------------- Backend: codex --------------------

def backend_codex(prompt: str, response: str, cfg: dict) -> dict:
    """`codex exec "<prompt>"` 사용. codex 비대화 모드.
    codex CLI의 정확한 플래그는 환경별로 차이 있을 수 있어 여러 후보 시도."""
    template = cfg.get("prompt_template", JUDGE_PROMPT_DEFAULT)
    text_in = template.format(prompt=prompt[:2000], response=response[:4000])

    candidates = [
        ["codex", "exec", text_in],          # 가장 일반적
        ["codex", "-p", text_in],             # 단일 prompt 모드
        ["codex", "--print", text_in],        # alt
    ]
    last_err = None
    for cmd in candidates:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except FileNotFoundError:
            raise BackendError("codex CLI 없음. 설치 후 PATH에 추가하세요.")
        except subprocess.TimeoutExpired:
            last_err = "timeout"
            continue
        if proc.returncode == 0 and proc.stdout.strip():
            parsed = parse_judge_text(proc.stdout)
            if parsed is None:
                raise BackendError(f"JSON 파싱 실패: {proc.stdout[:200]}")
            parsed["model"] = "codex-cli"
            parsed["tokens"] = {"input": 0, "output": 0}
            return parsed
        last_err = f"rc={proc.returncode} stderr={proc.stderr[:200]}"
    raise BackendError(f"codex 호출 실패 (모든 변형 시도). last: {last_err}")


# -------------------- Backend: manual --------------------

def backend_manual(prompt: str, response: str, cfg: dict) -> dict:
    """사용자에게 직접 채점 요청 (TTY)."""
    print("\n" + "=" * 60)
    print("[Manual Judge] 다음 prompt-응답 쌍을 0~10 점으로 평가하세요.")
    print("=" * 60)
    print("== Prompt ==")
    print(prompt[:1500])
    print("\n== Response ==")
    print(response[:2500])
    print("=" * 60)
    while True:
        s = input("점수 (0~10, 'skip' = 건너뜀): ").strip()
        if s.lower() == "skip":
            raise BackendError("user skip")
        try:
            score = float(s)
            if 0 <= score <= 10:
                break
        except ValueError:
            pass
        print("0~10 사이 숫자 또는 'skip'")
    feedback = input("피드백 한 줄 (옵션): ").strip()
    return {
        "score": score,
        "feedback": feedback,
        "model": "manual",
        "tokens": {"input": 0, "output": 0},
    }


# -------------------- Dispatch --------------------

BACKENDS = {
    "claude_cli": backend_claude_cli,
    "codex":      backend_codex,
    "manual":     backend_manual,
}


def evaluate(prompt: str, response: str, judge_cfg: dict) -> dict:
    """judge_cfg는 compose.yaml의 llm_judge 섹션 전체.
    backend별 sub-config는 judge_cfg.<backend_name> dict."""
    backend_name = judge_cfg.get("backend", "claude_cli")
    backend = BACKENDS.get(backend_name)
    if backend is None:
        raise BackendError(f"unknown backend: {backend_name} (가능: {list(BACKENDS.keys())})")
    sub_cfg = judge_cfg.get(backend_name) or {}
    if "prompt_template" in judge_cfg:
        sub_cfg = {**sub_cfg, "prompt_template": judge_cfg["prompt_template"]}
    return backend(prompt, response, sub_cfg)
