#!/usr/bin/env python3
"""
tmx_to_markdown.py
==================
Converts TMX (Translation Memory eXchange) files into structured Markdown
glossary tables matching the format used in the Trados termbase converter:

| English | Definition | Part of Speech | Source Case Sensitive? |
| Mandatory DNT | Portuguese Variations (Brazil) | [pt-BR] |

Unlike TBX/CSV termbases, TMX files contain full translated segments rather
than curated term pairs. This script applies several filters to extract only
the entries most likely to be glossary-worthy:

  1. Length filter      — skips segments above a configurable word limit
  2. Identity filter    — flags entries where source and target are identical
  3. Punctuation filter — skips segments that read as full sentences
  4. Deduplication      — normalised exact-match deduplication with warnings
  5. Untranslated flag  — marks entries where target appears to be English

Usage
-----
    # Convert a single TMX file:
    python3 tmx_to_markdown.py file.tmx

    # Convert an entire folder:
    python3 tmx_to_markdown.py /path/to/folder/

    # Merge all files into one output:
    python3 tmx_to_markdown.py /path/to/folder/ --merge

    # Custom output directory:
    python3 tmx_to_markdown.py /path/to/folder/ --outdir ~/Desktop/Glossaries

    # Adjust the word limit (default: 6):
    python3 tmx_to_markdown.py file.tmx --max-words 10

    # Include sentence-length segments (disables length filter):
    python3 tmx_to_markdown.py file.tmx --no-length-filter

    # Show all skipped entries in the terminal:
    python3 tmx_to_markdown.py file.tmx --verbose

    # Export a separate review file of flagged/skipped entries:
    python3 tmx_to_markdown.py file.tmx --review

Output
------
For each input file, the script produces:
  - <filename>.md         — clean glossary table, ready for manual completion
  - <filename>_review.md  — flagged entries requiring manual review (--review)

With --merge:
  - merged_glossary.md
  - merged_review.md      (if --review is set)

Notes
-----
- Definition, Part of Speech, Source Case Sensitive?, Mandatory DNT, and
  Portuguese Variations columns are left blank for manual completion.
- Entries where source == target are included but marked [DNT?] in the
  Mandatory DNT column as a prompt for review.
- Entries where the target appears untranslated (Latin script, high overlap
  with source) are marked [REVIEW] in the [pt-BR] column.
- The script targets pt-BR by default. Use --target-lang to override.
"""

import argparse
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_WORDS = 6

# Characters that strongly suggest a full sentence rather than a term
SENTENCE_PUNCTUATION = re.compile(r'[.!?;:]$')

# Detect strings that are probably still in English (rough heuristic:
# mostly ASCII letters, no accented characters typical of Portuguese)
PT_ACCENT_CHARS = set("áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ")


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

def word_count(text: str) -> int:
    return len(text.split())


def is_sentence(text: str) -> bool:
    """True if the segment ends with sentence-final punctuation."""
    return bool(SENTENCE_PUNCTUATION.search(text.strip()))


def is_identical(source: str, target: str) -> bool:
    return source.strip().lower() == target.strip().lower()


def looks_untranslated(source: str, target: str) -> bool:
    """
    Heuristic: target looks like it was not translated if:
    - it shares >70% of its words with the source (case-insensitive), AND
    - it contains no Portuguese accent characters
    """
    if any(c in target for c in PT_ACCENT_CHARS):
        return False
    src_words = set(source.lower().split())
    tgt_words = set(target.lower().split())
    if not tgt_words:
        return False
    overlap = len(src_words & tgt_words) / len(tgt_words)
    return overlap > 0.7


def normalise_key(text: str) -> str:
    """Lowercase, strip, collapse whitespace — used for deduplication."""
    return re.sub(r'\s+', ' ', text.strip().lower())


# ---------------------------------------------------------------------------
# TMX parser
# ---------------------------------------------------------------------------

def strip_ns(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def parse_tmx(
    filepath: Path,
    source_lang_prefix: str = "en",
    target_lang_prefix: str = "pt",
    max_words: int = DEFAULT_MAX_WORDS,
    length_filter: bool = True,
    verbose: bool = False,
) -> tuple[list[dict], list[dict]]:
    """
    Parse a TMX file and return (clean_entries, flagged_entries).

    clean_entries  — passed all filters, ready for the glossary table
    flagged_entries — skipped or flagged, written to the review file
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as exc:
        print(f"  [ERROR] Could not parse XML in {filepath.name}: {exc}")
        return [], []

    clean = []
    flagged = []
    seen = {}  # normalised_key -> original entry, for deduplication

    tu_elements = list(root.iter())
    tu_list = [el for el in tu_elements if strip_ns(el.tag) == "tu"]

    if not tu_list:
        print(f"  [WARNING] No <tu> elements found in {filepath.name}.")
        return [], []

    for tu in tu_list:
        source_seg = ""
        target_seg = ""

        for tuv in tu:
            if strip_ns(tuv.tag) != "tuv":
                continue

            lang = (
                tuv.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", "")
                or tuv.attrib.get("xml:lang", "")
                or tuv.attrib.get("lang", "")
            ).lower()

            for child in tuv:
                if strip_ns(child.tag) == "seg":
                    text = (child.text or "").strip()
                    if lang.startswith(source_lang_prefix):
                        source_seg = text
                    elif lang.startswith(target_lang_prefix):
                        target_seg = text

        # Skip if either segment is empty
        if not source_seg or not target_seg:
            if verbose:
                print(f"  [SKIP] Empty segment: '{source_seg}' / '{target_seg}'")
            continue

        # ── Length filter ────────────────────────────────────────────────
        if length_filter and word_count(source_seg) > max_words:
            reason = f"too long ({word_count(source_seg)} words)"
            if verbose:
                print(f"  [SKIP] {reason}: '{source_seg}'")
            flagged.append({
                "english": source_seg,
                "pt_br": target_seg,
                "flag": f"SKIPPED — {reason}",
            })
            continue

        # ── Sentence punctuation filter ──────────────────────────────────
        if is_sentence(source_seg):
            reason = "ends with sentence punctuation"
            if verbose:
                print(f"  [SKIP] {reason}: '{source_seg}'")
            flagged.append({
                "english": source_seg,
                "pt_br": target_seg,
                "flag": f"SKIPPED — {reason}",
            })
            continue

        # ── Deduplication ────────────────────────────────────────────────
        key = normalise_key(source_seg)
        if key in seen:
            reason = f"duplicate of '{seen[key]['english']}'"
            if verbose:
                print(f"  [SKIP] {reason}: '{source_seg}'")
            flagged.append({
                "english": source_seg,
                "pt_br": target_seg,
                "flag": f"SKIPPED — {reason}",
            })
            continue
        seen[key] = {"english": source_seg, "pt_br": target_seg}

        # ── Build entry with inline flags ────────────────────────────────
        entry = {
            "english": source_seg,
            "pt_br": target_seg,
            "dnt_flag": "",
            "review_flag": "",
        }

        if is_identical(source_seg, target_seg):
            entry["dnt_flag"] = "DNT?"
            if verbose:
                print(f"  [FLAG] Identical source/target: '{source_seg}'")

        if looks_untranslated(source_seg, target_seg):
            entry["review_flag"] = "[REVIEW]"
            if verbose:
                print(f"  [FLAG] Possibly untranslated: '{source_seg}' / '{target_seg}'")

        clean.append(entry)

    return clean, flagged


# ---------------------------------------------------------------------------
# Markdown renderers
# ---------------------------------------------------------------------------

GLOSSARY_HEADER = (
    "| English | [pt-BR] |\n"
    "|---|---|\n"
)

REVIEW_HEADER = (
    "| English | [pt-BR] | Reason |\n"
    "|---|---|---|\n"
)


def entries_to_glossary_md(entries: list[dict], label: str = "") -> str:
    lines = []
    if label:
        lines.append(f"## {label}\n\n")
    lines.append(GLOSSARY_HEADER)
    for e in entries:
        en  = e["english"].replace("|", "\\|")
        pt  = e["pt_br"].replace("|", "\\|")
        if e.get("review_flag"):
            pt = f"{e['review_flag']} {pt}"
        lines.append(f"| {en} | {pt} |\n")
    return "".join(lines)


def flagged_to_review_md(entries: list[dict], label: str = "") -> str:
    if not entries:
        return ""
    lines = []
    if label:
        lines.append(f"## {label}\n\n")
    lines.append(REVIEW_HEADER)
    for e in entries:
        en   = e["english"].replace("|", "\\|")
        pt   = e["pt_br"].replace("|", "\\|")
        flag = e.get("flag", "").replace("|", "\\|")
        lines.append(f"| {en} | {pt} | {flag} |\n")
    return "".join(lines)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def collect_tmx_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() == ".tmx" else []
    return sorted(p for p in path.rglob("*") if p.suffix.lower() == ".tmx")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert TMX translation memories to Markdown glossary tables."
    )
    parser.add_argument(
        "input",
        help="Path to a .tmx file or a folder containing .tmx files.",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge all converted files into a single output file.",
    )
    parser.add_argument(
        "--outdir",
        default=None,
        help="Output directory. Defaults to same location as input.",
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=DEFAULT_MAX_WORDS,
        help=f"Maximum word count for a segment to be included (default: {DEFAULT_MAX_WORDS}).",
    )
    parser.add_argument(
        "--no-length-filter",
        action="store_true",
        help="Disable the word-count filter and include all segment lengths.",
    )
    parser.add_argument(
        "--source-lang",
        default="en",
        help="Source language prefix to match (default: en).",
    )
    parser.add_argument(
        "--target-lang",
        default="pt",
        help="Target language prefix to match (default: pt).",
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help="Export a separate _review.md file of skipped and flagged entries.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print details of every skipped or flagged entry.",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"Error: '{input_path}' does not exist.")
        sys.exit(1)

    files = collect_tmx_files(input_path)
    if not files:
        print("No .tmx files found.")
        sys.exit(0)

    # Resolve output directory
    if args.outdir:
        outdir = Path(args.outdir).resolve()
        outdir.mkdir(parents=True, exist_ok=True)
    elif input_path.is_file():
        outdir = input_path.parent
    else:
        outdir = input_path

    length_filter = not args.no_length_filter

    all_clean   = []  # for --merge
    all_flagged = []  # for --merge --review

    for fp in files:
        print(f"\nProcessing: {fp.name}")
        clean, flagged = parse_tmx(
            fp,
            source_lang_prefix=args.source_lang,
            target_lang_prefix=args.target_lang,
            max_words=args.max_words,
            length_filter=length_filter,
            verbose=args.verbose,
        )

        total = len(clean) + len(flagged)
        print(f"  → {total} segments found: {len(clean)} included, {len(flagged)} skipped/flagged.")

        if not clean and not flagged:
            continue

        if args.merge:
            all_clean.append((fp.stem, clean))
            all_flagged.append((fp.stem, flagged))
        else:
            # Write glossary
            out_path = outdir / (fp.stem + ".md")
            out_path.write_text(entries_to_glossary_md(clean), encoding="utf-8")
            print(f"  → Glossary written to: {out_path}")

            # Write review file if requested
            if args.review and flagged:
                review_path = outdir / (fp.stem + "_review.md")
                review_path.write_text(flagged_to_review_md(flagged), encoding="utf-8")
                print(f"  → Review file written to: {review_path}")

    # Handle --merge output
    if args.merge:
        if all_clean:
            merged_lines = ["# Merged TMX Glossary\n\n"]
            for label, entries in all_clean:
                merged_lines.append(entries_to_glossary_md(entries, label=label))
                merged_lines.append("\n")
            out_path = outdir / "merged_glossary.md"
            out_path.write_text("".join(merged_lines), encoding="utf-8")
            total_clean = sum(len(e) for _, e in all_clean)
            print(f"\nMerged {total_clean} entries from {len(all_clean)} file(s) → {out_path}")

        if args.review and any(f for _, f in all_flagged):
            review_lines = ["# Merged TMX Review\n\n"]
            for label, entries in all_flagged:
                if entries:
                    review_lines.append(flagged_to_review_md(entries, label=label))
                    review_lines.append("\n")
            review_path = outdir / "merged_review.md"
            review_path.write_text("".join(review_lines), encoding="utf-8")
            total_flagged = sum(len(f) for _, f in all_flagged)
            print(f"Review file: {total_flagged} flagged entries → {review_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
