"""C30 测验/作业 API 数据格式化（供导出脚本复用）."""
import json
import re


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&ndash;", "-").replace("&le;", "≤")
    return re.sub(r"\s+", " ", text).strip()


def parse_choice_answer(answer_idx: str, options: list) -> str:
    try:
        i = int(answer_idx)
        if 0 <= i < len(options):
            return f"{chr(65 + i)}. {strip_html(options[i].get('Content', ''))}"
    except (ValueError, TypeError):
        pass
    return answer_idx


def parse_fill_answer(answer_raw: str) -> str:
    try:
        items = json.loads(answer_raw) if isinstance(answer_raw, str) else answer_raw
        return "；".join(strip_html(x.get("Content", "")) for x in items)
    except Exception:
        return strip_html(str(answer_raw))


def format_question(q: dict) -> dict:
    title = strip_html(q.get("title", ""))
    ques_type = q.get("quesType")
    ques_name = q.get("quesName", "")
    options = []
    if q.get("datajson"):
        try:
            dj = json.loads(q["datajson"]) if isinstance(q["datajson"], str) else q["datajson"]
            if isinstance(dj, list):
                options = [strip_html(o.get("Content", "")) for o in dj]
            elif isinstance(dj, dict) and "options" in dj:
                options = [strip_html(o.get("Content", "")) for o in dj["options"]]
        except Exception:
            pass

    answer_raw = q.get("answer", "")
    if ques_type == 1:
        opts = json.loads(q["datajson"]) if isinstance(q.get("datajson"), str) else q.get("datajson", [])
        correct = parse_choice_answer(str(answer_raw), opts)
        stu = parse_choice_answer(str(q.get("stuAnswer", "")), opts)
    elif ques_type == 4:
        correct = parse_fill_answer(answer_raw)
        stu = parse_fill_answer(q.get("stuAnswer", ""))
    else:
        correct = strip_html(str(answer_raw))
        stu = strip_html(str(q.get("stuAnswer", "")))

    return {
        "sort": q.get("sortOrder"),
        "type": ques_name,
        "title": title,
        "options": options,
        "correct_answer": correct,
        "your_answer": stu,
        "score": q.get("getScore"),
        "full_score": q.get("quesScore"),
    }
