"""Claude Code provider driver.

읽는 위치:
  ~/.claude/mcp.json                          - MCP 서버 등록
  ~/.claude/skills/<name>/SKILL.md            - skill 정의 (frontmatter)
  ~/.claude/plugins/installed_plugins.json    - 설치된 plugin 메타
  ~/.claude/settings.json                     - enabledPlugins (native plugin 토글)

쓰는 위치 (disable/enable 시):
  ~/.claude/mcp.json                          - MCP entry 제거/복원
  ~/.claude/settings.json                     - enabledPlugins[<name>] 토글
  ~/.claude/skills/<name>/SKILL.md ↔ SKILL.md.disabled - rename

harness 사이드 상태:
  ~/.harness/state/claude/mcp_backup.json     - disabled MCP의 원본 설정 백업
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional


def _harness_data_dir() -> Path:
    """harness 의 사용자 데이터 디렉토리 (XDG Base Directory 컨벤션).

    install.sh 가 갈아엎는 `~/.harness/` 와 분리되어, 사용자 데이터(백업 등)는
    여기 보관한다. XDG_DATA_HOME 우선, 없으면 `~/.local/share/harness/`.
    """
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / "harness"
    return Path.home() / ".local" / "share" / "harness"

# adapters/claude/driver.py → adapters/ 를 sys.path에 추가해 base 임포트
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from base import Item, ItemNotFound, ProviderDriver  # noqa: E402


CLAUDE_HOME = Path.home() / ".claude"
MCP_JSON = CLAUDE_HOME / "mcp.json"
SKILLS_DIR = CLAUDE_HOME / "skills"
PLUGINS_JSON = CLAUDE_HOME / "plugins" / "installed_plugins.json"
SETTINGS_JSON = CLAUDE_HOME / "settings.json"

# harness 사이드 상태 — disabled MCP 백업
# XDG_DATA_HOME(또는 ~/.local/share/harness/) 아래에 보관.
# install.sh 가 ~/.harness 를 갈아엎어도 안전.
HARNESS_STATE_DIR = _harness_data_dir() / "state" / "claude"
MCP_BACKUP = HARNESS_STATE_DIR / "mcp_backup.json"

# skill disable 시 파일명 suffix
SKILL_DISABLED_SUFFIX = ".disabled"


def _parse_frontmatter(text: str) -> dict:
    """SKILL.md 의 YAML frontmatter 최소 파싱 (key: value 단일 라인만).

    PyYAML 의존 회피용. multi-line/리스트 미지원 — Phase 1에 필요한
    name/description/trigger 정도면 충분.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    block = text[3:end].strip()
    out: dict = {}
    for line in block.splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def _read_json(path: Path, default):
    """JSON 파일을 안전 읽기. 없거나 깨졌으면 default 반환."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write_json_atomic(path: Path, data) -> None:
    """원자적 JSON 쓰기 — tmp 파일 작성 후 rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


class ClaudeDriver(ProviderDriver):
    id = "claude"

    # ────────────────────── list ──────────────────────

    def list(self, kind: Optional[str] = None) -> list[Item]:
        items: list[Item] = []
        if kind in (None, "mcp"):
            items.extend(self._list_mcps())
        if kind in (None, "skill"):
            items.extend(self._list_skills())
        if kind in (None, "plugin"):
            items.extend(self._list_plugins())
        return items

    def _list_mcps(self) -> list[Item]:
        """mcp.json (enabled) + mcp_backup.json (disabled) 통합."""
        out: list[Item] = []
        # enabled
        active = _read_json(MCP_JSON, {}) or {}
        servers = active.get("mcpServers") or {}
        for name, cfg in servers.items():
            cfg = cfg or {}
            out.append(
                Item(
                    name=name,
                    provider=self.id,
                    kind="mcp",
                    enabled=True,
                    source=str(MCP_JSON),
                    meta={
                        "scope": "user",
                        "version": "",
                        "command": cfg.get("command", ""),
                        "args": cfg.get("args", []),
                    },
                )
            )
        # disabled (harness 백업에서 복원해 표시)
        backup = _read_json(MCP_BACKUP, {}) or {}
        for name, cfg in backup.items():
            cfg = cfg or {}
            out.append(
                Item(
                    name=name,
                    provider=self.id,
                    kind="mcp",
                    enabled=False,
                    source=str(MCP_BACKUP),
                    meta={
                        "scope": "user",
                        "version": "",
                        "command": cfg.get("command", ""),
                        "args": cfg.get("args", []),
                    },
                )
            )
        return out

    def _list_skills(self) -> list[Item]:
        """SKILL.md (enabled) + SKILL.md.disabled (disabled) 둘 다 인지."""
        if not SKILLS_DIR.exists():
            return []
        out: list[Item] = []
        for entry in sorted(SKILLS_DIR.iterdir()):
            if not entry.is_dir():
                continue
            skill_md = entry / "SKILL.md"
            disabled_md = entry / ("SKILL.md" + SKILL_DISABLED_SUFFIX)
            if skill_md.exists():
                target, enabled = skill_md, True
            elif disabled_md.exists():
                target, enabled = disabled_md, False
            else:
                continue
            try:
                head = target.read_text(encoding="utf-8", errors="replace")[:4096]
            except OSError:
                continue
            fm = _parse_frontmatter(head)
            out.append(
                Item(
                    name=fm.get("name", entry.name),
                    provider=self.id,
                    kind="skill",
                    enabled=enabled,
                    source=str(target),
                    meta={
                        "scope": "user",
                        "version": "",
                        "trigger": fm.get("trigger", ""),
                        "description": fm.get("description", ""),
                    },
                )
            )
        return out

    def _list_plugins(self) -> list[Item]:
        """installed_plugins.json + settings.json[enabledPlugins] 조합."""
        plugins_data = _read_json(PLUGINS_JSON, {}) or {}
        plugins = plugins_data.get("plugins") or {}
        settings = _read_json(SETTINGS_JSON, {}) or {}
        enabled_map = settings.get("enabledPlugins") or {}

        out: list[Item] = []
        for pid, installs in plugins.items():
            if not isinstance(installs, list) or not installs:
                continue
            top = installs[0]
            # enabledPlugins 에서 명시적 False 면 disabled. 키 없거나 True 면 enabled.
            enabled_val = enabled_map.get(pid, True)
            enabled = bool(enabled_val)
            out.append(
                Item(
                    name=pid,
                    provider=self.id,
                    kind="plugin",
                    enabled=enabled,
                    source=str(PLUGINS_JSON),
                    meta={
                        "version": top.get("version", ""),
                        "scope": top.get("scope", ""),
                        "install_path": top.get("installPath", ""),
                        "git_commit_sha": top.get("gitCommitSha", ""),
                        "installed_at": top.get("installedAt", ""),
                        "last_updated": top.get("lastUpdated", ""),
                        "project_path": top.get("projectPath", ""),
                    },
                )
            )
        return out

    # ────────────────────── disable ──────────────────────

    def disable(self, kind: str, name: str) -> bool:
        if kind == "mcp":
            return self._disable_mcp(name)
        if kind == "skill":
            return self._disable_skill(name)
        if kind == "plugin":
            return self._disable_plugin(name)
        raise ValueError(f"지원되지 않는 kind: {kind}")

    def _disable_mcp(self, name: str) -> bool:
        active = _read_json(MCP_JSON, {}) or {}
        servers = active.get("mcpServers") or {}
        backup = _read_json(MCP_BACKUP, {}) or {}
        if name in backup and name not in servers:
            return False  # 이미 disabled
        if name not in servers:
            raise ItemNotFound(f"MCP '{name}' 가 mcp.json 에 없음")
        # 백업 후 mcp.json 에서 제거
        backup[name] = servers.pop(name)
        active["mcpServers"] = servers
        _write_json_atomic(MCP_BACKUP, backup)
        _write_json_atomic(MCP_JSON, active)
        return True

    def _disable_skill(self, name: str) -> bool:
        skill_dir = self._find_skill_dir(name)
        if skill_dir is None:
            raise ItemNotFound(f"skill '{name}' 폴더를 찾을 수 없음")
        active = skill_dir / "SKILL.md"
        disabled = skill_dir / ("SKILL.md" + SKILL_DISABLED_SUFFIX)
        if disabled.exists() and not active.exists():
            return False  # 이미 disabled
        if not active.exists():
            raise ItemNotFound(f"skill '{name}' 의 SKILL.md 가 없음")
        os.rename(active, disabled)
        return True

    def _disable_plugin(self, name: str) -> bool:
        plugins_data = _read_json(PLUGINS_JSON, {}) or {}
        plugins = plugins_data.get("plugins") or {}
        if name not in plugins:
            raise ItemNotFound(f"plugin '{name}' 가 설치되어 있지 않음")
        settings = _read_json(SETTINGS_JSON, {}) or {}
        enabled_map = settings.setdefault("enabledPlugins", {})
        if enabled_map.get(name) is False:
            return False  # 이미 disabled
        enabled_map[name] = False
        _write_json_atomic(SETTINGS_JSON, settings)
        return True

    # ────────────────────── enable ──────────────────────

    def enable(self, kind: str, name: str) -> bool:
        if kind == "mcp":
            return self._enable_mcp(name)
        if kind == "skill":
            return self._enable_skill(name)
        if kind == "plugin":
            return self._enable_plugin(name)
        raise ValueError(f"지원되지 않는 kind: {kind}")

    def _enable_mcp(self, name: str) -> bool:
        active = _read_json(MCP_JSON, {}) or {}
        servers = active.get("mcpServers") or {}
        backup = _read_json(MCP_BACKUP, {}) or {}
        if name in servers and name not in backup:
            return False  # 이미 enabled
        if name not in backup:
            raise ItemNotFound(f"MCP '{name}' 백업이 없음 (disable 이력 없음)")
        servers[name] = backup.pop(name)
        active["mcpServers"] = servers
        _write_json_atomic(MCP_JSON, active)
        _write_json_atomic(MCP_BACKUP, backup)
        return True

    def _enable_skill(self, name: str) -> bool:
        skill_dir = self._find_skill_dir(name)
        if skill_dir is None:
            raise ItemNotFound(f"skill '{name}' 폴더를 찾을 수 없음")
        active = skill_dir / "SKILL.md"
        disabled = skill_dir / ("SKILL.md" + SKILL_DISABLED_SUFFIX)
        if active.exists() and not disabled.exists():
            return False  # 이미 enabled
        if not disabled.exists():
            raise ItemNotFound(f"skill '{name}' 의 SKILL.md.disabled 가 없음")
        os.rename(disabled, active)
        return True

    def _enable_plugin(self, name: str) -> bool:
        plugins_data = _read_json(PLUGINS_JSON, {}) or {}
        plugins = plugins_data.get("plugins") or {}
        if name not in plugins:
            raise ItemNotFound(f"plugin '{name}' 가 설치되어 있지 않음")
        settings = _read_json(SETTINGS_JSON, {}) or {}
        enabled_map = settings.get("enabledPlugins") or {}
        current = enabled_map.get(name, True)
        if current is True:
            return False  # 이미 enabled
        enabled_map[name] = True
        settings["enabledPlugins"] = enabled_map
        _write_json_atomic(SETTINGS_JSON, settings)
        return True

    # ────────────────────── helpers ──────────────────────

    def _find_skill_dir(self, name: str) -> Optional[Path]:
        """skill name 으로 폴더 찾기. frontmatter name이 매치되는 폴더 우선,
        없으면 폴더명이 매치되는 것."""
        if not SKILLS_DIR.exists():
            return None
        candidate_by_dirname: Optional[Path] = None
        for entry in SKILLS_DIR.iterdir():
            if not entry.is_dir():
                continue
            md = entry / "SKILL.md"
            disabled_md = entry / ("SKILL.md" + SKILL_DISABLED_SUFFIX)
            target = md if md.exists() else (disabled_md if disabled_md.exists() else None)
            if target is None:
                continue
            try:
                head = target.read_text(encoding="utf-8", errors="replace")[:4096]
            except OSError:
                continue
            fm = _parse_frontmatter(head)
            if fm.get("name") == name:
                return entry
            if entry.name == name:
                candidate_by_dirname = entry
        return candidate_by_dirname
