# Custom Theme Overrides

This directory contains custom theme overrides for Material for MkDocs to support languages that are not included by default in the theme.

## Structure

```
overrides/
└── partials/
    └── languages/
        ├── ha.html  # Hausa language template
        ├── sw.html  # Kiswahili language template
        ├── yo.html  # Yorùbá language template
        └── arc.html # Aramaic language template (RTL)
```

## Language Templates

These templates provide the necessary translations for Material theme's UI elements. They are based on the English template structure and can be extended with proper translations as needed.

### Hausa (ha)
- Direction: LTR (Left-to-Right)
- Status: Basic template with English fallback

### Kiswahili (sw)
- Direction: LTR (Left-to-Right)
- Status: Basic template with English fallback

### Yorùbá (yo)
- Direction: LTR (Left-to-Right)
- Status: Basic template with English fallback

### Aramaic (arc)
- Direction: RTL (Right-to-Left)
- Script: Syriac (ܐܪܡܝܐ)
- Status: Basic template with English fallback, RTL support enabled

## Adding Translations

To add proper translations for these languages:

1. Edit the corresponding `.html` file in `partials/languages/`
2. Replace English text values with translations
3. Maintain the same key structure
4. Test the build: `uv run mkdocs build -f dev/mkdocs.yml`

## Contributing

If you're a native speaker of any of these languages and would like to contribute proper translations, please:

1. Fork the repository
2. Update the language template file
3. Submit a pull request

## References

- [Material for MkDocs - Customization](https://squidfunk.github.io/mkdocs-material/customization/)
- [Material for MkDocs - Changing the Language](https://squidfunk.github.io/mkdocs-material/setup/changing-the-language/)













