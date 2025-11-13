# Translation Scripts

This directory contains scripts for managing translations in ccBitTorrent.

## Available Scripts

### 1. `generate_translations_hi_ur_fa_arc.py`
Generates complete translation files for Hindi, Urdu, Persian, and Aramaic.

**Usage:**
```bash
python -m ccbt.i18n.scripts.generate_translations_hi_ur_fa_arc
```

**What it does:**
- Reads the English .po file
- Applies translations from the translation dictionaries
- Creates/updates .po files for hi, ur, fa, arc
- Preserves Rich markup and format strings

### 2. `update_translations.py`
Updates translation files when new strings are added to the codebase.

**Usage:**
```bash
# Update all translations
python -m ccbt.i18n.scripts.update_translations

# Specify source directory
python -m ccbt.i18n.scripts.update_translations --source-dir /path/to/ccbt
```

**What it does:**
1. Extracts translatable strings from source code
2. Updates the .pot template file
3. Merges new strings into existing .po files using `msgmerge`

**Requirements:**
- GNU gettext tools (`msgmerge` command)
  - Windows: https://mlocati.github.io/articles/gettext-iconv-windows.html
  - Linux: `sudo apt-get install gettext`
  - macOS: `brew install gettext`

### 3. `check_completeness.py`
Checks translation completeness for all languages.

**Usage:**
```bash
# Check all languages
python -m ccbt.i18n.scripts.check_completeness

# Show untranslated strings for a specific language
python -m ccbt.i18n.scripts.check_completeness --lang hi
```

**What it reports:**
- Total strings
- Translated strings
- Untranslated strings
- Fuzzy translations (need review)
- Completion percentage

### 4. `validate_po.py`
Validates .po file format.

**Usage:**
```bash
python -m ccbt.i18n.scripts.validate_po
```

**What it checks:**
- Required header fields
- Valid msgid/msgstr pairs
- Proper string escaping
- No syntax errors

### 5. `compile_all.py`
Compiles all .po files to .mo files.

**Usage:**
```bash
python -m ccbt.i18n.scripts.compile_all
```

**What it does:**
- Compiles each .po file to .mo using `msgfmt`
- Reports success/failure for each language

**Requirements:**
- GNU gettext tools (`msgfmt` command)

### 6. `translation_workflow.py`
Orchestrates the complete translation workflow.

**Usage:**
```bash
# Run full workflow
python -m ccbt.i18n.scripts.translation_workflow

# Skip extraction (if .pot is already up to date)
python -m ccbt.i18n.scripts.translation_workflow --skip-extract

# Run specific step
python -m ccbt.i18n.scripts.translation_workflow --step check
```

**Workflow steps:**
1. Extract strings from codebase
2. Update translation files
3. Check completeness
4. Validate .po files
5. Compile .mo files

### 7. `setup_language.py`
Sets up a new language translation.

**Usage:**
```bash
python -m ccbt.i18n.scripts.setup_language <lang_code> [language_name] [team_name]
```

**Example:**
```bash
python -m ccbt.i18n.scripts.setup_language hi Hindi
```

## Translation Workflow

### Adding a New Language

1. **Setup the language:**
   ```bash
   python -m ccbt.i18n.scripts.setup_language <lang_code> <language_name>
   ```

2. **Translate strings:**
   - Edit `ccbt/i18n/locales/<lang>/LC_MESSAGES/ccbt.po`
   - Fill in `msgstr` fields with translations
   - Preserve Rich markup tags: `[green]`, `[yellow]`, etc.
   - Preserve format strings: `{count}`, `{name}`, etc.

3. **Check completeness:**
   ```bash
   python -m ccbt.i18n.scripts.check_completeness --lang <lang_code>
   ```

4. **Validate:**
   ```bash
   python -m ccbt.i18n.scripts.validate_po
   ```

5. **Compile:**
   ```bash
   python -m ccbt.i18n.scripts.compile_all
   ```

### Updating Translations

When new strings are added to the codebase:

1. **Run update workflow:**
   ```bash
   python -m ccbt.i18n.scripts.translation_workflow
   ```

2. **Review new strings:**
   - Check for untranslated strings marked with `#, fuzzy`
   - Translate new strings in .po files
   - Remove fuzzy markers after translation

3. **Re-compile:**
   ```bash
   python -m ccbt.i18n.scripts.compile_all
   ```

## Translation Guidelines

### Preserving Rich Markup

Rich markup tags must be preserved in translations:

```po
msgid "[green]Download completed[/green]"
msgstr "[green]डाउनलोड पूर्ण[/green]"  # Hindi - markup preserved
```

### Format Strings

Use named parameters in format strings:

```po
msgid "Downloaded {count} files"
msgstr "{count} फ़ाइलें डाउनलोड की गईं"  # Hindi - parameter preserved
```

### Pluralization

Plural forms are handled automatically by gettext based on the `Plural-Forms` header in each .po file.

### RTL Languages

For right-to-left languages (Urdu, Persian, Aramaic):
- Test terminal RTL rendering
- Verify table alignment
- Check interactive prompts

## Troubleshooting

### msgmerge/msgfmt not found

Install GNU gettext tools:
- **Windows**: Download from https://mlocati.github.io/articles/gettext-iconv-windows.html
- **Linux**: `sudo apt-get install gettext`
- **macOS**: `brew install gettext`

### Translation not appearing

1. Check that .mo file is compiled: `python -m ccbt.i18n.scripts.compile_all`
2. Verify locale is set: `export CCBT_LOCALE=<lang>`
3. Check .po file has translations (not empty `msgstr`)

### Encoding issues

All .po files use UTF-8 encoding. Ensure your editor is configured for UTF-8.

## File Structure

```
ccbt/i18n/
├── locales/
│   ├── en/LC_MESSAGES/
│   │   ├── ccbt.po      # English (source)
│   │   └── ccbt.pot     # Template
│   ├── hi/LC_MESSAGES/
│   │   ├── ccbt.po      # Hindi translations
│   │   └── ccbt.mo      # Compiled binary
│   ├── ur/LC_MESSAGES/
│   │   ├── ccbt.po      # Urdu translations
│   │   └── ccbt.mo      # Compiled binary
│   └── ...
└── scripts/
    ├── generate_translations_hi_ur_fa_arc.py
    ├── update_translations.py
    ├── check_completeness.py
    ├── validate_po.py
    ├── compile_all.py
    ├── translation_workflow.py
    └── setup_language.py
```

## See Also

- [Translation Plan](../docs/translation-plan-hi-ur-fa-arc.md)
- [i18n Documentation](../../docs/i18n.md)

