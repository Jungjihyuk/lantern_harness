#!/usr/bin/env python3
"""evolution.py — git post-commit이 호출.
.harness/ 의 diff를 분석해 evolution/CHANGELOG.md에 한 항목 자동 추가.

사용:
    python3 evolution.py <project_root>

룰 기반 분류 (LLM 요약은 미래 옵션):
- standard/<name>/ 신규/삭제 → plugin Added/Removed
- know-how/skills/<name>/ 신규 → skill Added
- AGENTS.md 변경 → Changed (+N -M lines)
- compose.yaml 변경 → Changed
- 그 외 .harness/ 파일 → Changed (path)
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def get_diff_summary(project_root: Path):
    """이번 commit의 .harness/ 안 변경을 분류."""
    res = run(
        ["git", "diff", "--name-status", "HEAD~1", "HEAD", "--", ".harness/"],
        cwd=project_root,
    )
    if res.returncode != 0:
        return None  # 첫 commit 이거나 git 에러
    added, changed, removed = [], [], []
    for line in res.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, path = parts[0], parts[1]
        if status.startswith("A"):
            added.append(path)
        elif status.startswith("D"):
            removed.append(path)
        else:  # M, R, etc.
            changed.append(path)
    return {"added": added, "changed": changed, "removed": removed}


def classify(paths_dict, project_root):
    """카테고리별 사람 가독 메시지 리스트 생성."""
    out = {"Added": [], "Changed": [], "Removed": []}

    def label(p):
        m = re.match(r"\.harness/standard/([^/]+)(?:/.*)?$", p)
        if m:
            return f"plugin: {m.group(1)}"
        m = re.match(r"\.harness/know-how/skills/([^/]+)(?:/.*)?$", p)
        if m:
            return f"skill: know-how/skills/{m.group(1)}"
        m = re.match(r"\.harness/know-how/hooks/(.+)$", p)
        if m:
            return f"hook: know-how/hooks/{m.group(1)}"
        if p == ".harness/compose.yaml":
            return "compose.yaml"
        if p == ".harness/know-how/AGENTS.md":
            return "know-how/AGENTS.md"
        return p

    seen = {"Added": set(), "Changed": set(), "Removed": set()}
    for cat_key, paths in [("Added", paths_dict["added"]),
                           ("Removed", paths_dict["removed"]),
                           ("Changed", paths_dict["changed"])]:
        for p in paths:
            lbl = label(p)
            if lbl in seen[cat_key]:
                continue
            seen[cat_key].add(lbl)
            # AGENTS.md / compose.yaml 의 경우 라인 diff 추가
            extra = ""
            if cat_key == "Changed" and p in (".harness/compose.yaml", ".harness/know-how/AGENTS.md"):
                stat = run(
                    ["git", "diff", "--shortstat", "HEAD~1", "HEAD", "--", p],
                    cwd=project_root,
                )
                if stat.returncode == 0 and stat.stdout.strip():
                    # "1 file changed, 2 insertions(+), 1 deletion(-)"
                    txt = stat.stdout.strip().split(",", 1)[-1]
                    extra = f" ({txt.strip()})"
            out[cat_key].append(f"- {lbl}{extra}")
    return out


def get_commit_meta(project_root):
    sha = run(["git", "rev-parse", "--short", "HEAD"], cwd=project_root).stdout.strip()
    msg = run(["git", "log", "-1", "--pretty=%s"], cwd=project_root).stdout.strip()
    return sha, msg


def append_changelog(project_root: Path, classified, sha, msg):
    cl = project_root / ".harness" / "evolution" / "CHANGELOG.md"
    cl.parent.mkdir(parents=True, exist_ok=True)
    if not cl.exists():
        cl.write_text("# Harness Evolution Changelog\n\n", encoding="utf-8")

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    section = [f"## [{ts} — {sha}] {msg}"]
    has_any = False
    for cat in ("Added", "Changed", "Removed"):
        items = classified.get(cat, [])
        if items:
            has_any = True
            section.append(f"\n### {cat}")
            section.extend(items)
    if not has_any:
        return False
    section.append("")  # trailing blank line

    # 최신 항목이 위로 가게 — Header 다음에 prepend
    existing = cl.read_text(encoding="utf-8")
    lines = existing.splitlines(keepends=True)
    # 첫 # 헤더 다음에 삽입
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            insert_at = i + 1
            break
    new_section = "\n" + "\n".join(section) + "\n"
    new = "".join(lines[:insert_at]) + new_section + "".join(lines[insert_at:])
    cl.write_text(new, encoding="utf-8")
    return True


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: python3 evolution.py <project_root>\n")
        sys.exit(1)
    project_root = Path(sys.argv[1]).resolve()
    if not (project_root / ".harness").is_dir():
        return  # harness 미적용 프로젝트
    if not (project_root / ".git").is_dir():
        return

    summary = get_diff_summary(project_root)
    if summary is None:
        return  # 첫 commit
    if not (summary["added"] or summary["changed"] or summary["removed"]):
        return  # .harness/ 변경 없음

    classified = classify(summary, project_root)
    sha, msg = get_commit_meta(project_root)
    if append_changelog(project_root, classified, sha, msg):
        sys.stderr.write("✓ harness: evolution/CHANGELOG.md 갱신\n")


if __name__ == "__main__":
    main()
