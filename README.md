# trados-termbase-converter

Python toolkit that converts Trados MultiTerm termbases (.tbx, .csv) and translation memories (.tmx) into structured Markdown glossary tables for English-to-Portuguese (pt-BR) localization workflows.

---

## Scripts

### `termbase_to_markdown.py` — TBX and CSV converter

Converts Trados MultiTerm termbase exports into a Markdown glossary table with the following columns:

| English | Definition | Part of Speech | Source Case Sensitive? | Mandatory DNT | Portuguese Variations (Brazil) | [pt-BR] |

The columns Definition, Part of Speech, Source Case Sensitive?, Mandatory DNT, and Portuguese Variations are left blank for manual completion. Only English and [pt-BR] are populated automatically.

**Usage**

```bash
# Convert one file
python3 termbase_to_markdown.py file.tbx
python3 termbase_to_markdown.py file.csv

# Convert a folder — one .md file per termbase
python3 termbase_to_markdown.py "/path/to/Trados Termbases" --outdir ~/Desktop/Glossaries

# Convert a folder — merge all into one file
python3 termbase_to_markdown.py "/path/to/Trados Termbases" --merge --outdir ~/Desktop/Glossaries
```

---

### `tmx_to_markdown.py` — TMX converter

Converts Trados translation memory (.tmx) files into a clean two-column Markdown glossary table:

| English | [pt-BR] |

Unlike TBX/CSV termbases, TMX files contain full translated segments rather than curated term pairs. This script applies smart pre-filtering to extract only glossary-worthy entries:

- **Length filter** — skips segments above a configurable word limit (default: 6 words)
- **Sentence filter** — skips segments ending with sentence-final punctuation
- **Identity filter** — flags entries where source and target are identical (DNT candidates)
- **Deduplication** — normalised exact-match deduplication with warnings
- **Untranslated flag** — marks entries where the target appears to still be in English

**Usage**

```bash
# Convert one file
python3 tmx_to_markdown.py file.tmx

# Convert a folder — one .md file per TMX
python3 tmx_to_markdown.py "/path/to/TM folder" --outdir ~/Desktop/Glossaries

# Convert a folder — merge all into one file
python3 tmx_to_markdown.py "/path/to/TM folder" --merge --outdir ~/Desktop/Glossaries

# Include a review file of skipped/flagged entries
python3 tmx_to_markdown.py file.tmx --review --outdir ~/Desktop/Glossaries

# Adjust the word limit (default: 6)
python3 tmx_to_markdown.py file.tmx --max-words 10

# Disable the length filter entirely
python3 tmx_to_markdown.py file.tmx --no-length-filter
```

---

## Requirements

- Python 3.10 or later
- No additional packages required — uses Python standard library only

Verify your Python version:

```bash
python3 --version
```

---

## Output

### termbase_to_markdown.py

| English | Definition | Part of Speech | Source Case Sensitive? | Mandatory DNT | Portuguese Variations (Brazil) | [pt-BR] |
|---|---|---|---|---|---|---|
| Big Room Planning | | | | | | Big Room Planning |
| Iterative Development | | | | | | Desenvolvimento Iterativo |
| Continuous Integration | | | | | | Integração Contínua |
| Sprint | | | | | | Sprint |

### tmx_to_markdown.py

| English | [pt-BR] |
|---|---|
| Product Owner | Dono do Produto |
| Iterative Development | Desenvolvimento Iterativo |
| Sprint Review | Revisão de Sprint |
| DNT? Scrum | Scrum |

---

## Tips

- Always quote folder paths that contain spaces: `"/path/to/Trados Termbases"` not `Trados\ Termbases`
- Use `--review` with TMX files to capture skipped entries for manual inspection
- Use `--merge` when building a consolidated master glossary across all clients
- Preview `.md` output in VS Code with `Cmd+Shift+V` (macOS) or `Ctrl+Shift+V` (Windows)

---

## Full Guide

See [`Trados_Termbase_to_Markdown_Guide.md`](./Trados_Termbase_to_Markdown_Guide.md) for a complete step-by-step walkthrough including file format anatomy, troubleshooting, and GitHub publishing instructions.

---

*Built for EN→PT-BR localization workflows. Adaptable to any language pair via the `--source-lang` and `--target-lang` flags in `tmx_to_markdown.py`.*
