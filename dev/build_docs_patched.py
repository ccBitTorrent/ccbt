#!/usr/bin/env python3
"""Patched mkdocs build script with i18n plugin fixes and instrumentation."""

import json
import os
from pathlib import Path

# #region agent log
# Log path from system reminder
LOG_PATH = Path(r"c:\Users\MeMyself\bittorrentclient\.cursor\debug.log")

def log_debug(session_id: str, run_id: str, hypothesis_id: str, location: str, message: str, data: dict | None = None) -> None:
    """Write debug log entry in NDJSON format."""
    try:
        entry = {
            "sessionId": session_id,
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "timestamp": __import__("time").time() * 1000,
            "data": data or {}
        }
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # Silently fail if logging fails
# #endregion agent log

# Apply patch BEFORE importing mkdocs
import mkdocs_static_i18n
from mkdocs_static_i18n.plugin import I18n
import mkdocs_static_i18n.reconfigure

SESSION_ID = "debug-session"
RUN_ID = "run1"

# Store original functions
original_is_relative_to = mkdocs_static_i18n.is_relative_to
original_reconfigure_files = I18n.reconfigure_files

# Create patched functions
def patched_is_relative_to(src_path, dest_path):
    # #region agent log
    log_debug(SESSION_ID, RUN_ID, "A", "patched_is_relative_to:entry", "is_relative_to called", {
        "src_path": str(src_path) if src_path else None,
        "dest_path": str(dest_path) if dest_path else None,
        "src_is_none": src_path is None
    })
    # #endregion agent log
    
    if src_path is None:
        # #region agent log
        log_debug(SESSION_ID, RUN_ID, "A", "patched_is_relative_to:early_return", "Returning False (src_path is None)", {})
        # #endregion agent log
        return False
    try:
        result = original_is_relative_to(src_path, dest_path)
        # #region agent log
        log_debug(SESSION_ID, RUN_ID, "A", "patched_is_relative_to:success", "Original function succeeded", {"result": result})
        # #endregion agent log
        return result
    except (TypeError, AttributeError) as e:
        # #region agent log
        log_debug(SESSION_ID, RUN_ID, "A", "patched_is_relative_to:exception", "Caught exception, returning False", {
            "exception_type": type(e).__name__,
            "exception_msg": str(e)
        })
        # #endregion agent log
        return False

def patched_reconfigure_files(self, files, mkdocs_config):
    # #region agent log
    log_debug(SESSION_ID, RUN_ID, "B", "patched_reconfigure_files:entry", "reconfigure_files called", {
        "total_files": len(files) if hasattr(files, "__len__") else "unknown",
        "files_type": type(files).__name__
    })
    # #endregion agent log
    
    valid_files = [f for f in files if hasattr(f, 'abs_src_path') and f.abs_src_path is not None]
    invalid_files = [f for f in files if not hasattr(f, 'abs_src_path') or f.abs_src_path is None]
    
    # #region agent log
    log_debug(SESSION_ID, RUN_ID, "B", "patched_reconfigure_files:filtered", "Files filtered", {
        "valid_count": len(valid_files),
        "invalid_count": len(invalid_files),
        "invalid_has_alternates": [hasattr(f, 'alternates') for f in invalid_files[:5]] if invalid_files else []
    })
    # #endregion agent log
    
    if valid_files:
        result = original_reconfigure_files(self, valid_files, mkdocs_config)
        
        # #region agent log
        log_debug(SESSION_ID, RUN_ID, "C", "patched_reconfigure_files:after_original", "After original reconfigure_files", {
            "result_type": type(result).__name__,
            "result_has_alternates": [hasattr(f, 'alternates') for f in list(result)[:5]] if hasattr(result, "__iter__") else []
        })
        # #endregion agent log
        
        # Add invalid files back using append (I18nFiles is not a list)
        if invalid_files:
            for invalid_file in invalid_files:
                # #region agent log
                log_debug(SESSION_ID, RUN_ID, "D", "patched_reconfigure_files:adding_invalid", "Adding invalid file back", {
                    "has_alternates": hasattr(invalid_file, 'alternates'),
                    "file_type": type(invalid_file).__name__
                })
                # #endregion agent log
                
                # Ensure invalid files have alternates attribute to prevent sitemap template errors
                if not hasattr(invalid_file, 'alternates'):
                    invalid_file.alternates = {}
                    # #region agent log
                    log_debug(SESSION_ID, RUN_ID, "D", "patched_reconfigure_files:added_alternates", "Added empty alternates to invalid file", {})
                    # #endregion agent log
                
                result.append(invalid_file)
        
        # Ensure ALL files in result have alternates attribute (defensive check)
        for file_obj in result:
            if not hasattr(file_obj, 'alternates'):
                file_obj.alternates = {}
                # #region agent log
                log_debug(SESSION_ID, RUN_ID, "E", "patched_reconfigure_files:fixed_missing_alternates", "Fixed missing alternates on file", {
                    "file_src": getattr(file_obj, 'src_path', 'unknown')
                })
                # #endregion agent log
        
        # #region agent log
        log_debug(SESSION_ID, RUN_ID, "B", "patched_reconfigure_files:exit", "Returning result", {
            "final_count": len(result) if hasattr(result, "__len__") else "unknown",
            "all_have_alternates": all(hasattr(f, 'alternates') for f in list(result)[:10]) if hasattr(result, "__iter__") else "unknown"
        })
        # #endregion agent log
        
        return result
    
    # If no valid files, return original files object (shouldn't happen but safe fallback)
    # #region agent log
    log_debug(SESSION_ID, RUN_ID, "B", "patched_reconfigure_files:fallback", "No valid files, returning original", {})
    # #endregion agent log
    
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

# #region agent log
log_debug(SESSION_ID, RUN_ID, "F", "patch_applied", "All patches applied successfully", {})
# #endregion agent log

# Now import and run mkdocs in the same process
if __name__ == '__main__':
    import sys
    from mkdocs.__main__ import cli
    
    # #region agent log
    log_debug(SESSION_ID, RUN_ID, "F", "mkdocs_starting", "Starting mkdocs build", {
        "argv": sys.argv
    })
    # #endregion agent log
    
    sys.argv = ['mkdocs', 'build', '--strict', '-f', 'dev/mkdocs.yml']
    cli()
    
    # #region agent log
    log_debug(SESSION_ID, RUN_ID, "F", "mkdocs_complete", "Mkdocs build completed", {})
    # #endregion agent log

