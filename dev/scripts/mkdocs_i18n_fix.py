"""Workaround for mkdocs-static-i18n plugin bug with None abs_src_path.

This script patches the mkdocs-static-i18n plugin to handle files with None abs_src_path.
Import this module before running mkdocs build.
"""


def apply_patch():
    """Apply monkey patch to mkdocs-static-i18n plugin."""
    try:
        # Import the modules
        import mkdocs_static_i18n
        from mkdocs_static_i18n.plugin import I18n
        
        # Get the original functions before patching
        original_is_relative_to = mkdocs_static_i18n.is_relative_to
        original_reconfigure_files = I18n.reconfigure_files

        def patched_is_relative_to(src_path, dest_path):
            """Patched version that handles None paths."""
            if src_path is None:
                return False
            try:
                return original_is_relative_to(src_path, dest_path)
            except (TypeError, AttributeError):
                # Fallback if original function also fails
                return False

        def patched_reconfigure_files(self, files, mkdocs_config):
            """Patched version that filters out files with None abs_src_path."""
            # Filter out files without abs_src_path before processing
            valid_files = [
                f for f in files
                if hasattr(f, 'abs_src_path') and f.abs_src_path is not None
            ]
            invalid_files = [
                f for f in files
                if not hasattr(f, 'abs_src_path') or f.abs_src_path is None
            ]

            # Process only valid files
            if valid_files:
                result = original_reconfigure_files(self, valid_files, mkdocs_config)
                # Add back invalid files (they won't be processed by i18n)
                if invalid_files:
                    result.extend(invalid_files)
                return result
            return files

        # Monkey patch the functions in all locations
        # Patch the module-level function in __init__.py
        mkdocs_static_i18n.is_relative_to = patched_is_relative_to
        # Patch the function in reconfigure.py (it imports from __init__)
        import mkdocs_static_i18n.reconfigure
        mkdocs_static_i18n.reconfigure.is_relative_to = patched_is_relative_to
        # Patch the reconfigure_files method on the I18n class
        I18n.reconfigure_files = patched_reconfigure_files
            
    except ImportError:
        # Plugin not installed, skip patching
        pass


# Auto-apply patch when imported
apply_patch()

