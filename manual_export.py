"""手动导航 + 自动监听 API 导出测验（不再自动乱点）."""
import json
import msvcrt
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_util import OLD_SESSION, TEMP_SESSION, launch_logged_in_context, open_portal_page
from page_extract import API_PATHS, FETCH_HOOK_JS, FIND_QUES_JS, SINGLE_FRAME_EXTRACT_JS

ROOT = Path(__file__).parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

import export_homework as eh

GUIDE_HTML = """
<div id="__guide" style="position:fixed;top:12px;left:12px;z-index:2147483647;background:#fff;border:2px solid #1677ff;
padding:0;border-radius:10px;font-size:14px;line-height:1.7;max-width:340px;box-shadow:0 4px 16px rgba(0,0,0,.15);user-select:none;">
<div id="__guide_handle" style="cursor:move;background:#1677ff;color:#fff;padding:8px 12px;border-radius:8px 8px 0 0;font-size:13px;">
<b>导出助手</b> <span style="opacity:.85;font-weight:normal;">— 按住此处拖动</span>
</div>
<div style="padding:10px 14px 14px;">
1. 进入<b>测验详情</b>（能看到题目+正确答案）<br>
<button id="__export_page_btn" type="button" style="margin-top:8px;width:100%;padding:10px;border:none;border-radius:6px;background:#52c41a;color:#fff;font-size:14px;font-weight:bold;cursor:pointer;">导出当前页</button>
<button id="__scan_cache_btn" type="button" style="margin-top:6px;width:100%;padding:8px;border:none;border-radius:6px;background:#1677ff;color:#fff;font-size:13px;cursor:pointer;">从缓存重新扫描</button>
<div id="__guide_status" style="margin-top:8px;padding:6px 8px;background:#fff7e6;border:1px solid #ffd591;border-radius:6px;font-size:12px;color:#ad6800;">等待操作…</div>
</div>
</div>
""".strip()

UI_INIT_JS = """
window.__showExportToast = (msg) => {
    let t = document.getElementById('__export_toast');
    if (!t) {
        t = document.createElement('div');
        t.id = '__export_toast';
        t.style.cssText = 'position:fixed;bottom:20px;left:20px;z-index:2147483647;background:#52c41a;color:#fff;padding:12px 18px;border-radius:8px;font-size:15px;max-width:380px;';
        document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.display = 'block';
    setTimeout(() => { t.style.display = 'none'; }, 8000);
};
window.__updateGuideStatus = (msg) => {
    const el = document.getElementById('__guide_status');
    if (el) el.textContent = msg;
};
"""


def _guide_script() -> str:
    html = json.dumps(GUIDE_HTML)
    return f"""
(function() {{
    {UI_INIT_JS}
    if (document.getElementById('__guide')) return;
    document.body.insertAdjacentHTML('beforeend', {html});
    const box = document.getElementById('__guide');
    const handle = document.getElementById('__guide_handle');
    const bindBtn = (id, pendingKey) => {{
        const btn = document.getElementById(id);
        if (!btn || btn.__hooked) return;
        btn.__hooked = true;
        btn.addEventListener('click', (e) => {{
            e.preventDefault();
            e.stopPropagation();
            window[pendingKey] = Date.now();
            window.__updateGuideStatus('正在处理…');
            window.__showExportToast('收到点击，正在导出…');
        }});
    }};
    bindBtn('__export_page_btn', '__export_page_pending');
    bindBtn('__scan_cache_btn', '__scan_cache_pending');
    const key = '__guide_pos';
    try {{
        const saved = JSON.parse(sessionStorage.getItem(key) || 'null');
        if (saved && saved.left != null) {{
            box.style.left = saved.left + 'px';
            box.style.top = saved.top + 'px';
            box.style.right = 'auto';
        }}
    }} catch (e) {{}}
    let dragging = false, ox = 0, oy = 0;
    const start = (e) => {{
        dragging = true;
        const r = box.getBoundingClientRect();
        const p = e.touches ? e.touches[0] : e;
        ox = p.clientX - r.left;
        oy = p.clientY - r.top;
        box.style.right = 'auto';
        e.preventDefault();
    }};
    const move = (e) => {{
        if (!dragging) return;
        const p = e.touches ? e.touches[0] : e;
        const x = Math.max(0, Math.min(p.clientX - ox, window.innerWidth - box.offsetWidth));
        const y = Math.max(0, Math.min(p.clientY - oy, window.innerHeight - 40));
        box.style.left = x + 'px';
        box.style.top = y + 'px';
        e.preventDefault();
    }};
    const end = () => {{
        if (!dragging) return;
        dragging = false;
        try {{
            sessionStorage.setItem(key, JSON.stringify({{
                left: parseInt(box.style.left, 10) || 12,
                top: parseInt(box.style.top, 10) || 12
            }}));
        }} catch (e) {{}}
    }};
    handle.addEventListener('mousedown', start);
    handle.addEventListener('touchstart', start, {{passive: false}});
    window.addEventListener('mousemove', move);
    window.addEventListener('touchmove', move, {{passive: false}});
    window.addEventListener('mouseup', end);
    window.addEventListener('touchend', end);
}})();
"""


def try_parse_resp_json(resp) -> dict | list | None:
    try:
        if resp.status != 200:
            return None
        body = resp.text()
        if not body or not body.strip().startswith(("{", "[")):
            return None
        return json.loads(body)
    except Exception:
        return None


def extract_quiz_result(data) -> dict | None:
    if not isinstance(data, dict):
        return None
    r = data.get("result")
    if isinstance(r, dict) and isinstance(r.get("quesList"), list) and r["quesList"]:
        return r

    def walk(obj):
        if isinstance(obj, dict):
            ql = obj.get("quesList")
            if isinstance(ql, list) and ql and isinstance(ql[0], dict) and "title" in ql[0]:
                return obj
            for v in obj.values():
                found = walk(v)
                if found:
                    return found
        elif isinstance(obj, list):
            for v in obj:
                found = walk(v)
                if found:
                    return found
        return None

    return walk(data)


def cache_dirs() -> list[Path]:
    dirs = []
    for base in (OLD_SESSION, TEMP_SESSION):
        d = base / "Default" / "Cache" / "Cache_Data"
        if d.exists():
            dirs.append(d)
    return dirs


def redact_url(url: str) -> str:
    if not url:
        return ""
    redacted = re.sub(r"[a-f0-9]{24}", "[id]", url)
    return redacted.split("?", 1)[0]


def scan_cache(saved: set) -> list[tuple[str, dict]]:
    found = []
    seen_titles = set()
    for cache_dir in cache_dirs():
        for f in cache_dir.glob("f_*"):
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
                if "quesList" not in text:
                    continue
                data = json.loads(text)
                result = extract_quiz_result(data)
                if not result:
                    continue
                title = result.get("title") or f"unknown_{f.name}"
                if title in seen_titles or title in saved:
                    continue
                seen_titles.add(title)
                found.append((title, result))
            except Exception:
                pass
    return found


def save_quiz(title: str, result: dict) -> Path:
    qs = [eh.format_question(q) for q in result["quesList"]]
    safe = re.sub(r'[\\/:*?"<>|]', "_", title)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md = OUT / f"{safe}_{ts}.md"
    js = OUT / f"{safe}_{ts}.json"
    payload = {"title": title, "exported_at": datetime.now().isoformat(), "questions": qs}
    js.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# {title}", "", f"- 题目数量: {len(qs)}", ""]
    for q in qs:
        lines += [f"## 第 {q['sort']} 题 ({q['type']})", "", q["title"], ""]
        if q["options"]:
            for i, opt in enumerate(q["options"]):
                if opt:
                    lines.append(f"- {chr(65 + i)}. {opt}")
            lines.append("")
        lines += [f"**正确答案:** {q['correct_answer']}", f"**你的作答:** {q['your_answer']}", ""]
    md.write_text("\n".join(lines), encoding="utf-8")
    return md


def notify_all_pages(ctx, msg: str, status: str | None = None):
    for pg in ctx.pages:
        try:
            pg.evaluate(
                """([msg, status]) => {
                    if (window.__showExportToast) window.__showExportToast(msg);
                    if (status && window.__updateGuideStatus) window.__updateGuideStatus(status);
                }""",
                [msg, status or ""],
            )
        except Exception:
            pass


def export_result(saved: set, exports: list, result: dict, source: str, ctx) -> bool:
    title = result.get("title") or "未命名测验"
    title = re.sub(r"<[^>]+>", "", str(title)).strip()
    if title in saved:
        return False
    saved.add(title)
    md = save_quiz(title, result)
    exports.append({"title": title, "file": str(md.relative_to(ROOT)), "count": len(result["quesList"]), "source": source})
    print(f"已导出: {title} ({len(result['quesList'])} 题) [{source}]")
    status = f"已导出 {len(exports)} 份，最近: {title}"
    notify_all_pages(ctx, f"已导出: {title} ({len(result['quesList'])}题)", status)
    return True


def pick_best_result(results: list[dict | None]) -> dict | None:
    best = None
    for r in results:
        if not r or not r.get("quesList"):
            continue
        if not best or len(r["quesList"]) > len(best["quesList"]):
            best = r
    return best


def extract_from_page(pg) -> dict | None:
    results = []
    try:
        results.append(pg.evaluate(FIND_QUES_JS))
    except Exception:
        pass
    for frame in pg.frames:
        try:
            results.append(frame.evaluate(SINGLE_FRAME_EXTRACT_JS))
        except Exception:
            pass
    return pick_best_result(results)


def try_api_refetch(pg, ctx) -> dict | None:
    url = pg.url or ""
    if "previewHomework" not in url and "previewExam" not in url and "workexam" not in url:
        return None
    ids = re.findall(r"[a-f0-9]{24}", url)
    if not ids:
        return None
    params_list = [
        {"workExamId": ids[0], "stuWorkExamId": ids[1] if len(ids) > 1 else ids[0]},
        {"workExamId": ids[0]},
        {"stuWorkExamId": ids[0]},
        {"id": ids[0]},
        {"homeworkId": ids[0]},
    ]
    for base in API_PATHS:
        for params in params_list:
            try:
                resp = ctx.request.get(base, params=params, timeout=15000)
                if resp.status != 200:
                    continue
                data = resp.json()
                result = extract_quiz_result(data)
                if result:
                    return result
            except Exception:
                pass
    return None


def try_export_from_pages(ctx, saved: set, exports: list, source: str = "page") -> dict:
    exported = []
    debug = []
    for pg in ctx.pages:
        url = pg.url or ""
        if "about:blank" in url:
            continue
        result = extract_from_page(pg)
        if not result:
            result = try_api_refetch(pg, ctx)
            if result:
                source = "api-refetch"
        if result and result.get("quesList"):
            if export_result(saved, exports, result, source, ctx):
                exported.append(re.sub(r"<[^>]+>", "", str(result.get("title") or "当前测验")).strip())
        else:
            try:
                debug.append({"url": redact_url(url), "frames": len(pg.frames)})
            except Exception as e:
                debug.append({"url": redact_url(url), "error": str(e)})
    if debug and not exported:
        (OUT / "export_debug.json").write_text(json.dumps(debug, ensure_ascii=False, indent=2), encoding="utf-8")
    if exported:
        return {"ok": True, "exported": exported, "total": len(exports)}
    return {"ok": False, "msg": "未找到题目。请确认在测验详情页，或刷新页面后再点绿色按钮"}


def poll_pending_buttons(ctx, saved, exports, do_cache_scan, do_export_page):
    for pg in ctx.pages:
        try:
            flags = pg.evaluate(
                """() => ({
                    export: window.__export_page_pending || 0,
                    scan: window.__scan_cache_pending || 0
                })"""
            )
        except Exception:
            continue
        if flags.get("scan"):
            pg.evaluate("() => { window.__scan_cache_pending = 0; }")
            do_cache_scan()
        if flags.get("export"):
            pg.evaluate("() => { window.__export_page_pending = 0; }")
            do_export_page()


def main():
    saved = set()
    exports = []
    api_hits = 0

    with sync_playwright() as p:
        ctx = launch_logged_in_context(p)
        guide_js = _guide_script()
        ctx.add_init_script(FETCH_HOOK_JS + UI_INIT_JS + guide_js)

        def do_cache_scan() -> dict:
            new_items = scan_cache(saved)
            exported = []
            for _title, result in new_items:
                if export_result(saved, exports, result, "cache", ctx):
                    exported.append(_title)
            page_res = try_export_from_pages(ctx, saved, exports, "page")
            exported.extend(page_res.get("exported", []))
            if exported:
                msg = "导出成功: " + "、".join(str(x) for x in exported)
            else:
                msg = "未找到数据，请刷新详情页后再点绿色按钮"
            notify_all_pages(ctx, msg, f"已导出 {len(exports)} 份" if exports else "未找到题目")
            return {"exported": exported, "total": len(exports)}

        def do_export_page() -> dict:
            res = try_export_from_pages(ctx, saved, exports, "page")
            if not res["ok"]:
                notify_all_pages(ctx, res["msg"], "未找到题目，请刷新后重试")
            return res

        page = open_portal_page(ctx)

        def on_resp(resp):
            nonlocal api_hits
            try:
                url = resp.url
                if "iclass30.com" not in url and "12xue" not in url:
                    return
                data = try_parse_resp_json(resp)
                if data is None:
                    return
                if "quesList" in json.dumps(data, ensure_ascii=False)[:8000]:
                    api_hits += 1
                result = extract_quiz_result(data)
                if not result:
                    return
                export_result(saved, exports, result, "api", ctx)
            except Exception:
                pass

        ctx.on("response", on_resp)

        def on_new_page(pg):
            try:
                pg.evaluate(FETCH_HOOK_JS)
                pg.evaluate(guide_js)
            except Exception:
                pass

        ctx.on("page", on_new_page)
        page.evaluate(FETCH_HOOK_JS)
        page.evaluate(guide_js)

        print("浏览器已打开。")
        print("进入测验详情页后，点绿色「导出当前页」。")
        print("导出文件在 output/ 文件夹")
        print("全部导出完成后按 Enter 关闭…")

        try:
            while True:
                poll_pending_buttons(ctx, saved, exports, do_cache_scan, do_export_page)
                for pg in ctx.pages:
                    url = pg.url or ""
                    if any(k in url for k in ("previewHomework", "previewExam", "workexam")):
                        try_export_from_pages(ctx, saved, exports, "auto")
                if msvcrt.kbhit():
                    ch = msvcrt.getch()
                    if ch in (b"\r", b"\n"):
                        break
                page.wait_for_timeout(1500)
        except EOFError:
            for _ in range(2400):
                poll_pending_buttons(ctx, saved, exports, do_cache_scan, do_export_page)
                page.wait_for_timeout(1500)

        do_export_page()
        do_cache_scan()
        (OUT / "manual_exports.json").write_text(
            json.dumps({"exports": exports, "api_hits": api_hits}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            ctx.close()
        except Exception:
            pass

    print(f"\n共导出 {len(exports)} 份")
    for e in exports:
        print(f"  - {e['title']} ({e['count']}题)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
