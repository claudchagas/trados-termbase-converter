# From Trados Termbase to Markdown Glossary
## A Step-by-Step Reusable Guide

**Purpose:** Convert Trados MultiTerm termbases (.tbx and .csv) into structured markdown glossary tables for use in localization style guides, reference documentation, or master glossary consolidation.

**Audience:** Translators and localization specialists with basic command-line familiarity.

**Time required:** ~15 minutes (plus script run time, which scales with folder size).

---

## What You Will Produce

A markdown table with the following columns for each termbase file:

| English | Definition | Part of Speech | Source Case Sensitive? | Mandatory DNT | Portuguese Variations (Brazil) | [pt-BR] |
|---|---|---|---|---|---|---|
| Sprint | A fixed time period in Scrum... | noun | Yes | Yes | — | Sprint |

The columns **Definition**, **Part of Speech**, **Source Case Sensitive?**, **Mandatory DNT**, and **Portuguese Variations** are left blank by the script for manual completion. Only **English** and **[pt-BR]** are populated automatically from the termbase.

---

## Prerequisites

- Python 3.10 or later
- VS Code (or any terminal)
- Your Trados termbase files (.tbx and/or .csv) in a local folder

### Verify Python version

```bash
python3 --version
```

Expected output: `Python 3.11.x` or higher. If you see `command not found`, try `python` instead of `python3`.

---

## Key Decisions Made in This Project

**TBX vs CSV — which to use?**
Both formats export identical term pair data from Trados MultiTerm. The script handles both. If you have both versions of the same termbase, run only one — the output will be the same.

**What data is NOT in the termbases?**
Trados termbases in this configuration store only the term pairs (English ↔ pt-BR) and transaction metadata (who created/modified entries and when). Definitions, part of speech, case sensitivity, and DNT flags must be added manually after conversion.

**Pipe-separated variants in pt-BR (`Scrum Master\|Mestre Scrum`)**
When Trados stores multiple acceptable translations for a single entry, they appear pipe-separated in the output. Review these entries and either keep the preferred variant or move the alternative to the Portuguese Variations column.

**One file per termbase vs. merged output**
Use one file per termbase when you want to maintain per-client glossary separation. Use `--merge` when building a consolidated master glossary across all clients.

---

## Step 1 — Understand the File Formats

### TBX (TermBase eXchange)

TBX is an XML-based standard. Each entry is a `<termEntry>` block containing two `<langSet>` blocks — one for `en-US` and one for `pt-BR`. The term itself is inside `<tig><term>`.

```xml
<termEntry id="LC67ac061850e998773189f5ab">
  <langSet xml:lang="en-US">
    <tig>
      <term>Big Room Planning</term>
    </tig>
  </langSet>
  <langSet xml:lang="pt-BR">
    <tig>
      <term>Big Room Planning</term>
    </tig>
  </langSet>
</termEntry>
```

### CSV (Trados MultiTerm Export)

The CSV has a very wide header row filled with system metadata columns. The two columns that matter are:

- `>>L<<English (United States)` — source term
- `>>L<<Portuguese (Brazil)` — target term

Everything else (creation dates, user IDs, modification timestamps) is audit trail noise and is ignored by the script.

---

## Step 2 — Save the Conversion Script

Create a file named `termbase_to_markdown.py` and paste the full script below into it. Save it somewhere accessible, such as your `~/Downloads` folder.

```python
#!/usr/bin/env python3
"""
termbase_to_markdown.py
Converts Trados MultiTerm termbases (.tbx and .csv) to markdown glossary tables.

Usage:
    python3 termbase_to_markdown.py <file_or_folder> [--merge] [--outdir <path>]
"""

import argparse
import csv
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


# ---------------------------------------------------------------------------
# TBX parser
# ---------------------------------------------------------------------------

def parse_tbx(filepath: Path) -> list[dict]:
    tree = ET.parse(filepath)
    root = tree.getroot()

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

            lang = lang_set.attrib.get(
                "{http://www.w3.org/XML/1998/namespace}lang", ""
            ) or lang_set.attrib.get("xml:lang", "")

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
            print(f"  [DUPLICATE] '{en_term}' in {filepath.name} — keeping first.")
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

EN_HEADER = ">>L<<English (United States)"
PT_HEADER = ">>L<<Portuguese (Brazil)"


def parse_csv(filepath: Path) -> list[dict]:
    entries = []
    seen = set()

    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        en_col = next((h for h in headers if h == EN_HEADER or h.startswith(EN_HEADER)), None)
        pt_col = next((h for h in headers if h == PT_HEADER or h.startswith(PT_HEADER)), None)

        if not en_col:
            print(f"  [WARNING] Could not find English column in {filepath.name}. Skipping.")
            return []

        for row in reader:
            en_term = (row.get(en_col) or "").strip()
            pt_term = (row.get(pt_col) or "").strip() if pt_col else ""

            if not en_term:
                continue

            if en_term in seen:
                print(f"  [DUPLICATE] '{en_term}' in {filepath.name} — keeping first.")
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
    lines = []
    if source_label:
        lines.append(f"## {source_label}\n\n")
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
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*") if p.suffix.lower() in {".tbx", ".csv"})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert Trados TBX/CSV termbases to markdown glossary tables."
    )
    parser.add_argument("input", help="Path to a file or folder of termbase files.")
    parser.add_argument("--merge", action="store_true",
                        help="Merge all files into a single merged_glossary.md.")
    parser.add_argument("--outdir", default=None,
                        help="Output directory. Defaults to same location as input.")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"Error: '{input_path}' does not exist.")
        sys.exit(1)

    files = collect_files(input_path)
    if not files:
        print("No .tbx or .csv files found.")
        sys.exit(0)

    if args.outdir:
        outdir = Path(args.outdir).resolve()
        outdir.mkdir(parents=True, exist_ok=True)
    elif input_path.is_file():
        outdir = input_path.parent
    else:
        outdir = input_path

    all_blocks = []

    for fp in files:
        print(f"Processing: {fp.name}")
        try:
            entries = parse_tbx(fp) if fp.suffix.lower() == ".tbx" else parse_csv(fp)
        except Exception as exc:
            print(f"  [ERROR] Failed to parse {fp.name}: {exc}")
            continue

        print(f"  → {len(entries)} entries extracted.")

        if args.merge:
            all_blocks.append((fp.stem, entries))
        else:
            out_path = outdir / (fp.stem + ".md")
            out_path.write_text(entries_to_markdown(entries), encoding="utf-8")
            print(f"  → Written to: {out_path}")

    if args.merge and all_blocks:
        merged = ["# Merged Glossary\n\n"]
        for label, entries in all_blocks:
            merged.append(entries_to_markdown(entries, source_label=label))
            merged.append("\n")
        out_path = outdir / "merged_glossary.md"
        out_path.write_text("".join(merged), encoding="utf-8")
        total = sum(len(e) for _, e in all_blocks)
        print(f"\nMerged {total} entries from {len(all_blocks)} file(s) → {out_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
```

---

## Step 3 — Run the Script

Open a terminal in VS Code: **Terminal → New Terminal** (or press `` Ctrl+` ``).

### Convert one file at a time

```bash
python3 termbase_to_markdown.py "/Users/yourname/Downloads/Agile_practices.tbx"
```

### Convert an entire folder — one .md file per termbase

```bash
python3 termbase_to_markdown.py "/Users/yourname/Downloads/Trados Termbases" \
  --outdir ~/Desktop/Glossaries
```

### Convert an entire folder — merge all into one file

```bash
python3 termbase_to_markdown.py "/Users/yourname/Downloads/Trados Termbases" \
  --merge --outdir ~/Desktop/Glossaries
```

> **Note:** Always quote paths that contain spaces. Use regular quotes (`"`), not backslash escaping.

---

## Step 4 — Review the Output

Open any `.md` file in VS Code. Press `Cmd+Shift+V` (macOS) or `Ctrl+Shift+V` (Windows/Linux) to preview the rendered markdown table.

### What to review manually

After conversion, go through each file and complete the blank columns:

**Definition** — Add a concise, domain-appropriate definition for each term.

**Part of Speech** — Common values: `noun`, `verb`, `adjective`, `noun phrase`, `proper noun`.

**Source Case Sensitive?** — Mark `Yes` for proper nouns, product names, and trademarked terms. Mark `No` for common nouns and verbs.

**Mandatory DNT** — Mark `Yes` for terms that must never be translated (e.g. `passkey`, `roadmap`, `Scrum`). Leave blank or mark `No` otherwise.

**Portuguese Variations (Brazil)** — Add alternative accepted translations where applicable.

### Special case: pipe-separated pt-BR variants

When Trados stores multiple translations for one term, the script outputs them pipe-separated:

```
Scrum Master\|Mestre Scrum
```

Decide which is the preferred translation, place it in `[pt-BR]`, and move the alternative to **Portuguese Variations (Brazil)**.

---

## Step 5 — Troubleshooting

**`command not found: python3`**
Try `python` instead. If neither works, install Python from python.org.

**`[WARNING] Could not find English column`**
The CSV was not exported from Trados MultiTerm using the default column layout. Open the CSV in a text editor and check the header row for the exact column name used for the English terms.

**`[ERROR] Failed to parse`**
The TBX file may be malformed or use a non-standard TBX dialect. Open the file in a text editor and check that it has a valid XML header and `<martif>` root element.

**`MISSING` in the [pt-BR] column**
The source termbase had no pt-BR translation for that entry. Fill in manually.

**Duplicate warnings**
The script keeps the first occurrence and skips subsequent ones. If you need to reconcile duplicates, open the source termbase in Trados and resolve them there before re-exporting.

---

## Step 6 — Publish to GitHub

Once your output files are ready, you can publish the script and guide to GitHub for version control, sharing, and reuse across machines.

### Prerequisites

- A GitHub account (github.com)
- Git installed — verify with `git --version` (macOS includes Git by default)
- A Personal Access Token for authentication (see below)

### 6.1 — Create a new repository on GitHub

Go to github.com → click the green **New** button → name it (e.g. `trados-termbase-converter`) → add a description → leave it completely empty (no README, no .gitignore) → click **Create repository**.

### 6.2 — Set up your local folder

Create the project folder inside your existing Projects directory:

```bash
mkdir ~/Projects/trados-termbase-converter
cd ~/Projects/trados-termbase-converter
```

Copy your files into the folder:
- `termbase_to_markdown.py`
- `Trados_Termbase_to_Markdown_Guide.md`

Then create a README (GitHub renders this automatically as the repo front page):

```bash
cp Trados_Termbase_to_Markdown_Guide.md README.md
```

### 6.3 — Add a .gitignore

This prevents macOS system files from being accidentally committed:

```bash
echo ".DS_Store" > .gitignore
```

### 6.4 — Initialise, commit, and push

```bash
git init
git add .
git commit -m "Initial commit: termbase converter script and guide"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/trados-termbase-converter.git
git push --set-upstream origin main
```

Replace `YOUR_USERNAME` with your GitHub username.

### 6.5 — Authenticate with a Personal Access Token

When Git asks for a password, do not type your GitHub password — paste a Personal Access Token instead.

To generate one: GitHub → avatar menu → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)** → add a description (e.g. `MacBook Pro - VS Code Git access`) → set expiration → tick the **repo** checkbox → click **Generate token** → copy it immediately (it only shows once).

Paste the token as your password when prompted.

### 6.6 — Pushing future updates

Whenever you update a file, run:

```bash
cd ~/Projects/trados-termbase-converter
git add .
git commit -m "Describe what you changed"
git push
```

### Key decisions for GitHub

**Always quote folder paths that contain spaces** — use `"Trados Termbases"` not `Trados\ Termbases`.

**Keep .gitignore in the repo** — macOS generates `.DS_Store` files automatically in every folder. The `.gitignore` prevents them from appearing in your commit history.

**Use the same Personal Access Token across repos** — one token works for all your GitHub repositories on the same machine. Store it in a password manager so you don't need to regenerate it.

**README.md renders automatically** — whatever is in `README.md` appears as the front page of your repository. Keeping it in sync with your guide means the repo is self-documenting.

---

## Quick Reference

| Goal | Command |
|---|---|
| Convert one TBX file | `python3 termbase_to_markdown.py file.tbx` |
| Convert one CSV file | `python3 termbase_to_markdown.py file.csv` |
| Convert folder, one file per termbase | `python3 termbase_to_markdown.py "folder/" --outdir ~/Desktop/Glossaries` |
| Convert folder, merge all into one file | `python3 termbase_to_markdown.py "folder/" --merge --outdir ~/Desktop/Glossaries` |
| Preview markdown in VS Code | `Cmd+Shift+V` (macOS) / `Ctrl+Shift+V` (Windows) |
| Initialise a new Git repo | `git init` |
| Stage all files | `git add .` |
| Commit staged files | `git commit -m "Your message"` |
| Push to GitHub (first time) | `git push --set-upstream origin main` |
| Push to GitHub (subsequent) | `git push` |

---

## Sample Output

Given a termbase with Agile practices terminology, the script produces:

| English | Definition | Part of Speech | Source Case Sensitive? | Mandatory DNT | Portuguese Variations (Brazil) | [pt-BR] |
|---|---|---|---|---|---|---|
| Big Room Planning | | | | | | Big Room Planning |
| Time-boxing | | | | | | Caixa de Tempo |
| Iterative Development | | | | | | Desenvolvimento Iterativo |
| Continuous Integration | | | | | | Integração Contínua |
| Kanban Board | | | | | | Quadro Kanban |
| Sprint | | | | | | Sprint |
| Scrum | | | | | | Scrum |

---

*Guide produced from a working session converting Trados MultiTerm termbases to markdown for use in a Brazilian Portuguese localization workflow.*
