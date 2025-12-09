# Translation Guide

This guide explains how to contribute translations to the ccBitTorrent documentation.

## Overview

ccBitTorrent documentation supports multiple languages using the `mkdocs-static-i18n` plugin. The documentation is organized by language in separate directories under `docs/`.

## Language Structure

Documentation files are organized as follows:

```
docs/
├── en/          # English (default)
├── es/          # Spanish
├── fr/          # French
├── ja/          # Japanese
├── ko/          # Korean
├── hi/          # Hindi
├── ur/          # Urdu
├── fa/          # Persian
├── th/          # Thai
└── zh/          # Chinese
```

## Adding a New Translation

### Step 1: Create Language Directory

If the language directory doesn't exist, create it:

```bash
mkdir -p docs/{language_code}
```

### Step 2: Translate Content

1. Copy the English version of the file you want to translate
2. Translate the content while maintaining:
   - Markdown formatting
   - Code examples (keep in original language)
   - Links to other documentation pages (update paths if needed)
   - File structure and organization

### Step 3: Update Navigation

If adding a new language, update `dev/mkdocs.yml` to include it in the i18n plugin configuration:

```yaml
plugins:
  - i18n:
      default_language: en
      languages:
        en: English
        es: Español
        # Add your language here
        your_lang: Your Language Name
```

## Translation Guidelines

### Keep Code Examples

Code examples should remain in their original language (usually English). Only translate:
- Comments in code (if appropriate)
- Documentation text
- User-facing messages

### Maintain Links

When translating, update internal links to point to the translated versions:

```markdown
# English version
[Getting Started](getting-started.md)

# Translated version (Spanish)
[Inicio](getting-started.md)
```

### Preserve Structure

Maintain the same file structure and organization as the English version. This ensures consistency across languages.

### Translation Quality

- Use clear, concise language
- Maintain technical accuracy
- Follow the style of the original English documentation
- Test links and code examples after translation

## Integration with Code i18n

The documentation i18n system is separate from the code i18n system in `ccbt/i18n/`. However, both systems support the same languages:

- English (en)
- Spanish (es)
- French (fr)
- Japanese (ja)
- Korean (ko)
- Hindi (hi)
- Urdu (ur)
- Persian (fa)
- Thai (th)
- Chinese (zh)

## Contributing Translations

1. Fork the repository
2. Create a branch for your translation work
3. Add or update translated files
4. Test the documentation build locally
5. Submit a pull request

## Testing Translations

To test your translations locally:

```bash
uv run mkdocs build -f dev/mkdocs.yml
uv run mkdocs serve -f dev/mkdocs.yml
```

Then navigate to `http://localhost:8000` and use the language switcher to view your translations.

## Questions?

If you have questions about translations, please:
- Open an issue on GitHub
- Join our [Discord](https://discord.gg/ccbittorrent) community
- Check the [Contributing Guide](../contributing.md)

Thank you for helping make ccBitTorrent accessible to users worldwide!







This guide explains how to contribute translations to the ccBitTorrent documentation.

## Overview

ccBitTorrent documentation supports multiple languages using the `mkdocs-static-i18n` plugin. The documentation is organized by language in separate directories under `docs/`.

## Language Structure

Documentation files are organized as follows:

```
docs/
├── en/          # English (default)
├── es/          # Spanish
├── fr/          # French
├── ja/          # Japanese
├── ko/          # Korean
├── hi/          # Hindi
├── ur/          # Urdu
├── fa/          # Persian
├── th/          # Thai
└── zh/          # Chinese
```

## Adding a New Translation

### Step 1: Create Language Directory

If the language directory doesn't exist, create it:

```bash
mkdir -p docs/{language_code}
```

### Step 2: Translate Content

1. Copy the English version of the file you want to translate
2. Translate the content while maintaining:
   - Markdown formatting
   - Code examples (keep in original language)
   - Links to other documentation pages (update paths if needed)
   - File structure and organization

### Step 3: Update Navigation

If adding a new language, update `dev/mkdocs.yml` to include it in the i18n plugin configuration:

```yaml
plugins:
  - i18n:
      default_language: en
      languages:
        en: English
        es: Español
        # Add your language here
        your_lang: Your Language Name
```

## Translation Guidelines

### Keep Code Examples

Code examples should remain in their original language (usually English). Only translate:
- Comments in code (if appropriate)
- Documentation text
- User-facing messages

### Maintain Links

When translating, update internal links to point to the translated versions:

```markdown
# English version
[Getting Started](getting-started.md)

# Translated version (Spanish)
[Inicio](getting-started.md)
```

### Preserve Structure

Maintain the same file structure and organization as the English version. This ensures consistency across languages.

### Translation Quality

- Use clear, concise language
- Maintain technical accuracy
- Follow the style of the original English documentation
- Test links and code examples after translation

## Integration with Code i18n

The documentation i18n system is separate from the code i18n system in `ccbt/i18n/`. However, both systems support the same languages:

- English (en)
- Spanish (es)
- French (fr)
- Japanese (ja)
- Korean (ko)
- Hindi (hi)
- Urdu (ur)
- Persian (fa)
- Thai (th)
- Chinese (zh)

## Contributing Translations

1. Fork the repository
2. Create a branch for your translation work
3. Add or update translated files
4. Test the documentation build locally
5. Submit a pull request

## Testing Translations

To test your translations locally:

```bash
uv run mkdocs build -f dev/mkdocs.yml
uv run mkdocs serve -f dev/mkdocs.yml
```

Then navigate to `http://localhost:8000` and use the language switcher to view your translations.

## Questions?

If you have questions about translations, please:
- Open an issue on GitHub
- Join our [Discord](https://discord.gg/ccbittorrent) community
- Check the [Contributing Guide](../contributing.md)

Thank you for helping make ccBitTorrent accessible to users worldwide!

































































































































































































