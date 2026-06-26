"""从当前浏览器页面提取测验数据（Vue / 拦截缓存 / 全文解析 / iframe）."""

EXTRACT_IN_DOC_JS = """
(doc) => {
  const root = doc || document;
  const bodyText = (root.body && root.body.innerText) || "";

  const store = (root.defaultView || window).__captured_quizzes__ || {};
  const keys = Object.keys(store);
  if (keys.length) {
    const last = store[keys[keys.length - 1]];
    if (last && last.quesList && last.quesList.length) return last;
  }

  const walk = (obj, d = 0, seen = new WeakSet()) => {
    if (!obj || d > 12 || typeof obj !== "object") return null;
    if (seen.has(obj)) return null;
    try { seen.add(obj); } catch (e) {}
    if (Array.isArray(obj.quesList) && obj.quesList.length && obj.quesList[0] && obj.quesList[0].title) {
      return obj;
    }
    if (Array.isArray(obj)) {
      for (const x of obj) { const f = walk(x, d + 1, seen); if (f) return f; }
      return null;
    }
    for (const k of Object.keys(obj)) {
      try { const f = walk(obj[k], d + 1, seen); if (f) return f; } catch (e) {}
    }
    return null;
  };

  const win = root.defaultView || window;
  for (const k of Object.keys(win)) {
    try {
      const f = walk(win[k]);
      if (f) return f;
    } catch (e) {}
  }

  const clean = (s) => (s || "").replace(/\\s+/g, " ").trim();
  if (!/正确答案/.test(bodyText) || !/单选|多选|填空/.test(bodyText)) return null;

  let title = "";
  const skip = /学习空间|作业考试|答题卡|测验列表|全部|首页|帮助中心/;
  const titleRes = [
    /\\n([\\u4e00-\\u9fa5A-Za-z0-9（）()\\-\\s]{2,40})\\n\\s*得分[:：]/,
    /\\n([\\u4e00-\\u9fa5A-Za-z0-9（）()\\-\\s]{2,40})\\n\\s*1\\.[\\s\\[【]/,
  ];
  for (const re of titleRes) {
    const m = bodyText.match(re);
    if (m && m[1] && !skip.test(m[1])) { title = clean(m[1]); break; }
  }
  if (!title) {
    const h = root.querySelector(".paper-title, .homework-title, .exam-name, .title-name, h1, h2");
    if (h) {
      const t = clean(h.innerText);
      if (t && t.length <= 40 && !skip.test(t)) title = t;
    }
  }

  const quesList = [];
  const text = bodyText.replace(/\\r/g, "");
  const qRe = /(\\d+)\\.[\\s\\[【]*(单选题|多选题|填空题)[\\]】]*\\s*([\\s\\S]*?)正确答案\\s*[:：]\\s*\\n?\\s*([A-DＡ-Ｄ]|[^\\n]+?)(?=\\n\\s*\\d+\\.[\\s\\[【]|\\n答题卡|\\n全部|$)/g;
  let m;
  while ((m = qRe.exec(text)) !== null) {
    const sort = parseInt(m[1], 10);
    const qType = m[2];
    let block = m[3].replace(/\\r/g, "").trim();
    let answer = clean(m[4]);
    let qText = block;
    const options = [];
    const optStart = block.search(/\\n[A-DＡ-Ｄ][.．、]/);
    if (optStart >= 0) {
      qText = block.slice(0, optStart).trim();
      const optBlock = block.slice(optStart);
      const optRe = /([A-DＡ-Ｄ])[.．、]\\s*([^\\n]+)/g;
      let om;
      while ((om = optRe.exec(optBlock)) !== null) {
        options.push({ SortOrder: options.length, Content: "<p>" + clean(om[2]) + "</p>" });
      }
    }
    qText = clean(qText);
    if (!qText) continue;
    if (/^[A-DＡ-Ｄ]$/.test(answer)) {
      const map = { A: "0", B: "1", C: "2", D: "3", "Ａ": "0", "Ｂ": "1", "Ｃ": "2", "Ｄ": "3" };
      answer = map[answer] ?? answer;
    }
    quesList.push({
      title: "<p>" + qText + "</p>",
      quesName: qType,
      quesType: qType.includes("填空") ? 4 : 1,
      sortOrder: sort,
      answer,
      stuAnswer: answer,
      datajson: options.length ? JSON.stringify(options) : "[]",
    });
  }

  if (quesList.length) return { title: title || "当前测验", quesList };
  return null;
}
"""

FIND_QUES_JS = f"""
() => {{
  const fn = {EXTRACT_IN_DOC_JS.strip()};
  let best = null;
  const tryDoc = (doc) => {{
    try {{
      const r = fn(doc);
      if (r && r.quesList && (!best || r.quesList.length > best.quesList.length)) best = r;
    }} catch (e) {{}}
  }};
  tryDoc(document);
  document.querySelectorAll("iframe").forEach((f) => {{
    try {{ if (f.contentDocument) tryDoc(f.contentDocument); }} catch (e) {{}}
  }});
  return best;
}}
"""

SINGLE_FRAME_EXTRACT_JS = EXTRACT_IN_DOC_JS.replace("(doc) => {", "() => { const doc = document;")

FETCH_HOOK_JS = """
(function() {
  if (window.__fetch_hooked) return;
  window.__fetch_hooked = true;
  window.__captured_quizzes__ = window.__captured_quizzes__ || {};

  const savePayload = (data) => {
    try {
      const walk = (obj, d = 0) => {
        if (!obj || d > 10 || typeof obj !== "object") return null;
        if (Array.isArray(obj.quesList) && obj.quesList.length) return obj;
        if (Array.isArray(obj)) { for (const x of obj) { const f = walk(x, d + 1); if (f) return f; } return null; }
        for (const k of Object.keys(obj)) { const f = walk(obj[k], d + 1); if (f) return f; }
        return null;
      };
      const r = walk(data);
      if (r) {
        const title = r.title || ("quiz_" + Date.now());
        window.__captured_quizzes__[title] = r;
      }
    } catch (e) {}
  };

  const origFetch = window.fetch;
  window.fetch = function(...args) {
    return origFetch.apply(this, args).then(resp => {
      try {
        resp.clone().text().then(t => {
          if (t && t.trim().startsWith("{")) savePayload(JSON.parse(t));
        });
      } catch (e) {}
      return resp;
    });
  };

  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this.__iclass_url = url;
    return origOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function(...args) {
    this.addEventListener("load", function() {
      try {
        const t = this.responseText;
        if (t && t.trim().startsWith("{")) savePayload(JSON.parse(t));
      } catch (e) {}
    });
    return origSend.apply(this, args);
  };
})();
"""

API_PATHS = [
    "https://service.iclass30.com/workexam/student/getStuWorkExamQuesList",
    "https://service.iclass30.com/workexam/student/getStuWorkExamDetail",
    "https://service.iclass30.com/workexam/work/getStuWorkExamQuesList",
    "https://service.iclass30.com/workexam/work/getWorkExamQuesList",
    "https://service.iclass30.com/homework/student/getStuHomeworkQuesList",
]
