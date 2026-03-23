# Translation Scripts

This directory contains scripts for managing translations in ccBitTorrent.

Extraction lives in [`ccbt/i18n/extract.py`](../extract.py) and is run as `python -m ccbt.i18n.extract` (not under `scripts/`).

## Local vs CI

- **Local (optional):** Run extract when you change user-facing strings; run `validate_po` when `.po` files change; merge catalogs with `msgmerge` or `translation_workflow --step update` (requires GNU gettext on `PATH`).
- **CI (approval-required):** The `i18n` job in `.github/workflows/ci.yml` runs extract, `validate_po`, and `check_completeness`. There is no automated gate that every `_()` in source appears in the `.pot`; use extract before committing template changes.
- **Manual full pipeline:** `.github/workflows/i18n-manual.yml` (`workflow_dispatch`) runs extract, `msgmerge` on all locales, `fill_english`, validate, completeness report, and `compile_all`.

## Available Scripts

### 1. `generate_hi_ur_fa_arc_translations.py`

Generates translation files for Hindi, Urdu, Persian, and Aramaic from project dictionaries.

**Usage:**

```bash
python -m ccbt.i18n.scripts.generate_hi_ur_fa_arc_translations
```

### 2. Merging catalogs (`msgmerge`)

There is no Python `update_translations` module in this tree. After regenerating `ccbt/i18n/locales/en/LC_MESSAGES/ccbt.pot` with extract, merge it into every `*/LC_MESSAGES/ccbt.po`:

```bash
POT=ccbt/i18n/locales/en/LC_MESSAGES/ccbt.pot
for po in ccbt/i18n/locales/*/LC_MESSAGES/ccbt.po; do
  msgmerge --update --backup=none --sort-output "$po" "$POT"
done
```

Or run `python -m ccbt.i18n.scripts.translation_workflow` (or `--step update` after extract).

**Requirements:** GNU gettext (`msgmerge` on `PATH`). Windows: [gettext for Windows](https://mlocati.github.io/articles/gettext-iconv-windows.html); Linux: `sudo apt install gettext`; macOS: `brew install gettext`.

### 3. `check_completeness.py`

Reports translation completeness per locale against the canonical `.pot` msgids.

**Usage:**

```bash
python -m ccbt.i18n.scripts.check_completeness
python -m ccbt.i18n.scripts.check_completeness --lang hi
```

### 4. `fill_english.py`

Fills empty English `msgstr` entries with their `msgid`. The canonical entry point is `python -m ccbt.i18n.fill_english`; `ccbt.i18n.scripts.fill_english` remains a compatibility wrapper.

**Usage:**

```bash
python -m ccbt.i18n.fill_english
python -m ccbt.i18n.scripts.fill_english
```

### 5. `validate_po.py`

Validates `.po` file structure and headers.

**Usage:**

```bash
python -m ccbt.i18n.scripts.validate_po
```

### 6. `compile_all.py`

Compiles each `.po` to `.mo` using `msgfmt`.

**Usage:**

```bash
python -m ccbt.i18n.scripts.compile_all
```

**.mo and version control:** The project may ignore `*.mo` in `.gitignore`. Run `compile_all` locally after updating `.po` files so the app can load translations.

### 7. `translation_workflow.py`

Orchestrates extract → msgmerge → check_completeness → validate_po → compile_all.

**Usage:**

```bash
python -m ccbt.i18n.scripts.translation_workflow
python -m ccbt.i18n.scripts.translation_workflow --skip-extract
python -m ccbt.i18n.scripts.translation_workflow --step update
```

**Workflow steps:**

1. Extract strings (`extract.py` under `ccbt/i18n/`)
2. Merge `.pot` into each locale `.po` (`msgmerge`)
3. Check completeness
4. Validate `.po` files
5. Compile `.mo` files

### Other generators

- `generate_translations.py` (es, eu, fr) — merges hand-maintained data with `ccbt/i18n/locale_data/{es,eu,fr}_supplement.json`.
- `comprehensive_translations.py` (ja, ko, th, zh)
- `generate_african_translations.py` (sw, ha, yo)
- `add_rich_markup_translations.py`

### Legacy: `check_coverage.py`

Small standalone script for rough per-file counts; it is **not** the same as a source-vs-template coverage tool and uses paths that may not match the current tree. Prefer `check_completeness` for workflow use.

## Translation Workflow

### Adding a New Language

1. Create `ccbt/i18n/locales/<lang>/LC_MESSAGES/` and copy `locales/en/LC_MESSAGES/ccbt.pot` to `ccbt.po` (or copy `en/ccbt.po` as a starting point). Set `Language:` and `Plural-Forms` in the header.
2. Translate strings in `ccbt.po`; preserve Rich markup and `{named}` placeholders.
3. `python -m ccbt.i18n.scripts.check_completeness --lang <lang_code>`
4. `python -m ccbt.i18n.scripts.validate_po`
5. `python -m ccbt.i18n.scripts.compile_all`

### Updating Translations After Code Changes

1. `python -m ccbt.i18n.extract ccbt ccbt/i18n/locales/en/LC_MESSAGES/ccbt.pot`
2. Merge: `translation_workflow --step update` or the `msgmerge` loop above
3. `python -m ccbt.i18n.fill_english` (for `en`)
4. Run the appropriate generator if applicable, or translate new msgids manually
5. `validate_po`, `check_completeness`, then `compile_all`

## Translation Guidelines

### Preserving Rich Markup

```po
msgid "[green]Download completed[/green]"
msgstr "[green]डाउनलोड पूर्ण[/green]"
```

### Format Strings

Use named parameters: `_("Downloaded {count} files").format(count=n)`.

### RTL Languages

**ur**, **fa**, **arc**: test terminals and Rich/Textual layout; run `check_completeness` and visual QA.

## Troubleshooting

### msgmerge / msgfmt not found

Install GNU gettext (see requirements under **Merging catalogs**).

### Translation not appearing

1. Compile: `python -m ccbt.i18n.scripts.compile_all`
2. `export CCBT_LOCALE=<lang>`
3. Ensure `msgstr` is non-empty where expected

## Template (.pot) location

Canonical template: `ccbt/i18n/locales/en/LC_MESSAGES/ccbt.pot`. Run extract before msgmerge if the template may be stale.

## File Structure (scripts subset)

```
ccbt/i18n/
├── extract.py
├── locales/
│   └── <lang>/LC_MESSAGES/ccbt.po
└── scripts/
    ├── check_completeness.py
    ├── check_coverage.py          # legacy
    ├── compile_all.py
    ├── fill_english.py
    ├── generate_hi_ur_fa_arc_translations.py
    ├── translation_workflow.py
    ├── validate_po.py
    └── ...
```

## See Also

- [i18n patterns](../../../.cursor/rules/i18n-patterns.mdc) (Cursor rule)
- Project docs under `docs/en/implementation-plans/` for language plans
