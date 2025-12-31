# Custom Language Templates Setup

## Problems Solved

### 1. Missing Language Templates

Material for MkDocs theme doesn't include language templates for:
- Hausa (ha)
- Kiswahili (sw)  
- Yorùbá (yo)
- Aramaic (arc)

This caused build failures with error:
```
jinja2.exceptions.TemplateNotFound: 'partials/languages/ha.html' not found
```

### 2. Aramaic Locale Code Validation

The `mkdocs-static-i18n` plugin validates locale codes strictly using ISO-639-1 (two-letter) standard. However, Aramaic only has an ISO-639-2 (three-letter) code 'arc', which caused validation errors:

```
ERROR - Language code values must be either ISO-639-1 lower case or represented 
with their territory/region/country codes, received 'arc'
```

This is solved by patching the plugin's `Locale.run_validation` method in `dev/build_docs_patched_clean.py` to allow 'arc' as a special case.

## Solution

Created custom language templates in `docs/overrides/partials/languages/` that extend Material theme's template system.

## Files Created

1. `docs/overrides/partials/languages/ha.html` - Hausa template (LTR)
2. `docs/overrides/partials/languages/sw.html` - Kiswahili template (LTR)
3. `docs/overrides/partials/languages/yo.html` - Yorùbá template (LTR)
4. `docs/overrides/partials/languages/arc.html` - Aramaic template (RTL)

## Configuration Changes

### 1. Updated `dev/mkdocs.yml`

1. Added `custom_dir` to theme configuration:
   ```yaml
   theme:
     custom_dir: ../docs/overrides
   ```

2. Re-enabled builds for these languages:
   ```yaml
   - locale: ha
     build: true
   - locale: sw
     build: true
   - locale: yo
     build: true
   - locale: arc
     build: true
   ```

### 2. Patched Plugin Validation

Updated `dev/build_docs_patched_clean.py` to patch the `Locale.run_validation` method:

```python
from mkdocs_static_i18n.config import Locale

original_run_validation = Locale.run_validation

def patched_run_validation(self, value):
    """Allow 'arc' (Aramaic) locale code."""
    if value and value.lower() == 'arc':
        return value
    return original_run_validation(self, value)

Locale.run_validation = patched_run_validation
```

This allows the 'arc' locale code to pass validation even though it's not ISO-639-1 compliant.

## Testing

To verify the setup works:

```bash
uv run mkdocs build -f dev/mkdocs.yml
```

The build should now complete successfully without the `TemplateNotFound` error.

## Next Steps

1. **Add Translations**: Replace English placeholder text in templates with proper translations
2. **Test RTL Support**: Verify Aramaic (arc) RTL rendering works correctly
3. **Contribute**: If you're a native speaker, contribute translations via pull request

## Troubleshooting

If the build still fails:

1. Verify `custom_dir` path is correct relative to where mkdocs.yml is located
2. Check that template files exist in `docs/overrides/partials/languages/`
3. Ensure template syntax is valid Jinja2
4. Check Material theme version compatibility

## References

- [Material for MkDocs - Customization](https://squidfunk.github.io/mkdocs-material/customization/)
- [Material for MkDocs - Changing the Language](https://squidfunk.github.io/mkdocs-material/setup/changing-the-language/)

