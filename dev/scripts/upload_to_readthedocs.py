#!/usr/bin/env python3
"""Script to manually upload documentation to Read the Docs.

This script provides multiple methods for uploading documentation to Read the Docs:
1. Upload pre-built HTML ZIP file directly
2. Trigger a build via Read the Docs API
3. Create ZIP from existing site directory and upload
4. Build locally first, then create ZIP and upload

Usage:
    # Upload pre-built HTML ZIP
    python scripts/upload_to_readthedocs.py upload --zip site.zip --version latest

    # Trigger build via API
    python scripts/upload_to_readthedocs.py trigger --version latest

    # Create ZIP from existing site directory and upload
    python scripts/upload_to_readthedocs.py zip-and-upload --version latest

    # Build locally first, then upload
    python scripts/upload_to_readthedocs.py build-and-upload --version latest
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("Error: 'requests' library is required. Install it with: pip install requests")
    sys.exit(1)


# Default configuration
DEFAULT_PROJECT_SLUG = "ccbittorrent"
DEFAULT_RTD_URL = "https://readthedocs.org"
DEFAULT_BUILD_DIR = "site"
DEFAULT_VERSION = "latest"


def get_rtd_token() -> str | None:
    """Get Read the Docs API token from environment variable."""
    token = os.environ.get("RTD_API_TOKEN")
    if not token:
        print(
            "Warning: RTD_API_TOKEN environment variable not set.\n"
            "Get your token from: https://readthedocs.org/accounts/token/\n"
            "Then set it: export RTD_API_TOKEN='your-token-here'"
        )
    return token


def build_docs_locally(build_dir: str = DEFAULT_BUILD_DIR) -> Path:
    """Build documentation locally using MkDocs.

    Args:
        build_dir: Directory where built docs will be placed

    Returns:
        Path to the built documentation directory
    """
    print("Building documentation locally...")
    mkdocs_config = Path("dev/mkdocs.yml")
    if not mkdocs_config.exists():
        raise FileNotFoundError(f"MkDocs config not found: {mkdocs_config}")

    build_path = Path(build_dir)
    if build_path.exists():
        print(f"Cleaning existing build directory: {build_path}")
        shutil.rmtree(build_path)

    # Build using uv (preferred) or mkdocs directly
    try:
        result = subprocess.run(
            ["uv", "run", "mkdocs", "build", "--strict", "-f", str(mkdocs_config)],
            check=True,
            capture_output=True,
            text=True,
        )
        print("[OK] Documentation built successfully")
        if result.stdout:
            print(result.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback to mkdocs directly
        print("uv not found, trying mkdocs directly...")
        result = subprocess.run(
            ["mkdocs", "build", "--strict", "-f", str(mkdocs_config)],
            check=True,
            capture_output=True,
            text=True,
        )
        print("[OK] Documentation built successfully")
        if result.stdout:
            print(result.stdout)

    if not build_path.exists():
        raise RuntimeError(f"Build directory not created: {build_path}")

    return build_path


def create_html_zip(build_dir: Path, output_zip: str) -> Path:
    """Create a ZIP archive of the built documentation.

    Args:
        build_dir: Path to the built documentation directory
        output_zip: Name of the output ZIP file

    Returns:
        Path to the created ZIP file
    """
    zip_path = Path(output_zip)
    if zip_path.exists():
        print(f"Removing existing ZIP file: {zip_path}")
        zip_path.unlink()

    print(f"Creating ZIP archive: {zip_path}")
    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in build_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(build_dir)
                zipf.write(file_path, arcname)
                file_count += 1
    print(f"  Added {file_count} files to archive")

    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"[OK] ZIP archive created: {zip_path} ({size_mb:.2f} MB)")
    return zip_path


def upload_html_zip(
    zip_path: Path,
    project_slug: str,
    version: str,
    rtd_url: str = DEFAULT_RTD_URL,
) -> bool:
    """Upload HTML ZIP file to Read the Docs.

    Note: This requires using the Read the Docs web interface.
    The API doesn't support direct ZIP uploads, so this function
    provides instructions for manual upload.

    Args:
        zip_path: Path to the ZIP file
        project_slug: Read the Docs project slug
        version: Version to upload to (e.g., 'latest', 'stable', 'dev')
        rtd_url: Read the Docs base URL

    Returns:
        True if instructions were provided successfully
    """
    print("\n" + "=" * 70)
    print("MANUAL UPLOAD INSTRUCTIONS")
    print("=" * 70)
    print(f"\nRead the Docs doesn't support direct ZIP uploads via API.")
    print(f"Please use the web interface to upload your documentation:\n")
    print(f"1. Go to: {rtd_url}/projects/{project_slug}/versions/{version}/")
    print(f"2. Click on 'Upload HTML' or 'Import Documentation'")
    print(f"3. Upload the ZIP file: {zip_path.absolute()}")
    print(f"\nZIP file location: {zip_path.absolute()}")
    print(f"File size: {zip_path.stat().st_size / 1024 / 1024:.2f} MB")
    print("\n" + "=" * 70)
    return True


def trigger_build(
    project_slug: str,
    version: str,
    rtd_url: str = DEFAULT_RTD_URL,
    token: str | None = None,
) -> bool:
    """Trigger a build on Read the Docs via API.

    Args:
        project_slug: Read the Docs project slug
        version: Version to build (e.g., 'latest', 'stable', 'dev')
        rtd_url: Read the Docs base URL
        token: Read the Docs API token (if None, will try to get from env)

    Returns:
        True if build was triggered successfully
    """
    if not token:
        token = get_rtd_token()
        if not token:
            print("Error: RTD_API_TOKEN is required for API builds")
            return False

    api_url = f"{rtd_url}/api/v3/projects/{project_slug}/versions/{version}/builds/"
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
    }

    print(f"Triggering build for project '{project_slug}', version '{version}'...")
    print(f"API endpoint: {api_url}")

    try:
        response = requests.post(api_url, headers=headers, json={}, timeout=30)
        response.raise_for_status()

        build_data = response.json()
        build_id = build_data.get("id")
        build_url = build_data.get("urls", {}).get("build")

        print(f"[OK] Build triggered successfully!")
        print(f"  Build ID: {build_id}")
        if build_url:
            print(f"  Build URL: {build_url}")
        else:
            print(f"  View builds: {rtd_url}/projects/{project_slug}/builds/")

        return True
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] Error triggering build: HTTP {e.response.status_code}")
        if e.response.status_code == 401:
            print("  Authentication failed. Check your RTD_API_TOKEN.")
        elif e.response.status_code == 404:
            print(f"  Project or version not found. Check project slug '{project_slug}' and version '{version}'.")
        else:
            try:
                error_data = e.response.json()
                print(f"  Error details: {json.dumps(error_data, indent=2)}")
            except Exception:
                print(f"  Response: {e.response.text}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Error triggering build: {e}")
        return False


def get_build_status(
    project_slug: str,
    version: str,
    rtd_url: str = DEFAULT_RTD_URL,
    token: str | None = None,
) -> dict[str, Any] | None:
    """Get the status of the latest build for a version.

    Args:
        project_slug: Read the Docs project slug
        version: Version to check
        rtd_url: Read the Docs base URL
        token: Read the Docs API token

    Returns:
        Build status data or None if error
    """
    if not token:
        token = get_rtd_token()
        if not token:
            return None

    api_url = f"{rtd_url}/api/v3/projects/{project_slug}/versions/{version}/builds/"
    headers = {
        "Authorization": f"Token {token}",
    }

    try:
        response = requests.get(api_url, headers=headers, params={"limit": 1}, timeout=30)
        response.raise_for_status()
        data = response.json()
        builds = data.get("results", [])
        if builds:
            return builds[0]
        return None
    except Exception as e:
        print(f"Error getting build status: {e}")
        return None


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Upload documentation to Read the Docs manually",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Upload command
    upload_parser = subparsers.add_parser("upload", help="Upload pre-built HTML ZIP")
    upload_parser.add_argument(
        "--zip",
        type=str,
        required=True,
        help="Path to HTML ZIP file to upload",
    )
    upload_parser.add_argument(
        "--project",
        type=str,
        default=DEFAULT_PROJECT_SLUG,
        help=f"Read the Docs project slug (default: {DEFAULT_PROJECT_SLUG})",
    )
    upload_parser.add_argument(
        "--version",
        type=str,
        default=DEFAULT_VERSION,
        help=f"Version to upload to (default: {DEFAULT_VERSION})",
    )

    # Trigger command
    trigger_parser = subparsers.add_parser("trigger", help="Trigger build via API")
    trigger_parser.add_argument(
        "--project",
        type=str,
        default=DEFAULT_PROJECT_SLUG,
        help=f"Read the Docs project slug (default: {DEFAULT_PROJECT_SLUG})",
    )
    trigger_parser.add_argument(
        "--version",
        type=str,
        default=DEFAULT_VERSION,
        help=f"Version to build (default: {DEFAULT_VERSION})",
    )
    trigger_parser.add_argument(
        "--token",
        type=str,
        help="Read the Docs API token (or set RTD_API_TOKEN env var)",
    )

    # Build and upload command
    build_upload_parser = subparsers.add_parser(
        "build-and-upload",
        help="Build locally and provide upload instructions",
    )
    build_upload_parser.add_argument(
        "--project",
        type=str,
        default=DEFAULT_PROJECT_SLUG,
        help=f"Read the Docs project slug (default: {DEFAULT_PROJECT_SLUG})",
    )
    build_upload_parser.add_argument(
        "--version",
        type=str,
        default=DEFAULT_VERSION,
        help=f"Version to upload to (default: {DEFAULT_VERSION})",
    )
    build_upload_parser.add_argument(
        "--build-dir",
        type=str,
        default=DEFAULT_BUILD_DIR,
        help=f"Build directory (default: {DEFAULT_BUILD_DIR})",
    )
    build_upload_parser.add_argument(
        "--zip-name",
        type=str,
        help="Output ZIP file name (default: site-{version}.zip)",
    )

    # Zip and upload command (for existing site directory)
    zip_upload_parser = subparsers.add_parser(
        "zip-and-upload",
        help="Create ZIP from existing site directory and provide upload instructions",
    )
    zip_upload_parser.add_argument(
        "--site-dir",
        type=str,
        default=DEFAULT_BUILD_DIR,
        help=f"Path to existing site directory (default: {DEFAULT_BUILD_DIR})",
    )
    zip_upload_parser.add_argument(
        "--project",
        type=str,
        default=DEFAULT_PROJECT_SLUG,
        help=f"Read the Docs project slug (default: {DEFAULT_PROJECT_SLUG})",
    )
    zip_upload_parser.add_argument(
        "--version",
        type=str,
        default=DEFAULT_VERSION,
        help=f"Version to upload to (default: {DEFAULT_VERSION})",
    )
    zip_upload_parser.add_argument(
        "--zip-name",
        type=str,
        help="Output ZIP file name (default: site-{version}.zip)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "upload":
            zip_path = Path(args.zip)
            if not zip_path.exists():
                print(f"Error: ZIP file not found: {zip_path}")
                return 1
            upload_html_zip(zip_path, args.project, args.version)
            return 0

        elif args.command == "trigger":
            token = args.token or get_rtd_token()
            success = trigger_build(args.project, args.version, token=token)
            return 0 if success else 1

        elif args.command == "build-and-upload":
            # Build locally
            build_dir = build_docs_locally(args.build_dir)

            # Create ZIP
            zip_name = args.zip_name or f"site-{args.version}.zip"
            zip_path = create_html_zip(build_dir, zip_name)

            # Provide upload instructions
            upload_html_zip(zip_path, args.project, args.version)
            return 0

        elif args.command == "zip-and-upload":
            # Check if site directory exists
            site_dir = Path(args.site_dir)
            if not site_dir.exists():
                print(f"Error: Site directory not found: {site_dir}")
                return 1
            if not site_dir.is_dir():
                print(f"Error: Path is not a directory: {site_dir}")
                return 1

            # Create ZIP from existing directory
            zip_name = args.zip_name or f"site-{args.version}.zip"
            zip_path = create_html_zip(site_dir, zip_name)

            # Provide upload instructions
            upload_html_zip(zip_path, args.project, args.version)
            return 0

        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"\n[ERROR] Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())




















