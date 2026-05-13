"""v1 → v2 마이그레이션 스크립트 (issue #6 Phase B 실제 실행).

기존 `standard/` 를 안 건드리고 `standard_v2/` 를 옆에 새로 만든다 (side-by-side).
스크립트 실패 시 단순히 `standard_v2/` 삭제로 복구 가능 — v1 영향 0.

수행 작업:
  1. 단일 파일 자산 (AGENTS.md, hooks/*.sh, templates/*.md) → v2 폴더로 이동 + manifest 작성
  2. 폴더 자산 (ralph, adapters/*) → 폴더 통째 복사 + manifest 작성
  3. 단순 copy 자산 (eval/cases, hooks/lib, README, roles.yaml) → manifest 없이 복사
  4. 검증 — harness validate 가 만족할 수 있는 상태 확보

옵션:
  --src <path>        v1 standard 루트 (기본: standard)
  --dst <path>        v2 출력 루트 (기본: standard_v2)
  --dry-run           실제 생성 없이 무엇이 만들어질지만 출력
  --force             대상 디렉토리가 이미 있으면 삭제 후 진행
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Optional

import yaml


# ───────────────────── 매핑 표 ─────────────────────
# 단일 파일 → v2 폴더화 + manifest. 각 항목 = (src 상대경로, dst 상대경로, manifest dict).
SINGLE_FILE_ASSETS = [
    # === instructions ===
    {
        "src": "AGENTS.md",
        "dst": "instructions/agents_md/AGENTS.md",
        "manifest": {
            "id": "agents_md",
            "domain": "cognition",
            "mechanism": "instructions",
            "purpose": "harness 시스템 prefix 텍스트 (정체성 + 행동 원칙)",
            "roles": ["prefix_injection"],
            "entry": "./AGENTS.md",
        },
    },
    # === templates → instructions/templates ===
    {
        "src": "templates/README.md",
        "dst": "instructions/templates/readme/README.md",
        "manifest": {
            "id": "template_readme",
            "domain": "cognition",
            "mechanism": "instructions",
            "purpose": "README.md 스카폴드 템플릿",
            "roles": ["prefix_injection"],
            "entry": "./README.md",
        },
    },
    {
        "src": "templates/DESIGN.md",
        "dst": "instructions/templates/design/DESIGN.md",
        "manifest": {
            "id": "template_design",
            "domain": "cognition",
            "mechanism": "instructions",
            "purpose": "DESIGN.md 스카폴드 템플릿",
            "roles": ["prefix_injection"],
            "entry": "./DESIGN.md",
        },
    },
    {
        "src": "templates/CONVENTIONS.md",
        "dst": "instructions/templates/conventions/CONVENTIONS.md",
        "manifest": {
            "id": "template_conventions",
            "domain": "cognition",
            "mechanism": "instructions",
            "purpose": "CONVENTIONS.md 스카폴드 템플릿",
            "roles": ["prefix_injection"],
            "entry": "./CONVENTIONS.md",
        },
    },
    {
        "src": "templates/SECURITY.md",
        "dst": "instructions/templates/security/SECURITY.md",
        "manifest": {
            "id": "template_security",
            "domain": "cognition",
            "mechanism": "instructions",
            "purpose": "SECURITY.md 스카폴드 템플릿",
            "roles": ["prefix_injection"],
            "entry": "./SECURITY.md",
        },
    },
    # === hooks ===
    {
        "src": "hooks/session_start.sh",
        "dst": "hooks/session_start/session_start.sh",
        "manifest": {
            "id": "session_start",
            "domain": "cognition",
            "mechanism": "hooks",
            "purpose": "세션 시작: prefix 주입 + 상태 초기화 + trace 기록",
            "roles": ["prefix_injection", "status_init", "trace_log"],
            "event": "session_start",
            "entry": "./session_start.sh",
        },
    },
    {
        "src": "hooks/pre_tool_use.sh",
        "dst": "hooks/pre_tool_use/pre_tool_use.sh",
        "manifest": {
            "id": "pre_tool_use",
            "domain": "guard",
            "mechanism": "hooks",
            "purpose": "변경 도구 호출 직전 다중 검사 (required/cognitive/loop)",
            "roles": [
                "required_check",
                "cognitive_guard",
                "loop_detection",
                "context_gating",
                "trace_log",
            ],
            "event": "pre_tool_use",
            "entry": "./pre_tool_use.sh",
        },
    },
    {
        "src": "hooks/post_tool_use.sh",
        "dst": "hooks/post_tool_use/post_tool_use.sh",
        "manifest": {
            "id": "post_tool_use",
            "domain": "observe",
            "mechanism": "hooks",
            "purpose": "도구 호출 후 trace 및 metric 기록",
            "roles": ["trace_log", "metric_collect"],
            "event": "post_tool_use",
            "entry": "./post_tool_use.sh",
        },
    },
    {
        "src": "hooks/stop.sh",
        "dst": "hooks/stop/stop.sh",
        "manifest": {
            "id": "stop",
            "domain": "guard",
            "mechanism": "hooks",
            "purpose": "세션 종료 직전 stop 조건 검증",
            "roles": ["stop_validation", "trace_log"],
            "event": "stop",
            "entry": "./stop.sh",
        },
    },
    {
        "src": "hooks/user_prompt_submit.sh",
        "dst": "hooks/user_prompt_submit/user_prompt_submit.sh",
        "manifest": {
            "id": "user_prompt_submit",
            "domain": "cognition",
            "mechanism": "hooks",
            "purpose": "사용자 prompt 제출 시 rule reminder + trace",
            "roles": ["rule_reminder", "trace_log"],
            "event": "user_prompt_submit",
            "entry": "./user_prompt_submit.sh",
        },
    },
    {
        "src": "hooks/post_commit.sh",
        "dst": "hooks/post_commit/post_commit.sh",
        "manifest": {
            "id": "post_commit",
            "domain": "observe",
            "mechanism": "hooks",
            "purpose": "커밋 후 trace 기록",
            "roles": ["trace_log"],
            "event": "post_commit",
            "entry": "./post_commit.sh",
        },
    },
]


# 폴더 자산 → 폴더 통째 복사 + manifest 작성 (폴더 안 manifest.yaml).
FOLDER_ASSETS = [
    {
        "src": "ralph",
        "dst": "workflows/ralph",
        "manifest": {
            "id": "ralph",
            "domain": "state",
            "mechanism": "workflows",
            "purpose": "자가 검증 self-loop 워크플로우",
            "roles": ["workflow_step"],
            "entry": "./runner.sh",
        },
    },
    {
        "src": "adapters/claude",
        "dst": "adapters/claude",
        "manifest": {
            "id": "claude_adapter",
            "domain": "action",
            "mechanism": "adapters",
            "purpose": "Claude Code provider 결합 (driver + hook 번역)",
            "roles": ["adapter_call"],
            "entry": "./driver.py",
        },
    },
    {
        "src": "adapters/codex",
        "dst": "adapters/codex",
        "manifest": {
            "id": "codex_adapter",
            "domain": "action",
            "mechanism": "adapters",
            "purpose": "Codex CLI provider 결합 (TOML 기반)",
            "roles": ["adapter_call"],
            "entry": "./driver.py",
        },
    },
]


# manifest 없이 그대로 복사 (데이터 / 공유 코드 / 메타 파일).
# 폴더는 trailing slash 없이, 마지막에 / 가 없으면 단일 파일로 본다.
COPY_AS_IS = [
    ("hooks/lib", "hooks/_lib"),                # hook 공유 라이브러리
    ("hooks/README.md", "hooks/README.md"),
    ("eval/cases", "evals/cases"),               # 평가 케이스 데이터
    ("adapters/README.md", "adapters/README.md"),
    # provider artifact (claude/, codex/) 는 위 ADAPTER_ARTIFACTS 에서 manifest 와 함께 처리.
    # 엔진 .py 들은 v2 에서 lib/adapters/ 로 분리됨 — 사용자 v1 에 복사본이 있어도 install.sh 가 새로 깔아주므로 마이그레이션 X.
    ("roles.yaml", "roles.yaml"),
    ("README.md", "README.md"),
]


# ───────────────────── 핵심 로직 ─────────────────────


class Migration:
    def __init__(self, src: Path, dst: Path, dry_run: bool):
        self.src = src
        self.dst = dst
        self.dry_run = dry_run
        self.actions: list[str] = []

    def run(self) -> None:
        # 출력 루트 자체 생성
        self._mkdir(self.dst)

        # 1. 단일 파일 자산
        for spec in SINGLE_FILE_ASSETS:
            self._migrate_single_file(spec)

        # 2. 폴더 자산
        for spec in FOLDER_ASSETS:
            self._migrate_folder_with_manifest(spec)

        # 3. 단순 복사
        for src_rel, dst_rel in COPY_AS_IS:
            self._copy_as_is(src_rel, dst_rel)

    def _migrate_single_file(self, spec: dict) -> None:
        src = self.src / spec["src"]
        dst = self.dst / spec["dst"]
        if not src.exists():
            self.actions.append(f"⊙ skip (src 없음): {src}")
            return
        self._copy_file(src, dst)
        # manifest 작성 — dst 의 부모 폴더에
        manifest_path = dst.parent / "manifest.yaml"
        self._write_yaml(manifest_path, spec["manifest"])

    def _migrate_folder_with_manifest(self, spec: dict) -> None:
        src = self.src / spec["src"]
        dst = self.dst / spec["dst"]
        if not src.exists():
            self.actions.append(f"⊙ skip (src 없음): {src}")
            return
        self._copy_tree(src, dst)
        manifest_path = dst / "manifest.yaml"
        # 기존 manifest.yaml (v1) 가 있으면 덮어쓰기 (v2 형식으로)
        self._write_yaml(manifest_path, spec["manifest"])

    def _copy_as_is(self, src_rel: str, dst_rel: str) -> None:
        src = self.src / src_rel
        dst = self.dst / dst_rel
        if not src.exists():
            self.actions.append(f"⊙ skip (src 없음): {src}")
            return
        if src.is_dir():
            self._copy_tree(src, dst)
        else:
            self._copy_file(src, dst)

    # ───────────── 저수준 파일 작업 ─────────────

    def _mkdir(self, p: Path) -> None:
        self.actions.append(f"  📁 mkdir {p.relative_to(self.dst.parent)}")
        if not self.dry_run:
            p.mkdir(parents=True, exist_ok=True)

    def _copy_file(self, src: Path, dst: Path) -> None:
        rel = dst.relative_to(self.dst.parent)
        self.actions.append(f"  📄 copy {src.name} → {rel}")
        if not self.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    def _copy_tree(self, src: Path, dst: Path) -> None:
        rel = dst.relative_to(self.dst.parent)
        self.actions.append(f"  📂 copy-tree {src.name}/ → {rel}/")
        if not self.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)

    def _write_yaml(self, path: Path, data: dict) -> None:
        rel = path.relative_to(self.dst.parent)
        self.actions.append(f"  📝 manifest {rel} (id={data.get('id')})")
        if not self.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(
                    data,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )


# ───────────────────── CLI ─────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(
        description="standard/ (v1) → standard_v2/ side-by-side 마이그레이션",
    )
    ap.add_argument("--src", type=Path, default=Path("standard"))
    ap.add_argument("--dst", type=Path, default=Path("standard_v2"))
    ap.add_argument("--dry-run", action="store_true", help="실제 생성 없이 plan 만 출력")
    ap.add_argument("--force", action="store_true", help="dst 이미 존재 시 삭제 후 진행")
    args = ap.parse_args()

    if not args.src.exists():
        print(f"✗ src 디렉토리 없음: {args.src}", file=sys.stderr)
        return 2

    if args.dst.exists():
        if args.force:
            if not args.dry_run:
                shutil.rmtree(args.dst)
            print(f"⚠ {args.dst} 삭제 후 재생성 (force)")
        else:
            print(
                f"✗ {args.dst} 이미 존재. --force 또는 --dry-run 사용 권장.",
                file=sys.stderr,
            )
            return 2

    mode = "[dry-run] " if args.dry_run else ""
    print(f"{mode}migrate {args.src} → {args.dst}")
    print()

    m = Migration(args.src, args.dst, dry_run=args.dry_run)
    m.run()

    for action in m.actions:
        print(action)

    print()
    if args.dry_run:
        print("(dry-run — 실제 변경 없음)")
    else:
        print(f"✓ {args.dst} 생성 완료")
        print()
        print("다음 단계: harness validate --standard ./standard_v2  으로 검증")
    return 0


if __name__ == "__main__":
    sys.exit(main())
