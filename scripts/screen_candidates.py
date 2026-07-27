#!/usr/bin/env python3
"""Create/validate human screening records and a local HTML screening workbench."""
import argparse
import csv
import datetime as dt
import html
import io
import json
import pathlib


VALID = {"include", "exclude", "pending"}


def candidate_id(item, index):
    return str(item.get("DOI") or item.get("doi") or item.get("id") or f"row-{index}")


def load_decisions(path):
    source = pathlib.Path(path)
    if source.suffix.lower() == ".csv":
        return list(csv.DictReader(source.read_text(encoding="utf-8-sig").splitlines()))
    value = json.loads(source.read_text(encoding="utf-8"))
    return value.get("decisions", [])


def validate(decisions, candidate_ids):
    seen, invalid = set(), []
    for row in decisions:
        identifier = str(row.get("candidate_id") or "") if isinstance(row, dict) else ""
        decision = row.get("decision") if isinstance(row, dict) else None
        if (not identifier or identifier not in candidate_ids or identifier in seen or decision not in VALID
                or (decision != "pending" and not str(row.get("reason") or "").strip())):
            invalid.append(row)
        seen.add(identifier)
    if invalid:
        raise SystemExit("ERROR: each include/exclude decision requires a unique candidate_id and a reason.")


def write_csv(rows, out):
    stream = io.StringIO()
    fields = ["candidate_id", "title", "year", "source", "abstract", "decision", "reason"]
    writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
    for index, item in enumerate(rows):
        writer.writerow({"candidate_id": candidate_id(item, index), "title": item.get("title", ""),
                         "year": item.get("year") or item.get("publication_year") or "", "source": item.get("source", ""),
                         "abstract": item.get("abstract") or item.get("abstractNote") or "", "decision": "pending", "reason": ""})
    (out / "screening-template.csv").write_text(stream.getvalue(), encoding="utf-8-sig")


def write_workbench(rows, decisions, out):
    by_id = {str(row.get("candidate_id")): row for row in decisions}
    cards = []
    for index, item in enumerate(rows):
        identifier = candidate_id(item, index); previous = by_id.get(identifier, {})
        title = html.escape(str(item.get("title") or "Untitled candidate")); abstract = html.escape(str(item.get("abstract") or item.get("abstractNote") or "No abstract supplied."))
        source = html.escape(str(item.get("source") or "Unknown source")); year = html.escape(str(item.get("year") or item.get("publication_year") or "—"))
        reason = html.escape(str(previous.get("reason") or ""), quote=True); selected = previous.get("decision", "pending")
        options = "".join(f"<option value='{value}' {'selected' if selected == value else ''}>{label}</option>" for value, label in (("pending", "待定"), ("include", "纳入"), ("exclude", "排除")))
        cards.append(f"<article class='candidate' data-id='{html.escape(identifier, quote=True)}'><h2>{index + 1}. {title}</h2><p class='meta'>{source} · {year} · ID: {html.escape(identifier)}</p><p>{abstract}</p><label>决定 <select>{options}</select></label><label>理由 <input value='{reason}' placeholder='纳入/排除时必填'></label></article>")
    page = """<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>文献人工筛选工作台</title><style>body{max-width:1000px;margin:24px auto;padding:0 18px;font:15px/1.6 -apple-system,BlinkMacSystemFont,'Microsoft YaHei',sans-serif;background:#f6f8fb;color:#172033}header,.candidate{background:#fff;border-radius:10px;padding:18px;margin:14px 0;box-shadow:0 1px 4px #0002}.meta{color:#526275;font-size:13px}.candidate h2{font-size:18px;margin-top:0}label{display:block;margin-top:10px;font-weight:600}select,input{box-sizing:border-box;width:100%;margin-top:4px;padding:8px;border:1px solid #b9c8d6;border-radius:5px}button{padding:10px 14px;border:0;border-radius:6px;background:#155e75;color:#fff;font-weight:700;cursor:pointer}.note{background:#fff4cf;padding:10px;border-left:4px solid #c78900}</style><body><header><h1>人工筛选工作台</h1><p class='note'>本页不自动纳入任何文章。请逐篇选择决定并填写理由；下载 JSON 后，再交给 <code>screen_candidates.py --decisions</code> 验证与写入正式记录。</p><button id='download'>下载 screening-decisions.json</button> <button id='csv'>下载筛选结果 CSV</button></header>__CARDS__<script>const records=()=>[...document.querySelectorAll('.candidate')].map(x=>({candidate_id:x.dataset.id,title:x.querySelector('h2').textContent.replace(/^\\d+\\.\\s*/,''),decision:x.querySelector('select').value,reason:x.querySelector('input').value.trim()}));function download(name,text,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();URL.revokeObjectURL(a.href)}document.querySelector('#download').onclick=()=>{const decisions=records();const invalid=decisions.filter(x=>x.decision!=='pending'&&!x.reason);if(invalid.length){alert('纳入或排除必须填写理由。');return}download('screening-decisions.json',JSON.stringify({schema_version:'1.0',status:'human_screened',decisions},null,2),'application/json')};document.querySelector('#csv').onclick=()=>{const rows=records();download('screening-decisions.csv','candidate_id,title,decision,reason\\n'+rows.map(x=>[x.candidate_id,x.title,x.decision,x.reason].map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\\n'),'text/csv')}</script></body></html>"""
    (out / "screening-workbench.html").write_text(page.replace("__CARDS__", "".join(cards)), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True); parser.add_argument("--out", required=True); parser.add_argument("--decisions")
    args = parser.parse_args(); output = pathlib.Path(args.out); output.mkdir(parents=True, exist_ok=True)
    raw = json.loads(pathlib.Path(args.candidates).read_text(encoding="utf-8")); rows = raw if isinstance(raw, list) else raw.get("items", raw.get("additions", []))
    rows = [item for item in rows if isinstance(item, dict)]; ids = {candidate_id(item, index) for index, item in enumerate(rows)}
    if args.decisions:
        decisions = load_decisions(args.decisions); validate(decisions, ids)
        status, note = "human_screened", "Only human-confirmed includes may contribute to B metrics."
    else:
        decisions = [{"candidate_id": candidate_id(item, index), "title": item.get("title", ""), "decision": "pending", "reason": ""} for index, item in enumerate(rows)]
        status, note = "template", "Set decision to include/exclude/pending. Include and exclude require a reason."
    result = {"schema_version": "1.1", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "decisions": decisions, "status": status, "note": note}
    (output / "screening-decisions.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(rows, output); write_workbench(rows, decisions, output)
    print(f"Wrote {status} screening log, CSV template, and HTML workbench.")


if __name__ == "__main__": main()
