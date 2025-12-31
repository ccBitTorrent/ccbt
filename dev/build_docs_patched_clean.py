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
import mkdocs_static_i18n
from mkdocs_static_i18n.plugin import I18n
import mkdocs_static_i18n.reconfigure

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
    if src_path is None:
        return False
    try:
        return original_is_relative_to(src_path, dest_path)
    except (TypeError, AttributeError):
        return False

def patched_reconfigure_files(self, files, mkdocs_config):
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
    from mkdocs.__main__ import cli
    
    # Use --strict only if explicitly requested via environment variable
    # Otherwise, respect strict: false in mkdocs.yml
    import os
    strict_flag = ['--strict'] if os.getenv('MKDOCS_STRICT', '').lower() == 'true' else []
    sys.argv = ['mkdocs', 'build'] + strict_flag + ['-f', 'dev/mkdocs.yml']
    cli()




































































