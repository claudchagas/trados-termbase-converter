#!/usr/bin/env python3
"""
termbase_to_markdown.py
=======================
Converts Trados MultiTerm termbases (.tbx and .csv) into a markdown glossary
table matching the format:

| English | Definition | Part of Speech | Source Case Sensitive? |
| Mandatory DNT | Portuguese Variations (Brazil) | [pt-BR] |

Usage
-----
    # Convert a single file:
    python termbase_to_markdown.py Agile_practices.tbx
    python termbase_to_markdown.py Agile_practices.csv

    # Convert an entire folder (all .tbx and .csv files):
    python termbase_to_markdown.py /path/to/Trados_Termbases/

    # Merge all files into one output table:
    python termbase_to_markdown.py /path/to/Trados_Termbases/ --merge

    # Specify a custom output directory:
    python termbase_to_markdown.py /path/to/folder/ --outdir /path/to/output/

Notes
-----
- Definition, Part of Speech, Source Case Sensitive?, Mandatory DNT, and
  Portuguese Variations columns are left blank for manual completion.
- If a term entry has no pt-BR equivalent, [pt-BR] is marked as MISSING.
- Duplicate entries (same English term) within a single file are deduplicated;
  a warning is printed for each duplicate found.
- Output files are named after the source file (e.g. Agile_practices.md).
  With --merge, the output is named merged_glossary.md.
"""

import argparse
import csv
import io
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


# ---------------------------------------------------------------------------
# TBX parser
# ---------------------------------------------------------------------------

def parse_tbx(filepath: Path) -> list[dict]:
    """Parse a TBX-Basic file and return a list of term pair dicts."""
    tree = ET.parse(filepath)
    root = tree.getroot()

    # TBX uses a default namespace; strip it for simpler tag matching
    # by normalising all tags
    def strip_ns(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    entries = []
    seen = set()

    for term_entry in root.iter():
        if strip_ns(term_entry.tag) != "termEntry":
            continue

        en_term = ""
        pt_term = ""

        for lang_set in term_entry:
            if strip_ns(lang_set.tag) != "langSet":
                continue

            lang = lang_set.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", "")
            if not lang:
                # Try without namespace prefix
                lang = lang_set.attrib.get("xml:lang", "")

            # Find the <term> element inside <tig>
            for tig in lang_set:
                if strip_ns(tig.tag) != "tig":
                    continue
                for child in tig:
                    if strip_ns(child.tag) == "term":
                        term_text = (child.text or "").strip()
                        if lang.startswith("en"):
                            en_term = term_text
                        elif lang.startswith("pt"):
                            pt_term = term_text

        if not en_term:
            continue

        if en_term in seen:
            print(f"  [DUPLICATE] '{en_term}' in {filepath.name} — keeping first occurrence.")
            continue
        seen.add(en_term)

        entries.append({
            "english": en_term,
            "pt_br": pt_term if pt_term else "MISSING",
        })

    return entries


# ---------------------------------------------------------------------------
# CSV parser
# ---------------------------------------------------------------------------

# Column header markers used by Trados MultiTerm CSV exports
EN_HEADER = ">>L<<English (United States)"
PT_HEADER = ">>L<<Portuguese (Brazil)"


def parse_csv(filepath: Path) -> list[dict]:
    """Parse a Trados MultiTerm CSV export and return a list of term pair dicts."""
    entries = []
    seen = set()

    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        # Trados CSV repeats column names; csv.DictReader appends suffixes
        # like ">>L<<English (United States).1" for duplicates.
        # Find the FIRST occurrence of each language column.
        en_col = next((h for h in headers if h == EN_HEADER or h.startswith(EN_HEADER)), None)
        pt_col = next((h for h in headers if h == PT_HEADER or h.startswith(PT_HEADER)), None)

        if not en_col:
            print(f"  [WARNING] Could not find English column in {filepath.name}. Skipping.")
            return []
        if not pt_col:
            print(f"  [WARNING] Could not find pt-BR column in {filepath.name}. pt-BR will be MISSING.")

        for row in reader:
            en_term = (row.get(en_col) or "").strip()
            pt_term = (row.get(pt_col) or "").strip() if pt_col else ""

            if not en_term:
                continue

            if en_term in seen:
                print(f"  [DUPLICATE] '{en_term}' in {filepath.name} — keeping first occurrence.")
                continue
            seen.add(en_term)

            entries.append({
                "english": en_term,
                "pt_br": pt_term if pt_term else "MISSING",
            })

    return entries


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

HEADER = (
    "| English | Definition | Part of Speech | Source Case Sensitive? "
    "| Mandatory DNT | Portuguese Variations (Brazil) | [pt-BR] |\n"
    "|---|---|---|---|---|---|---|\n"
)


def entries_to_markdown(entries: list[dict], source_label: str = "") -> str:
    """Render a list of term pair dicts as a markdown table string."""
    lines = []
    if source_label:
        lines.append(f"## {source_label}\n")
    lines.append(HEADER)
    for e in entries:
        en = e["english"].replace("|", "\\|")
        pt = e["pt_br"].replace("|", "\\|")
        lines.append(f"| {en} | | | | | | {pt} |\n")
    return "".join(lines)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def collect_files(path: Path) -> list[Path]:
    """Return all .tbx and .csv files under path (file or directory)."""
    if path.is_file():
        return [path]
    files = sorted(
        p for p in path.rglob("*")
        if p.suffix.lower() in {".tbx", ".csv"}
    )
    return files


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert Trados TBX/CSV termbases to markdown glossary tables."
    )
    parser.add_argument(
        "input",
        help="Path to a .tbx/.csv file or a folder containing termbase files.",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge all converted files into a single output file (merged_glossary.md).",
    )
    parser.add_argument(
        "--outdir",
        default=None,
        help="Directory for output .md files. Defaults to same directory as input.",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"Error: '{input_path}' does not exist.")
        sys.exit(1)

    files = collect_files(input_path)
    if not files:
        print("No .tbx or .csv files found.")
        sys.exit(0)

    # Determine output directory
    if args.outdir:
        outdir = Path(args.outdir).resolve()
        outdir.mkdir(parents=True, exist_ok=True)
    elif input_path.is_file():
        outdir = input_path.parent
    else:
        outdir = input_path

    all_blocks = []  # for --merge mode

    for fp in files:
        print(f"Processing: {fp.name}")
        suffix = fp.suffix.lower()
        try:
            if suffix == ".tbx":
                entries = parse_tbx(fp)
            elif suffix == ".csv":
                entries = parse_csv(fp)
            else:
                continue
        except Exception as exc:
            print(f"  [ERROR] Failed to parse {fp.name}: {exc}")
            continue

        print(f"  → {len(entries)} entries extracted.")

        if args.merge:
            all_blocks.append((fp.stem, entries))
        else:
            md_content = entries_to_markdown(entries)
            out_path = outdir / (fp.stem + ".md")
            out_path.write_text(md_content, encoding="utf-8")
            print(f"  → Written to: {out_path}")

    if args.merge and all_blocks:
        merged_lines = ["# Merged Glossary\n\n"]
        for label, entries in all_blocks:
            merged_lines.append(entries_to_markdown(entries, source_label=label))
            merged_lines.append("\n")
        out_path = outdir / "merged_glossary.md"
        out_path.write_text("".join(merged_lines), encoding="utf-8")
        total = sum(len(e) for _, e in all_blocks)
        print(f"\nMerged {total} entries from {len(all_blocks)} file(s) → {out_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
