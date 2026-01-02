# Custom Language Templates

This directory contains custom language templates for Material for MkDocs theme to support languages that are not included by default.

## Supported Languages

### Hausa (ha)
- **File**: `ha.html`
- **Direction**: LTR
- **Status**: Template created, ready for translation

### Kiswahili (sw)
- **File**: `sw.html`
- **Direction**: LTR
- **Status**: Template created, ready for translation

### Yorùbá (yo)
- **File**: `yo.html`
- **Direction**: LTR
- **Status**: Template created, ready for translation

### Aramaic (arc)
- **File**: `arc.html`
- **Direction**: RTL (Right-to-Left)
- **Script**: Syriac (ܐܪܡܝܐ)
- **Status**: Template created with RTL support, ready for translation

## Template Structure

Each template follows the Material theme structure:

```jinja2
{% macro t(key) %}{{ {
  "language": "locale_code",
  "direction": "ltr" or "rtl",
  "action.edit": "Translation...",
  ...
}[key] }}{% endmacro %}
```

## Translation Status

Currently, all templates use English text as placeholders. To add proper translations:

1. Edit the corresponding `.html` file
2. Replace English values with translations
3. Maintain the exact key structure
4. Test with: `uv run mkdocs build -f dev/mkdocs.yml`

## Configuration

The templates are automatically loaded via `dev/mkdocs.yml`:

```yaml
theme:
  custom_dir: ../docs/overrides
```

This tells Material theme to look for custom templates in `docs/overrides/` directory.

## Contributing Translations

If you're a native speaker, please contribute translations by:

1. Editing the language template file
2. Translating all string values
3. Testing the build
4. Submitting a pull request

## References

- [Material for MkDocs - Customization](https://squidfunk.github.io/mkdocs-material/customization/)
- [Material for MkDocs - Changing the Language](https://squidfunk.github.io/mkdocs-material/setup/changing-the-language/)
















