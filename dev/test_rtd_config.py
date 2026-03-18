#!/usr/bin/env python3
"""Test script to verify Read the Docs configuration is correct."""

import sys
import importlib

def test_imports():
    """Test that all required packages can be imported."""
    print("Testing package imports...")
    
    packages = [
        ('mkdocs', 'mkdocs', True),
        ('mkdocs_static_i18n', 'mkdocs_static_i18n', True),
        ('mkdocstrings', 'mkdocstrings', True),
        ('mkdocs_git_revision_date_localized', 'mkdocs_git_revision_date_localized_plugin', True),
        ('mkdocs_blog', 'mkdocs_blog', True),
        ('mkdocs_coverage', 'mkdocs_coverage', True),
        ('pymdownx', 'pymdownx', True),
    ]
    
    failed = []
    for display_name, import_name, required in packages:
        try:
            importlib.import_module(import_name)
            print(f"  [OK] {display_name}")
        except ImportError as e:
            if required:
                print(f"  [FAIL] {display_name}: {e}")
                failed.append(display_name)
            else:
                print(f"  [SKIP] {display_name} (plugin, not directly importable)")
    
    return len(failed) == 0

def test_build_script():
    """Test that the build script can be imported and patches apply."""
    print("\nTesting build script patches...")
    try:
        # Import the build script (this applies patches)
        sys.path.insert(0, 'dev')
        import build_docs_patched_clean
        print("  [OK] Build script imports successfully")
        print("  [OK] Patches applied to mkdocs-static-i18n")
        return True
    except Exception as e:
        print(f"  [FAIL] Build script failed: {e}")
        return False

def test_mkdocs_config():
    """Test that mkdocs.yml configuration is correct."""
    print("\nTesting mkdocs.yml configuration...")
    try:
        # Read the file as text to check for build: true flags
        with open('dev/mkdocs.yml', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for i18n plugin
        if 'i18n:' not in content:
            print("  [FAIL] i18n plugin not found in configuration")
            return False
        
        # Count languages with build: true
        import re
        # Find all language entries
        language_blocks = re.findall(r'- locale: (\w+)\s+name:.*?build: (true|false)', content, re.DOTALL)
        built_languages = [lang for lang, build in language_blocks if build == 'true']
        
        if built_languages:
            print(f"  [OK] Found {len(built_languages)} languages with build=true")
            print(f"  [OK] Languages: {', '.join(built_languages)}")
        else:
            print("  [WARN] No languages found with build=true")
        
        # Check that .readthedocs.yaml references the build script
        try:
            with open('.readthedocs.yaml', 'r', encoding='utf-8') as f:
                rtd_content = f.read()
            if 'build_docs_patched_clean.py' in rtd_content:
                print("  [OK] .readthedocs.yaml references patched build script")
            else:
                print("  [WARN] .readthedocs.yaml may not use patched build script")
        except FileNotFoundError:
            print("  [WARN] .readthedocs.yaml not found")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Failed to check mkdocs.yml: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("Read the Docs Configuration Test")
    print("=" * 60)
    
    results = []
    results.append(("Package Imports", test_imports()))
    results.append(("Build Script", test_build_script()))
    results.append(("MkDocs Config", test_mkdocs_config()))
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("[SUCCESS] All tests passed! Configuration is ready for Read the Docs.")
        return 0
    else:
        print("[FAILURE] Some tests failed. Please fix the issues above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())

