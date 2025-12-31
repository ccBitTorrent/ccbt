# Read the Docs Compatibility

## ✅ Yes, This Will Work on Read the Docs!

All custom language templates and the Aramaic locale patch are fully compatible with Read the Docs builds.

## How It Works on Read the Docs

### 1. **Patched Build Script**

Read the Docs uses the same patched build script (`dev/build_docs_patched_clean.py`) that:
- ✅ Patches `Locale.run_validation` to allow 'arc' (Aramaic) locale code
- ✅ Handles files without alternates attribute
- ✅ Applies all necessary i18n plugin fixes

**Configuration in `.readthedocs.yaml`:**
```yaml
build:
  commands:
    - python dev/build_docs_patched_clean.py
```

### 2. **Custom Theme Overrides**

The custom language templates in `docs/overrides/partials/languages/` are automatically loaded because:
- ✅ `custom_dir: docs/overrides` is correctly configured in `dev/mkdocs.yml`
- ✅ Material theme resolves `custom_dir` relative to project root (where Read the Docs runs)
- ✅ All template files are committed to the repository

### 3. **Path Resolution**

- **Project Root**: Read the Docs runs from repository root
- **MkDocs Config**: `dev/mkdocs.yml` (specified in `.readthedocs.yaml`)
- **Custom Dir**: `docs/overrides` (resolved from project root)
- **Templates**: `docs/overrides/partials/languages/*.html`

## Verification Checklist

- [x] `.readthedocs.yaml` uses `dev/build_docs_patched_clean.py`
- [x] `dev/mkdocs.yml` has `custom_dir: docs/overrides`
- [x] All language templates exist in `docs/overrides/partials/languages/`
- [x] Aramaic locale patch is in `dev/build_docs_patched_clean.py`
- [x] All files are committed to repository

## Testing Locally

To verify Read the Docs compatibility locally:

```bash
# Simulate Read the Docs build
python dev/build_docs_patched_clean.py

# Or use the logging script
uv run python dev/build_docs_with_logs.py
```

## Troubleshooting

If builds fail on Read the Docs:

1. **Check Build Logs**: Read the Docs provides detailed build logs
2. **Verify Paths**: Ensure `custom_dir` path is correct relative to project root
3. **Check Patches**: Verify `build_docs_patched_clean.py` patches are applied
4. **Template Files**: Ensure all template files are committed

## References

- [Read the Docs Configuration](https://docs.readthedocs.io/en/stable/config-file/v2.html)
- [Material for MkDocs - Customization](https://squidfunk.github.io/mkdocs-material/customization/)








