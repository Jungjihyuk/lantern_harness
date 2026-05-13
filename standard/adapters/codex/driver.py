"""Codex CLI provider driver.

읽는 위치:
  ~/.codex/config.toml             - 전역 설정 (model + plugins + mcp_servers + marketplaces)
  ~/.codex/skills/<name>/SKILL.md  - skill 정의 (Claude와 동일 형식)

쓰는 위치 (disable/enable 시):
  ~/.codex/config.toml             - mcp_servers 섹션 제거 / plugins.<id>.enabled 토글
  ~/.codex/skills/<name>/SKILL.md ↔ SKILL.md.disabled - rename

harness 사이드 상태:
  ${XDG_DATA_HOME}/harness/state/codex/mcp_backup.json - disabled MCP의 원본 설정 백업

자체 minimal TOML 파서 사용 (tomli/tomllib 외부 의존 없이).
Codex config.toml 에서 우리가 다루는 패턴만 지원:
  - 섹션 헤더 ([a.b], [plugins."name@source"])
  - 단순 key-value (string / bool / number / array)
  - 주석 (#)
미지원: inline table, multi-line string, dotted keys (단일 라인), array of tables.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

from lib.adapters.base import Item, ItemNotFound, ProviderDriver


# ───────────────────── 경로 ─────────────────────

CODEX_HOME = Path.home() / ".codex"
CONFIG_TOML = CODEX_HOME / "config.toml"
SKILLS_DIR = CODEX_HOME / "skills"


def _harness_data_dir() -> Path:
    """harness 의 사용자 데이터 디렉토리 (XDG Base Directory). claude driver와 동일."""
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / "harness"
    return Path.home() / ".local" / "share" / "harness"


HARNESS_STATE_DIR = _harness_data_dir() / "state" / "codex"
MCP_BACKUP = HARNESS_STATE_DIR / "mcp_backup.json"

# skill disable 시 파일명 suffix (claude와 동일)
SKILL_DISABLED_SUFFIX = ".disabled"


# ───────────────────── Minimal TOML 파서 ─────────────────────

_SECTION_RE = re.compile(r"^\s*\[([^\[\]]+)\]\s*$")


def _split_section_path(raw: str) -> list[str]:
    """`a.b."c.d".e` → `["a", "b", "c.d", "e"]` (따옴표 안의 dot은 분리하지 않음)."""
    parts: list[str] = []
    buf = ""
    in_quote = False
    for ch in raw.strip():
        if ch == '"':
            in_quote = not in_quote
            buf += ch
        elif ch == "." and not in_quote:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    return [p.strip().strip('"') for p in parts]


def _parse_value(raw: str) -> Any:
    """TOML 값을 Python 타입으로. 우리가 다루는 단순 케이스만."""
    raw = raw.strip()
    # 끝에 주석 붙어있으면 제거 (따옴표 밖 # 만)
    raw = _strip_trailing_comment(raw)
    if not raw:
        return ""
    # string
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    if raw == "true":
        return True
    if raw == "false":
        return False
    # array
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
        return [_parse_value(item) for item in _split_array(inner)]
    # number
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    # fallback (inline table 등 미지원 케이스는 raw 그대로 보관)
    return raw


def _strip_trailing_comment(raw: str) -> str:
    """따옴표 밖에 있는 # 부터 끝까지 제거."""
    in_quote = False
    quote_char = ""
    for i, ch in enumerate(raw):
        if ch in ('"', "'"):
            if not in_quote:
                in_quote = True
                quote_char = ch
            elif ch == quote_char:
                in_quote = False
        elif ch == "#" and not in_quote:
            return raw[:i].rstrip()
    return raw.rstrip()


def _split_array(text: str) -> list[str]:
    """배열 안쪽을 콤마로 분리 (따옴표 안 콤마 무시)."""
    parts: list[str] = []
    buf = ""
    in_quote = False
    quote_char = ""
    for ch in text:
        if ch in ('"', "'"):
            if not in_quote:
                in_quote = True
                quote_char = ch
            elif ch == quote_char:
                in_quote = False
            buf += ch
        elif ch == "," and not in_quote:
            if buf.strip():
                parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf.strip())
    return parts


def _parse_toml(text: str) -> dict:
    """Codex config.toml 의 minimal 파서.

    section 헤더와 key=value 라인만 인식. inline table / multi-line / array of tables 미지원.
    """
    root: dict = {}
    current: dict = root
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # [[array]] 는 우리가 다루지 않음 — skip
        if stripped.startswith("[[") and stripped.endswith("]]"):
            continue
        m = _SECTION_RE.match(line)
        if m:
            parts = _split_section_path(m.group(1))
            d = root
            for p in parts:
                d = d.setdefault(p, {})
            current = d
            continue
        if "=" in stripped:
            key, _, val = stripped.partition("=")
            key = key.strip().strip('"').strip("'")
            current[key] = _parse_value(val)
    return root


# ───────────────────── 파일 헬퍼 ─────────────────────


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write_json_atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# ───────────────────── frontmatter 파서 (Claude driver와 동일) ─────────────────────


def _parse_frontmatter(text: str) -> dict:
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


# ───────────────────── config.toml 섹션 line surgery ─────────────────────
# disable/enable 시 line-level 편집으로 다른 섹션·주석·formatting 보존.


def _section_header_line(name: str) -> str:
    """`mcp_servers.figma` 또는 `plugins."google-calendar@..."` 같은 섹션의 헤더 라인 생성."""
    return f"[{name}]"


def _normalize_section_header(line: str) -> Optional[str]:
    """`[ mcp_servers.figma ]` → `mcp_servers.figma`. 섹션 아니면 None."""
    s = line.strip()
    if not s.startswith("[") or not s.endswith("]"):
        return None
    if s.startswith("[[") or s.endswith("]]"):
        return None
    return s[1:-1].strip()


def _find_section_block(lines: list[str], section: str) -> Optional[tuple[int, int]]:
    """주어진 섹션의 [start_inclusive, end_exclusive) 라인 인덱스 반환. 못 찾으면 None.

    end_exclusive 는 다음 섹션 헤더 직전(연속된 공백 라인은 포함).
    """
    start = None
    for i, line in enumerate(lines):
        if _normalize_section_header(line) == section:
            start = i
            break
    if start is None:
        return None
    # 다음 섹션 헤더 또는 EOF 까지
    end = len(lines)
    for j in range(start + 1, len(lines)):
        header = _normalize_section_header(lines[j])
        if header is not None and header != section:
            end = j
            break
    # 끝쪽 공백 라인은 다음 섹션의 여백으로 남겨둠 (제거 시 이중 빈줄 방지)
    while end > start + 1 and lines[end - 1].strip() == "":
        end -= 1
    return (start, end)


def _toggle_bool_in_block(
    lines: list[str], start: int, end: int, key: str, target: bool
) -> bool:
    """[start, end) 범위 안에서 `<key> = true/false` 줄을 찾아 target 값으로 교체.

    교체했으면 True, 못 찾았으면 (그 자리에 추가하지 않고) False.
    """
    pat = re.compile(rf"^(\s*){re.escape(key)}\s*=\s*(true|false)\s*(#.*)?$")
    for i in range(start, end):
        m = pat.match(lines[i])
        if not m:
            continue
        indent, _, comment = m.group(1), m.group(2), m.group(3) or ""
        new_val = "true" if target else "false"
        suffix = f"  {comment}" if comment else ""
        lines[i] = f"{indent}{key} = {new_val}{suffix}".rstrip()
        return True
    return False


def _extract_section_kv(lines: list[str], start: int, end: int) -> dict:
    """[start+1, end) 범위의 단순 key=value 들을 파싱해 dict 반환 (mcp 백업용)."""
    body = "\n".join(lines[start + 1 : end])
    # 파서는 root 레벨로 인식하도록 섹션 헤더 없이 파싱
    return _parse_toml(body)


# ───────────────────── CodexDriver ─────────────────────


class CodexDriver(ProviderDriver):
    id = "codex"

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
        out: list[Item] = []
        # enabled: config.toml의 [mcp_servers.*] 섹션
        data = _parse_toml(_read_text(CONFIG_TOML))
        mcp_servers = data.get("mcp_servers") or {}
        for name, cfg in mcp_servers.items():
            cfg = cfg if isinstance(cfg, dict) else {}
            out.append(
                Item(
                    name=name,
                    provider=self.id,
                    kind="mcp",
                    enabled=True,
                    source=str(CONFIG_TOML),
                    meta={
                        "scope": "user",
                        "version": "",
                        "command": cfg.get("command", ""),
                        "args": cfg.get("args", []),
                        "url": cfg.get("url", ""),
                    },
                )
            )
        # disabled: harness 백업
        backup = _read_json(MCP_BACKUP, {}) or {}
        for name, cfg in backup.items():
            cfg = cfg if isinstance(cfg, dict) else {}
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
                        "url": cfg.get("url", ""),
                    },
                )
            )
        return out

    def _list_skills(self) -> list[Item]:
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
        data = _parse_toml(_read_text(CONFIG_TOML))
        plugins = data.get("plugins") or {}
        out: list[Item] = []
        for pid, cfg in plugins.items():
            cfg = cfg if isinstance(cfg, dict) else {}
            enabled = bool(cfg.get("enabled", True))
            out.append(
                Item(
                    name=pid,
                    provider=self.id,
                    kind="plugin",
                    enabled=enabled,
                    source=str(CONFIG_TOML),
                    meta={
                        "scope": "user",
                        "version": cfg.get("version", ""),
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
        text = _read_text(CONFIG_TOML)
        lines = text.splitlines(keepends=False)
        section = f"mcp_servers.{name}"
        block = _find_section_block(lines, section)
        backup = _read_json(MCP_BACKUP, {}) or {}
        if block is None:
            if name in backup:
                return False  # 이미 disabled
            raise ItemNotFound(f"MCP '{name}' 가 config.toml 에 없음")
        # 섹션 본문을 dict로 추출해 백업
        start, end = block
        kv = _extract_section_kv(lines, start, end)
        backup[name] = kv
        # config.toml 에서 섹션 제거 (헤더 + 본문)
        new_lines = lines[:start] + lines[end:]
        _write_text_atomic(CONFIG_TOML, "\n".join(new_lines) + ("\n" if text.endswith("\n") else ""))
        _write_json_atomic(MCP_BACKUP, backup)
        return True

    def _disable_skill(self, name: str) -> bool:
        skill_dir = self._find_skill_dir(name)
        if skill_dir is None:
            raise ItemNotFound(f"skill '{name}' 폴더를 찾을 수 없음")
        active = skill_dir / "SKILL.md"
        disabled = skill_dir / ("SKILL.md" + SKILL_DISABLED_SUFFIX)
        if disabled.exists() and not active.exists():
            return False
        if not active.exists():
            raise ItemNotFound(f"skill '{name}' 의 SKILL.md 가 없음")
        os.rename(active, disabled)
        return True

    def _disable_plugin(self, name: str) -> bool:
        text = _read_text(CONFIG_TOML)
        lines = text.splitlines(keepends=False)
        section = f'plugins."{name}"'
        block = _find_section_block(lines, section)
        if block is None:
            raise ItemNotFound(f"plugin '{name}' 가 config.toml 에 없음")
        start, end = block
        # enabled 라인 토글. 없으면 섹션 직후에 추가.
        if _toggle_bool_in_block(lines, start, end, "enabled", target=False):
            _write_text_atomic(CONFIG_TOML, "\n".join(lines) + ("\n" if text.endswith("\n") else ""))
            return True
        # enabled 라인이 없는 경우 — 새로 추가
        insert_at = start + 1
        lines.insert(insert_at, "enabled = false")
        _write_text_atomic(CONFIG_TOML, "\n".join(lines) + ("\n" if text.endswith("\n") else ""))
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
        backup = _read_json(MCP_BACKUP, {}) or {}
        text = _read_text(CONFIG_TOML)
        lines = text.splitlines(keepends=False)
        section = f"mcp_servers.{name}"
        block = _find_section_block(lines, section)
        if block is not None and name not in backup:
            return False  # 이미 enabled
        if name not in backup:
            raise ItemNotFound(f"MCP '{name}' 백업이 없음 (disable 이력 없음)")
        cfg = backup.pop(name)
        # config.toml 끝에 섹션 추가 (formatting: 빈 줄 + 헤더 + key=value 들)
        new_block = ["", f"[{section}]"] + _render_toml_kv(cfg)
        body = text
        if not body.endswith("\n"):
            body += "\n"
        body += "\n".join(new_block) + "\n"
        _write_text_atomic(CONFIG_TOML, body)
        _write_json_atomic(MCP_BACKUP, backup)
        return True

    def _enable_skill(self, name: str) -> bool:
        skill_dir = self._find_skill_dir(name)
        if skill_dir is None:
            raise ItemNotFound(f"skill '{name}' 폴더를 찾을 수 없음")
        active = skill_dir / "SKILL.md"
        disabled = skill_dir / ("SKILL.md" + SKILL_DISABLED_SUFFIX)
        if active.exists() and not disabled.exists():
            return False
        if not disabled.exists():
            raise ItemNotFound(f"skill '{name}' 의 SKILL.md.disabled 가 없음")
        os.rename(disabled, active)
        return True

    def _enable_plugin(self, name: str) -> bool:
        text = _read_text(CONFIG_TOML)
        lines = text.splitlines(keepends=False)
        section = f'plugins."{name}"'
        block = _find_section_block(lines, section)
        if block is None:
            raise ItemNotFound(f"plugin '{name}' 가 config.toml 에 없음")
        start, end = block
        # 현재 enabled 값을 확인 — 이미 true 면 no-op
        body_dict = _extract_section_kv(lines, start, end)
        current = body_dict.get("enabled", True)
        if current is True:
            return False
        # enabled 라인 토글 또는 추가
        if _toggle_bool_in_block(lines, start, end, "enabled", target=True):
            _write_text_atomic(CONFIG_TOML, "\n".join(lines) + ("\n" if text.endswith("\n") else ""))
            return True
        lines.insert(start + 1, "enabled = true")
        _write_text_atomic(CONFIG_TOML, "\n".join(lines) + ("\n" if text.endswith("\n") else ""))
        return True

    # ────────────────────── helpers ──────────────────────

    def _find_skill_dir(self, name: str) -> Optional[Path]:
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


# ───────────────────── TOML 쓰기 헬퍼 (단순 key=value 만) ─────────────────────


def _render_toml_value(v: Any) -> str:
    """파이썬 값 → TOML 표현. 단순 케이스만."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_render_toml_value(x) for x in v) + "]"
    if isinstance(v, str):
        # 큰따옴표 escape
        escaped = v.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    # fallback — 안전하게 문자열
    return f'"{v}"'


def _render_toml_kv(d: dict) -> list[str]:
    """dict → TOML key=value 라인들."""
    out = []
    for k, v in d.items():
        out.append(f"{k} = {_render_toml_value(v)}")
    return out
