#!/usr/bin/env python3
"""harness viz dashboard — 라이브 브라우저 대시보드.

http.server + Server-Sent Events. localhost only. 외부 의존 X (Mermaid.js는 CDN).

사용:
    python3 dashboard.py [--project-root <path>] [--port 7891]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

try:
    import yaml
except ImportError:
    sys.stderr.write("Error: PyYAML 필요\n")
    sys.exit(1)

# main.py의 viz 함수 재사용
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from main import (  # noqa: E402
    list_sessions,
    load_session_events,
    viz_bottleneck,
    viz_eval,
    viz_improve,
    viz_prompts,
    viz_subagents,
    viz_workflow,
)


PROJECT_ROOT: Path = Path.cwd()


def _set_path(d: dict, dotted: str, value):
    """'a.b.c' 식으로 dict에 값 설정. plugins처럼 list인 경우는 add/remove 토글."""
    keys = dotted.split(".")
    if dotted == "plugins":
        # value가 list of plugin names
        d["plugins"] = list(value or [])
        return
    cur = d
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    # boolean 변환
    if isinstance(value, str):
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        else:
            try:
                value = int(value)
            except ValueError:
                pass
    cur[keys[-1]] = value


def _get_config_summary(project_root: Path):
    p = project_root / ".harness" / "compose.yaml"
    if not p.is_file():
        return {"error": "compose.yaml not found"}
    try:
        cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return {"error": f"parse: {e}"}
    return {
        "mode": cfg.get("mode", "human-gated"),
        "plugins": cfg.get("plugins", []),
        "hooks": cfg.get("hooks", {}),
        "loop_detection": cfg.get("loop_detection", {}),
        "cognitive_guard": {
            "enabled": (cfg.get("cognitive_guard") or {}).get("enabled", True),
            "per_call": (cfg.get("cognitive_guard") or {}).get("per_call", {}),
            "per_session": (cfg.get("cognitive_guard") or {}).get("per_session", {}),
        },
        "stop_validation": {
            "enabled": (cfg.get("stop_validation") or {}).get("enabled", False),
            "on_fail": (cfg.get("stop_validation") or {}).get("on_fail", "warn"),
        },
    }


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>harness dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <style>
    * { box-sizing: border-box; }
    body { font-family: -apple-system, sans-serif; margin: 0; padding: 0; color: #222; background: #fafafa; }
    header { background: #2c3e50; color: white; padding: 0.7em 1em; display: flex; align-items: center; gap: 1em; }
    header h1 { margin: 0; font-size: 1.1em; }
    header .live { font-size: 0.8em; opacity: 0.9; }
    header .live::before { content: "● "; color: #2ecc71; }
    main { padding: 1em; max-width: 1100px; margin: auto; }
    nav { display: flex; gap: 0.3em; margin-bottom: 1em; }
    nav button { padding: 0.5em 1em; border: 1px solid #ccc; background: white; cursor: pointer; border-radius: 4px; }
    nav button.active { background: #34495e; color: white; border-color: #34495e; }
    .panel { background: white; padding: 1em; border-radius: 6px; border: 1px solid #e0e0e0; }
    .meta { color: #777; font-size: 0.85em; margin-bottom: 0.8em; }
    pre.mermaid { background: #fafafa; padding: 1em; border-radius: 4px; overflow-x: auto; }
    select { padding: 0.3em 0.5em; }
    .config-panel { margin-top: 1.5em; padding: 1em; background: #f9f9f9; border: 1px solid #e5e5e5; border-radius: 6px; }
    .config-panel h3 { margin-top: 0; font-size: 1em; color: #444; }
    .config-row { display: flex; align-items: center; gap: 1em; padding: 0.3em 0; }
    .config-row label { min-width: 180px; font-size: 0.9em; }
    .config-row input[type=number] { width: 100px; padding: 0.2em 0.4em; }
    .config-row .saved { color: #27ae60; font-size: 0.8em; }
    .config-row .err { color: #c0392b; font-size: 0.8em; }
    table { border-collapse: collapse; width: 100%; margin-top: 0.8em; }
    th, td { border: 1px solid #e0e0e0; padding: 0.4em 0.6em; text-align: left; }
    th { background: #f4f4f4; }
    td.num { text-align: right; font-variant-numeric: tabular-nums; }
  </style>
</head>
<body>
  <header>
    <h1>harness dashboard</h1>
    <span class="live" id="status">connecting...</span>
    <span style="margin-left:auto">session:
      <select id="session"></select>
    </span>
  </header>
  <main>
    <nav>
      <button class="active" data-tab="workflow">Workflow</button>
      <button data-tab="subagents">Subagents</button>
      <button data-tab="bottleneck">Bottleneck</button>
      <button data-tab="eval">Eval</button>
      <button data-tab="improve">Improve</button>
      <button data-tab="prompts">Prompts</button>
    </nav>
    <div class="panel" id="content">로딩 중...</div>
  </main>

  <script>
    mermaid.initialize({ startOnLoad: false, theme: 'default' });

    let currentTab = 'workflow';
    let currentSession = null;

    async function loadSessions() {
      const r = await fetch('/api/sessions');
      const list = await r.json();
      const sel = document.getElementById('session');
      sel.innerHTML = list.map(s => `<option value="${s.id}">${s.label}</option>`).join('');
      if (list.length && !currentSession) currentSession = list[0].id;
      sel.value = currentSession || '';
    }

    async function loadViz() {
      if (!currentSession) {
        document.getElementById('content').innerHTML = '(세션 없음)';
        return;
      }
      const r = await fetch(`/api/viz?type=${currentTab}&session=${encodeURIComponent(currentSession)}`);
      const j = await r.json();
      render(j);
    }

    function render(j) {
      const el = document.getElementById('content');
      const meta = `<div class="meta">type: ${j.viz_type} · session: ${j.session_id}</div>`;
      let body = '';
      if (j.data && j.data.mermaid) {
        body += `<pre class="mermaid">${j.data.mermaid}</pre>`;
      }
      if (j.viz_type === 'bottleneck' && j.data.rows && j.data.rows.length) {
        body += '<table><thead><tr><th>tool</th><th>calls</th><th>total ms</th><th>avg ms</th><th>max ms</th></tr></thead><tbody>';
        for (const r of j.data.rows) {
          body += `<tr><td>${r.name}</td><td class="num">${r.calls}</td><td class="num">${r.total_ms}</td><td class="num">${r.avg_ms}</td><td class="num">${r.max_ms}</td></tr>`;
        }
        body += '</tbody></table>';
      }
      if (j.viz_type === 'subagents' && j.data.calls && j.data.calls.length) {
        body += '<table><thead><tr><th>ts</th><th>subagent</th><th>description</th><th>ms</th></tr></thead><tbody>';
        for (const c of j.data.calls) {
          body += `<tr><td>${c.ts}</td><td>${c.subagent_type}</td><td>${c.description}</td><td class="num">${c.duration_ms}</td></tr>`;
        }
        body += '</tbody></table>';
      }
      if (j.viz_type === 'eval') {
        if (j.data.no_data) {
          body += '<p>(eval 결과 없음 — <code>harness eval run</code> 먼저 실행)</p>';
        } else {
          if (j.data.regressions && j.data.regressions.length) {
            body += '<h3 style="color:#c0392b">⚠ Regression 감지</h3><ul>';
            for (const r of j.data.regressions) {
              body += `<li>${r.between[0].slice(0,19)} → ${r.between[1].slice(0,19)}: ${r.newly_failing.join(', ')}</li>`;
            }
            body += '</ul>';
          }
          if (j.data.runs && j.data.runs.length) {
            body += '<h3>최근 실행 (마지막 10회)</h3>';
            body += '<table><thead><tr><th>timestamp</th><th>passed</th><th>failed</th><th>skipped</th><th>total</th></tr></thead><tbody>';
            for (const r of j.data.runs) {
              const cls = r.failed > 0 ? ' style="background:#fdecea"' : '';
              body += `<tr${cls}><td>${r.ts}</td><td class="num">${r.passed}</td><td class="num">${r.failed}</td><td class="num">${r.skipped}</td><td class="num">${r.total}</td></tr>`;
            }
            body += '</tbody></table>';
            // 최신 결과 상세
            const last = j.data.runs[j.data.runs.length-1];
            if (last && last.results) {
              body += '<h3>최신 결과 상세</h3><table><thead><tr><th>case</th><th>status</th></tr></thead><tbody>';
              for (const c of last.results) {
                const sym = c.skipped ? '⊙' : (c.passed ? '✓' : '✗');
                const cls = c.skipped ? '' : (c.passed ? '' : ' style="color:#c0392b"');
                body += `<tr${cls}><td>${c.id}</td><td>${sym} ${c.passed ? 'pass' : (c.skipped ? 'skip' : 'fail')}</td></tr>`;
              }
              body += '</tbody></table>';
            }
          }
        }
      }
      if (j.viz_type === 'prompts') {
        if (j.data.error) {
          body += `<p style="color:#c0392b">분석 실패: ${j.data.error}</p>`;
        } else {
          const rows = j.data.rows || [];
          if (!rows.length) {
            body += '<p>(prompt 데이터 없음 — user_prompt_submit hook이 fire한 후 쌓임)</p>';
          } else {
            const sorted = rows.slice().sort((a,b) => (b.struggle_score||0) - (a.struggle_score||0)).slice(0, 30);
            body += '<h3>Prompt별 헤맴 점수 (상위 30, 점수 = denies×2 + retries×3 + 시간/10 + bypass)</h3>';
            body += '<table><thead><tr><th>ts</th><th>struggle</th><th>judge</th><th>tool</th><th>deny</th><th>retry</th><th>bypass</th><th>dur(s)</th><th>prompt</th></tr></thead><tbody>';
            for (const r of sorted) {
              const score = r.struggle_score || 0;
              let bg = '';
              if (score >= 30) bg = ' style="background:#fdecea"';
              else if (score >= 10) bg = ' style="background:#fff8e1"';
              const promptShort = (r.prompt || '').slice(0, 80).replace(/\n/g,' ');
              const judgeS = (r.judge_score !== undefined && r.judge_score !== null) ? r.judge_score : '-';
              const fb = r.judge_feedback ? ` title="${(r.judge_feedback||'').replace(/"/g,'&quot;')}"` : '';
              body += `<tr${bg}><td>${(r.ts||'').slice(0,19)}</td><td class="num"><b>${score}</b></td><td class="num"${fb}>${judgeS}</td><td class="num">${r.tool_calls||0}</td><td class="num">${r.denies||0}</td><td class="num">${r.retries||0}</td><td class="num">${r.bypass||0}</td><td class="num">${r.duration_s||0}</td><td>${promptShort}</td></tr>`;
            }
            body += '</tbody></table>';
            body += '<p style="font-size:0.85em; color:#666; margin-top:1em">붉은 배경 = 매우 헤맴 (점수 ≥ 30), 노란 = 약간 헤맴 (≥ 10). judge 컬럼은 LLM-as-judge 점수 (hover 시 피드백) — <code>harness judge run</code>으로 채움.</p>';
          }
        }
      }
      if (j.viz_type === 'improve') {
        if (j.data.error) {
          body += `<p style="color:#c0392b">분석 실패: ${j.data.error}</p>`;
        } else {
          const dec = j.data.summary.decisions || {};
          const trc = j.data.summary.traces || {};
          const ev = j.data.summary.eval || {};
          body += '<h3>📊 사용 패턴</h3><ul>';
          body += `<li>분석 세션: ${dec.sessions || 0} (decisions) / ${trc.sessions || 0} (traces)</li>`;
          body += `<li>총 결정: ${dec.total_decisions || 0} (allow ${(dec.summary||{}).allow||0}, deny ${(dec.summary||{}).deny_self_correct||0})</li>`;
          body += `<li>bypass marker 사용: ${dec.bypass_count || 0}회</li>`;
          if (ev.runs) body += `<li>eval 실행: ${ev.runs}회</li>`;
          body += '</ul>';

          const sugs = j.data.suggestions || [];
          if (sugs.length) {
            body += '<h3>⚠ 잠재 개선 제안</h3>';
            for (let i = 0; i < sugs.length; i++) {
              const s = sugs[i];
              body += `<div style="border:1px solid #ddd; border-radius:4px; padding:0.7em; margin:0.5em 0; background:#fff8e1">`;
              body += `<strong>${i+1}. ${s.title}</strong><br>`;
              body += `<small>근거: ${s.evidence}</small><br>`;
              body += `<small>권장: ${s.recommend}</small><br>`;
              if (s.yaml_path) body += `<small>위치: <code>${s.yaml_path}</code></small>`;
              body += '</div>';
            }
            body += '<p><small>자동 적용 X — compose.yaml을 직접 편집하세요.</small></p>';
          } else {
            body += '<p>✓ 특이 권고 없음 (데이터 부족 또는 모든 임계값 적정)</p>';
          }
        }
      }
      // Workflow 탭에 설정 컨트롤 추가
      if (j.viz_type === 'workflow') {
        body += '<div class="config-panel" id="config-panel">로딩 중...</div>';
      }

      el.innerHTML = meta + body;
      if (j.data && j.data.mermaid) {
        mermaid.run({ querySelector: '.mermaid' });
      }
      if (j.viz_type === 'workflow') {
        loadConfigPanel();
      }
    }

    async function loadConfigPanel() {
      const r = await fetch('/api/config');
      const cfg = await r.json();
      const el = document.getElementById('config-panel');
      if (!el) return;
      if (cfg.error) {
        el.innerHTML = `<p>config 로드 실패: ${cfg.error}</p>`;
        return;
      }
      let html = '<h3>⚙ 설정 — 변경 시 compose.yaml 즉시 반영 (백업 자동)</h3>';

      // mode
      html += `<div class="config-row">
        <label>mode</label>
        <select data-config-path="mode">
          <option ${cfg.mode==='human-gated'?'selected':''}>human-gated</option>
          <option ${cfg.mode==='ralph'?'selected':''}>ralph</option>
        </select>
        <span class="status"></span>
      </div>`;

      // hooks 토글
      html += '<h4 style="margin-top:1em">Hooks</h4>';
      const hookNames = ['session_start', 'user_prompt_submit', 'pre_tool_use', 'post_tool_use', 'stop'];
      for (const h of hookNames) {
        const v = cfg.hooks[h] || 'enabled';
        html += `<div class="config-row">
          <label>${h}</label>
          <input type="checkbox" data-config-path="hooks.${h}"
                 data-true="enabled" data-false="disabled"
                 ${v==='enabled'?'checked':''}>
          <span class="status"></span>
        </div>`;
      }

      // loop_detection
      const ld = cfg.loop_detection || {};
      html += '<h4 style="margin-top:1em">Loop Detection</h4>';
      html += `<div class="config-row">
        <label>enabled</label>
        <input type="checkbox" data-config-path="loop_detection.enabled" data-true="true" data-false="false" ${ld.enabled?'checked':''}>
        <span class="status"></span>
      </div>`;
      html += `<div class="config-row">
        <label>consecutive_same_path</label>
        <input type="number" min="2" max="20" value="${ld.consecutive_same_path || 3}" data-config-path="loop_detection.consecutive_same_path">
        <span class="status"></span>
      </div>`;
      html += `<div class="config-row">
        <label>on_loop</label>
        <select data-config-path="loop_detection.on_loop">
          <option ${ld.on_loop==='self_correct'?'selected':''}>self_correct</option>
          <option ${ld.on_loop==='hard_stop'?'selected':''}>hard_stop</option>
        </select>
        <span class="status"></span>
      </div>`;

      // cognitive_guard
      const cg = cfg.cognitive_guard || {};
      const pc = cg.per_call || {};
      const ps = cg.per_session || {};
      html += '<h4 style="margin-top:1em">Cognitive Guard</h4>';
      html += `<div class="config-row">
        <label>per_call.max_diff_lines</label>
        <input type="number" min="10" value="${pc.max_diff_lines || 200}" data-config-path="cognitive_guard.per_call.max_diff_lines">
        <span class="status"></span>
      </div>`;
      html += `<div class="config-row">
        <label>per_call.max_new_files</label>
        <input type="number" min="1" value="${pc.max_new_files || 3}" data-config-path="cognitive_guard.per_call.max_new_files">
        <span class="status"></span>
      </div>`;
      html += `<div class="config-row">
        <label>per_session.max_changed_files</label>
        <input type="number" min="1" value="${ps.max_changed_files || 10}" data-config-path="cognitive_guard.per_session.max_changed_files">
        <span class="status"></span>
      </div>`;
      html += `<div class="config-row">
        <label>per_session.max_diff_lines</label>
        <input type="number" min="10" value="${ps.max_diff_lines || 1000}" data-config-path="cognitive_guard.per_session.max_diff_lines">
        <span class="status"></span>
      </div>`;

      // stop_validation
      const pcomp = cfg.stop_validation || {};
      html += '<h4 style="margin-top:1em">Stop Validation</h4>';
      html += `<div class="config-row">
        <label>enabled</label>
        <input type="checkbox" data-config-path="stop_validation.enabled" data-true="true" data-false="false" ${pcomp.enabled?'checked':''}>
        <span class="status"></span>
      </div>`;
      html += `<div class="config-row">
        <label>on_fail</label>
        <select data-config-path="stop_validation.on_fail">
          <option ${pcomp.on_fail==='warn'?'selected':''}>warn</option>
          <option ${pcomp.on_fail==='block'?'selected':''}>block</option>
        </select>
        <span class="status"></span>
      </div>`;

      html += '<p style="font-size:0.85em; color:#666; margin-top:1em">변경은 즉시 compose.yaml에 저장됨. 새 claude 세션부터 적용.</p>';

      el.innerHTML = html;

      // 변경 핸들러
      el.querySelectorAll('[data-config-path]').forEach(input => {
        input.addEventListener('change', async (e) => {
          const path = input.dataset.configPath;
          let value;
          if (input.type === 'checkbox') {
            value = input.checked ? input.dataset.true : input.dataset.false;
          } else {
            value = input.value;
          }
          const status = input.parentElement.querySelector('.status');
          status.className = 'status';
          status.textContent = '저장중…';
          const resp = await fetch('/api/config-update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({path, value})
          });
          const data = await resp.json();
          if (data.ok) {
            status.className = 'saved';
            status.textContent = '✓ 저장됨';
            setTimeout(() => { status.textContent = ''; }, 2000);
            // 변경 즉시 workflow 다이어그램 재로드 (disabled hook 시각 반영)
            if (currentTab === 'workflow') {
              setTimeout(() => loadViz(), 200);
            }
          } else {
            status.className = 'err';
            status.textContent = '✗ ' + (data.error || 'error');
          }
        });
      });
    }

    document.querySelectorAll('nav button').forEach(b => {
      b.addEventListener('click', () => {
        document.querySelectorAll('nav button').forEach(x => x.classList.remove('active'));
        b.classList.add('active');
        currentTab = b.dataset.tab;
        loadViz();
      });
    });
    document.getElementById('session').addEventListener('change', e => {
      currentSession = e.target.value;
      loadViz();
    });

    // SSE 라이브 갱신
    const sse = new EventSource('/events');
    sse.onopen = () => { document.getElementById('status').textContent = 'live'; };
    sse.onerror = () => { document.getElementById('status').textContent = 'disconnected'; };
    sse.onmessage = (e) => {
      // 어떤 trace이든 업데이트되면 viz 새로고침
      loadSessions().then(loadViz);
    };

    loadSessions().then(loadViz);
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 콘솔 노이즈 줄이기
        return

    def _json(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/api/config-update":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
        except Exception:
            return self._json(400, {"error": "invalid JSON"})

        path = payload.get("path", "")
        value = payload.get("value")
        if not path:
            return self._json(400, {"error": "path required"})

        active_path = PROJECT_ROOT / ".harness" / "compose.yaml"
        if not active_path.is_file():
            return self._json(404, {"error": "compose.yaml not found"})

        # 허용된 path만 허용 (안전)
        allowed_prefixes = (
            "mode",
            "hooks.",
            "plugins",
            "loop_detection.enabled",
            "loop_detection.consecutive_same_path",
            "loop_detection.on_loop",
            "cognitive_guard.enabled",
            "cognitive_guard.per_call.max_diff_lines",
            "cognitive_guard.per_call.max_new_files",
            "cognitive_guard.per_session.max_changed_files",
            "cognitive_guard.per_session.max_diff_lines",
            "stop_validation.enabled",
            "stop_validation.on_fail",
        )
        if not any(path == p or path.startswith(p) for p in allowed_prefixes):
            return self._json(403, {"error": f"path '{path}' not editable from dashboard"})

        # 백업
        backup = active_path.with_suffix(".yaml.bak." + datetime.now().strftime("%s"))
        shutil.copy(active_path, backup)

        try:
            cfg = yaml.safe_load(active_path.read_text(encoding="utf-8")) or {}
            _set_path(cfg, path, value)
            active_path.write_text(
                yaml.safe_dump(cfg, default_flow_style=False, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
        except Exception as e:
            shutil.copy(backup, active_path)
            return self._json(500, {"error": f"update failed (rolled back): {e}"})

        return self._json(200, {"ok": True, "backup": str(backup), "path": path, "value": value})

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/" or u.path == "/index.html":
            body = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if u.path == "/api/config":
            return self._json(200, _get_config_summary(PROJECT_ROOT))

        if u.path == "/api/sessions":
            sessions = list_sessions(PROJECT_ROOT)
            return self._json(200, [
                {"id": sid, "label": f"{sid[:8]}… ({time.strftime('%Y-%m-%d %H:%M', time.localtime(mt))})"}
                for sid, mt in sessions
            ])

        if u.path == "/api/viz":
            qs = parse_qs(u.query)
            vtype = (qs.get("type") or ["workflow"])[0]
            sid = (qs.get("session") or [None])[0]
            if vtype in ("eval", "improve", "prompts"):
                # 세션 무관, 프로젝트 전체 분석
                if vtype == "eval":
                    data = viz_eval(PROJECT_ROOT)
                elif vtype == "improve":
                    data = viz_improve(PROJECT_ROOT)
                else:
                    data = viz_prompts(PROJECT_ROOT)
                return self._json(200, {"viz_type": vtype, "session_id": "all", "data": data})
            events, sid, _ = load_session_events(PROJECT_ROOT, sid)
            if vtype == "workflow":
                data = viz_workflow(events, live=True, project_root=PROJECT_ROOT)
            elif vtype == "subagents":
                data = viz_subagents(events)
            elif vtype == "bottleneck":
                data = viz_bottleneck(events)
            else:
                return self._json(400, {"error": "unknown viz type"})
            return self._json(200, {"viz_type": vtype, "session_id": sid, "data": data})

        if u.path == "/events":
            # SSE: traces 디렉토리 mtime 변화 감지 시 핑
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            traces = PROJECT_ROOT / ".harness" / "runtime" / "traces"
            last = 0.0
            try:
                while True:
                    cur = max([f.stat().st_mtime for f in traces.glob("*.jsonl")] or [0.0])
                    if cur > last:
                        last = cur
                        try:
                            self.wfile.write(b"data: update\n\n")
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            break
                    time.sleep(1.0)
            except Exception:
                pass
            return

        self.send_response(404)
        self.end_headers()


def main():
    global PROJECT_ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=os.getcwd())
    parser.add_argument("--port", type=int, default=7891)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    PROJECT_ROOT = Path(args.project_root).resolve()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"🚀 harness dashboard at {url}")
    print(f"   project: {PROJECT_ROOT}")
    print(f"   trace source: {PROJECT_ROOT}/.harness/runtime/traces/")
    print("   Ctrl-C to stop.")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping…")
        server.shutdown()


if __name__ == "__main__":
    main()
