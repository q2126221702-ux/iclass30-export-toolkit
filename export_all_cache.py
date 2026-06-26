"""扫描浏览器缓存中所有 quesList 并导出."""
import json
import os
import re
from datetime import datetime
from pathlib import Path

from browser_util import OLD_SESSION, TEMP_SESSION

SESSION_CACHE_DIRS = [
    OLD_SESSION / "Default/Cache/Cache_Data",
    TEMP_SESSION / "Default/Cache/Cache_Data",
]
OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)

import export_homework as eh


def extract_result(data: dict) -> dict | None:
    r = data.get("result", {})
    if isinstance(r, dict) and r.get("quesList"):
        return r
    return None


def save_export(title: str, result: dict) -> tuple[Path, Path]:
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
    return md, js


def main():
    found = {}
    for cache_dir in SESSION_CACHE_DIRS:
        if not cache_dir.exists():
            continue
        for f in cache_dir.glob("f_*"):
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
                if "quesList" not in text:
                    continue
                data = json.loads(text)
                result = extract_result(data)
                if not result:
                    continue
                title = result.get("title", f"unknown_{f.name}")
                found[title] = result
            except Exception:
                pass

    print(f"缓存中共 {len(found)} 份测验/作业:")
    for t in found:
        print(f"  - {t} ({len(found[t]['quesList'])} 题)")

    exported = []
    for title, result in found.items():
        md, js = save_export(title, result)
        exported.append((title, md, len(result["quesList"])))

    print(f"\n本次导出: {len(exported)} 份")
    for t, m, n in exported:
        print(f"  {t} ({n}题) -> {m.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
