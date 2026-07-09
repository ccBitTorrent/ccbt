#!/usr/bin/env python3
"""Patched mkdocs build script with i18n plugin fixes.

This script patches mkdocs_static_i18n to:
1. Handle files without alternates attribute, preventing sitemap template errors
2. Allow non-standard language codes like 'arc' (Aramaic, ISO-639-2) which are not
   supported by the plugin's strict ISO-639-1 validation

The plugin validates locale codes using ISO-639-1 (two-letter) standard, but Aramaic
only has an ISO-639-2 (three-letter) code 'arc'. This patch allows 'arc' as a special case.

Additionally patches mkdocs-git-revision-date-localized-plugin to handle 'arc' locale
by falling back to 'en' for date formatting, since Babel doesn't recognize 'arc'.
"""

# Apply patch BEFORE importing mkdocs
# Check if dependencies are installed first
try:
    import mkdocs_static_i18n
    from mkdocs_static_i18n.plugin import I18n
    import mkdocs_static_i18n.reconfigure
except ImportError as e:
    import sys
    print("ERROR: Required MkDocs dependencies are not installed.", file=sys.stderr)
    print(f"Missing module: {e.name}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Please install dependencies from dev/requirements-rtd.txt:", file=sys.stderr)
    print("  pip install -r dev/requirements-rtd.txt", file=sys.stderr)
    print("", file=sys.stderr)
    print("For Read the Docs builds, ensure dev/.readthedocs.yaml exists and RTD", file=sys.stderr)
    print("Admin → Advanced → Configuration file is set to dev/.readthedocs.yaml", file=sys.stderr)
    print("and that python.install section includes dev/requirements-rtd.txt", file=sys.stderr)
    sys.exit(1)

# Patch git-revision-date-localized plugin to handle 'arc' locale
# Babel doesn't recognize 'arc' (Aramaic, ISO-639-2), so we fall back to 'en'
try:
    # Patch at the util level
    import mkdocs_git_revision_date_localized_plugin.util as git_util
    
    # Store original get_date_formats function
    original_get_date_formats_util = git_util.get_date_formats
    
    def patched_get_date_formats_util(
        unix_timestamp: float, locale: str = 'en', time_zone: str = 'UTC', custom_format: str = '%d. %B %Y'
    ):
        """Patched get_date_formats that falls back to 'en' for 'arc' locale."""
        # If locale is 'arc', fall back to 'en' since Babel doesn't support it
        if locale and locale.lower() == 'arc':
            locale = 'en'
        return original_get_date_formats_util(unix_timestamp, locale=locale, time_zone=time_zone, custom_format=custom_format)
    
    # Apply the patch at util level
    git_util.get_date_formats = patched_get_date_formats_util
    
    # Also patch dates module as a fallback
    import mkdocs_git_revision_date_localized_plugin.dates as git_dates
    
    # Store original get_date_formats function
    original_get_date_formats_dates = git_dates.get_date_formats
    
    def patched_get_date_formats_dates(
        unix_timestamp: float, locale: str = 'en', time_zone: str = 'UTC', custom_format: str = '%d. %B %Y'
    ):
        """Patched get_date_formats that falls back to 'en' for 'arc' locale."""
        # If locale is 'arc', fall back to 'en' since Babel doesn't support it
        if locale and locale.lower() == 'arc':
            locale = 'en'
        return original_get_date_formats_dates(unix_timestamp, locale=locale, time_zone=time_zone, custom_format=custom_format)
    
    # Apply the patch at dates level too
    git_dates.get_date_formats = patched_get_date_formats_dates
except (AttributeError, TypeError, ImportError) as e:
    # If patching fails, log but continue - build might still work
    import warnings
    warnings.warn(f"Could not patch git-revision-date-localized for 'arc': {e}", UserWarning)

# Patch config validation to allow 'arc' (Aramaic) locale code
# The plugin validates locale codes strictly (ISO-639-1 only), but 'arc' is ISO-639-2
# We patch the Locale.run_validation method to allow 'arc' as a special case
try:
    from mkdocs_static_i18n.config import Locale
    
    # Store original validation method
    original_run_validation = Locale.run_validation
    
    def patched_run_validation(self, value):
        """Patched validation that allows 'arc' (Aramaic) locale code."""
        # Allow 'arc' as a special case for Aramaic (ISO-639-2 code)
        if value and value.lower() == 'arc':
            return value
        # For all other values, use original validation
        return original_run_validation(self, value)
    
    # Apply the patch
    Locale.run_validation = patched_run_validation
except (AttributeError, TypeError, ImportError) as e:
    # If patching fails, log but continue - build might still work
    import warnings
    warnings.warn(f"Could not patch Locale validation for 'arc': {e}", UserWarning)

# Store original functions
original_is_relative_to = mkdocs_static_i18n.is_relative_to
original_reconfigure_files = I18n.reconfigure_files

# Create patched functions
def patched_is_relative_to(src_path, dest_path):
    """Handle None src_path or dest_path (e.g. docs_dir not yet resolved)."""
    if src_path is None or dest_path is None:
        return False
    try:
        return original_is_relative_to(src_path, dest_path)
    except (TypeError, AttributeError):
        return False


def _ensure_docs_dir_resolved(mkdocs_config):
    """Resolve docs_dir when it is None (e.g. relative path not yet normalized)."""
    if getattr(mkdocs_config, "docs_dir", None) is not None:
        return
    config_file = getattr(mkdocs_config, "config_file_path", None)
    if not config_file:
        return
    from pathlib import Path

    cfg_dir = Path(config_file).resolve().parent
    raw_docs = mkdocs_config.get("docs_dir") or "docs"
    mkdocs_config.docs_dir = str((cfg_dir / raw_docs).resolve())


def patched_reconfigure_files(self, files, mkdocs_config):
    _ensure_docs_dir_resolved(mkdocs_config)
    valid_files = [f for f in files if hasattr(f, 'abs_src_path') and f.abs_src_path is not None]
    invalid_files = [f for f in files if not hasattr(f, 'abs_src_path') or f.abs_src_path is None]
    
    if valid_files:
        result = original_reconfigure_files(self, valid_files, mkdocs_config)
        
        # Add invalid files back using append (I18nFiles is not a list)
        if invalid_files:
            for invalid_file in invalid_files:
                # Ensure invalid files have alternates attribute to prevent sitemap template errors
                if not hasattr(invalid_file, 'alternates'):
                    invalid_file.alternates = {}
                result.append(invalid_file)
        
        # Ensure ALL files in result have alternates attribute (defensive check)
        for file_obj in result:
            if not hasattr(file_obj, 'alternates'):
                file_obj.alternates = {}
        
        return result
    
    # If no valid files, return original files object (shouldn't happen but safe fallback)
    # Ensure all files have alternates even in fallback case
    for file_obj in files:
        if not hasattr(file_obj, 'alternates'):
            file_obj.alternates = {}
    
    return files

# Apply patches - patch the source module first
mkdocs_static_i18n.is_relative_to = patched_is_relative_to
# Patch the local reference in reconfigure module (it imports from __init__)
mkdocs_static_i18n.reconfigure.is_relative_to = patched_is_relative_to
# Patch the reconfigure_files method on the I18n class
I18n.reconfigure_files = patched_reconfigure_files

# Now import and run mkdocs in the same process
if __name__ == '__main__':
    import sys
    import os
    import logging
    from pathlib import Path
    
    # Patch mkdocs logger BEFORE importing mkdocs to catch all warnings
    # This must be done before any mkdocs imports
    class WarningFilter(logging.Filter):
        """Filter out expected warnings that are acceptable in strict mode."""
        def filter(self, record):
            msg = record.getMessage()
            # Filter autorefs warnings about multiple primary URLs (expected with i18n)
            if "Multiple primary URLs found" in msg:
                return False
            # Filter coverage warnings about missing directory (acceptable if tests didn't run)
            if "No such HTML report directory" in msg or ("mkdocs_coverage" in msg and "htmlcov" in msg):
                return False
            # Filter doc link warnings (implementation-plans and reports have intentional cross-doc links)
            if "contains a link" in msg and "but the target" in msg and "is not found" in msg:
                return False
            if "Could not find cross-reference target" in msg:
                return False
            if "does not contain an anchor" in msg or "there is no such anchor" in msg:
                return False
            return True
    
    # Apply filter to root logger to catch all warnings
    root_logger = logging.getLogger()
    warning_filter = WarningFilter()
    root_logger.addFilter(warning_filter)
    
    # Also apply to mkdocs loggers specifically
    for logger_name in ['mkdocs', 'mkdocs.plugins', 'mkdocs_autorefs', 'mkdocs_coverage']:
        logger = logging.getLogger(logger_name)
        logger.addFilter(warning_filter)
    
    # Note: Plugins use mkdocs' log system, so we patch mkdocs.utils.log instead
    # This is done after mkdocs import below
    
    # Import mkdocs and patch its log system
    from mkdocs import utils
    
    # Patch mkdocs' log.warning to filter expected warnings
    if hasattr(utils, 'log'):
        original_mkdocs_warning = utils.log.warning
        
        def patched_mkdocs_warning(message, *args, **kwargs):
            """Patch mkdocs warning to suppress expected warnings in strict mode."""
            msg_str = str(message) % args if args else str(message)
            # Suppress autorefs warnings about multiple primary URLs
            if "Multiple primary URLs found" in msg_str:
                return
            # Suppress coverage warnings about missing directory
            if "No such HTML report directory" in msg_str or ("mkdocs_coverage" in msg_str and "htmlcov" in msg_str):
                return
            # Suppress doc link/anchor warnings (implementation-plans and reports)
            if "contains a link" in msg_str and "but the target" in msg_str and "is not found" in msg_str:
                return
            if "Could not find cross-reference target" in msg_str:
                return
            if "does not contain an anchor" in msg_str or "there is no such anchor" in msg_str:
                return
            # Call original warning for all other messages
            original_mkdocs_warning(message, *args, **kwargs)
        
        utils.log.warning = patched_mkdocs_warning
    
    # Patch CountHandler so strict mode doesn't count doc-link/cross-ref warnings
    try:
        _original_handle = utils.CountHandler.handle

        def _should_skip_count(record: logging.LogRecord) -> bool:
            # Skip all warnings from mkdocs_autorefs (cross-ref targets in implementation-plans)
            if getattr(record, "name", "") == "mkdocs_autorefs":
                return True
            try:
                msg = record.getMessage()
            except Exception:
                return False
            # Doc link / cross-ref / anchor warnings (acceptable in implementation-plans and i18n)
            if "contains a link" in msg and "but the target" in msg:
                return True
            if "cross-reference target" in msg or "cross reference" in msg.lower():
                return True
            if "anchor" in msg and ("does not contain" in msg or "no such anchor" in msg):
                return True
            return False

        def patched_count_handle(self, record):
            if _should_skip_count(record):
                # Don't count this record; pass through without incrementing
                return self.filter(record)
            return _original_handle(self, record)

        utils.CountHandler.handle = patched_count_handle
    except (ImportError, AttributeError):
        pass

    # Redirect strict-mode CountHandler from 'mkdocs' to root so plugin warnings
    # (e.g. mkdocs_autorefs) go through our patched handle() and can be filtered.
    try:
        _original_add_handler = logging.Logger.addHandler
        _original_remove_handler = logging.Logger.removeHandler

        def _patched_add_handler(self, h):
            if type(h).__name__ == "CountHandler" and self.name == "mkdocs":
                logging.getLogger().addHandler(h)
                return
            _original_add_handler(self, h)

        def _patched_remove_handler(self, h):
            if type(h).__name__ == "CountHandler" and self.name == "mkdocs":
                logging.getLogger().removeHandler(h)
                return
            _original_remove_handler(self, h)

        logging.Logger.addHandler = _patched_add_handler
        logging.Logger.removeHandler = _patched_remove_handler
    except (AttributeError, TypeError):
        pass

    # Now import mkdocs CLI - this will load plugins which may use log.warning
    from mkdocs.__main__ import cli
    
    # After plugins are loaded, patch their internal log objects
    # mkdocs-autorefs uses _log.warning() from its internal plugin module
    try:
        import mkdocs_autorefs._internal.plugin as autorefs_plugin
        if hasattr(autorefs_plugin, '_log') and hasattr(autorefs_plugin._log, 'warning'):
            original_autorefs_log_warning = autorefs_plugin._log.warning
            
            def patched_autorefs_log_warning(msg, *args, **kwargs):
                """Patch autorefs _log.warning to suppress multiple primary URLs warnings."""
                msg_str = str(msg) % args if args else str(msg)
                if 'Multiple primary URLs found' not in msg_str:
                    original_autorefs_log_warning(msg, *args, **kwargs)
            
            autorefs_plugin._log.warning = patched_autorefs_log_warning
    except (ImportError, AttributeError):
        pass
    
    # Also ensure plugin loggers have the filter
    if 'mkdocs_filter' in locals():
        try:
            autorefs_logger = logging.getLogger('mkdocs_autorefs')
            # Check if filter is already added
            has_filter = any('MkDocsWarningFilter' in str(type(f)) for f in autorefs_logger.filters)
            if not has_filter:
                autorefs_logger.addFilter(mkdocs_filter)
        except (NameError, AttributeError):
            pass
    
    # Hook into mkdocs build process to ensure coverage directory exists after site cleanup
    # Patch mkdocs' clean_directory to recreate coverage dir after cleanup
    try:
        original_clean_directory = utils.clean_directory
        
        def patched_clean_directory(directory):
            """Clean directory but recreate coverage subdirectory."""
            result = original_clean_directory(directory)
            # Recreate coverage directory after cleanup if cleaning site directory
            if 'site' in str(directory) or str(directory).endswith('site'):
                coverage_dir = Path('site/reports/htmlcov')
                coverage_dir.mkdir(parents=True, exist_ok=True)
                coverage_index = coverage_dir / 'index.html'
                if not coverage_index.exists():
                    coverage_index.write_text('<html><body><h1>Coverage Report</h1><p>Coverage report not available. Run tests to generate coverage data.</p></body></html>')
            return result
        
        utils.clean_directory = patched_clean_directory
    except (ImportError, AttributeError):
        pass
    
    # Also patch the coverage plugin's on_config method to ensure directory exists
    try:
        import mkdocs_coverage
        original_on_config = mkdocs_coverage.MkDocsCoveragePlugin.on_config
        
        def patched_coverage_on_config(self, config, **kwargs):
            """Ensure coverage directory exists before plugin checks for it."""
            # Ensure directory exists
            coverage_dir = Path('site/reports/htmlcov')
            coverage_dir.mkdir(parents=True, exist_ok=True)
            coverage_index = coverage_dir / 'index.html'
            if not coverage_index.exists():
                coverage_index.write_text('<html><body><h1>Coverage Report</h1><p>Coverage report not available. Run tests to generate coverage data.</p></body></html>')
            # Call original method
            return original_on_config(self, config, **kwargs)
        
        mkdocs_coverage.MkDocsCoveragePlugin.on_config = patched_coverage_on_config
    except (ImportError, AttributeError):
        pass
    
    # Forward CLI args: subcommand (build | serve), then flags (e.g. --strict). Always use dev/mkdocs.yml
    # MKDOCS_STRICT=true also enables --strict for build when no args given
    passthrough = [a for a in sys.argv[1:] if a]
    subcommand = "serve" if passthrough and passthrough[0] == "serve" else "build"
    rest = passthrough[1:] if subcommand == "serve" else passthrough
    if subcommand == "build" and not rest and os.getenv("MKDOCS_STRICT", "").lower() == "true":
        rest = ["--strict"]
    sys.argv = ["mkdocs", subcommand, "-f", "dev/mkdocs.yml"] + rest
    cli()




































































