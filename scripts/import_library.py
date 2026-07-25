#!/usr/bin/env python3
"""Import JSON, CSV, RIS or BibTeX into the canonical literature-item JSON contract."""
import argparse
import csv
import json
import pathlib
import re


def clean(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def canonical(row):
    title = clean(row.get("title") or row.get("TI") or row.get("T1"))
    doi = clean(row.get("DOI") or row.get("doi")).replace("https://doi.org/", "")
    year = re.search(r"\b(19|20)\d{2}\b", clean(row.get("year") or row.get("PY") or row.get("date")))
    return {"title": title, "DOI": doi, "year": int(year.group(0)) if year else None,
            "abstractNote": clean(row.get("abstract") or row.get("AB")),
            "publicationTitle": clean(row.get("journal") or row.get("JO") or row.get("venue")),
            "authors": row.get("authors") or [], "source": clean(row.get("source"))}


def parse_ris(text):
    records, current = [], {}
    for line in text.splitlines():
        if line.startswith("TY  - "):
            current = {}
        elif line.startswith("ER  - "):
            records.append(current); current = {}
        elif len(line) >= 6 and line[2:6] == "  - ":
            key, value = line[:2], line[6:]
            if key in current: current[key] = f"{current[key]}; {value}"
            else: current[key] = value
    return [canonical(item) for item in records]


def parse_bibtex(text):
    records = []
    for block in re.split(r"@\w+\s*\{", text)[1:]:
        fields = {key.lower(): clean(value.strip().strip(",").strip("{}\""))
                  for key, value in re.findall(r"(\w+)\s*=\s*([\{\"][^}\"]*[}\"])", block)}
        records.append(canonical(fields))
    return records


def load(path):
    source = pathlib.Path(path); suffix = source.suffix.lower(); text = source.read_text(encoding="utf-8-sig")
    if suffix == ".json":
        value = json.loads(text); rows = value if isinstance(value, list) else value.get("items", [])
        if not isinstance(rows, list): raise ValueError("JSON must be an array or an object with items[].")
        return [canonical(row) for row in rows if isinstance(row, dict)]
    if suffix == ".csv": return [canonical(row) for row in csv.DictReader(text.splitlines())]
    if suffix == ".ris": return parse_ris(text)
    if suffix in {".bib", ".bibtex"}: return parse_bibtex(text)
    raise ValueError("Supported formats: .json, .csv, .ris, .bib, .bibtex")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True); parser.add_argument("--out", required=True)
    args = parser.parse_args(); rows = load(args.input)
    missing_title = sum(not row["title"] for row in rows); missing_year = sum(row["year"] is None for row in rows)
    output = pathlib.Path(args.out); output.mkdir(parents=True, exist_ok=True)
    (output / "library.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {"source_filename": pathlib.Path(args.input).name, "records_imported": len(rows),
              "missing_title": missing_title, "missing_year": missing_year,
              "next_step": "Review import-preview.json, then use library.json as the audit input."}
    (output / "import-preview.json").write_text(json.dumps({**report, "sample": rows[:5]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__": main()
