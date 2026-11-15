"""Git LFS batch API logic (https://git-lfs.github.com/spec/v1).

Objects are identified by SHA-256 oid. When an object is available in
the CAS (xet_file_hash registered), batch responses advertise the
"xet" transfer so git-lfs hands the object to the git-xet custom
transfer agent; otherwise the built-in "basic" transfer with signed
hrefs to the object byte endpoints is used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ccbt.hub.repos import RepoStore

LFS_CONTENT_TYPE = "application/vnd.git-lfs+json"


def build_batch_response(
    store: RepoStore,
    repo_id: str,
    base_url: str,
    payload: dict,
) -> tuple[int, dict]:
    """Public function."""
    operation = payload.get("operation")
    if operation not in ("upload", "download"):
        return 422, {"message": "operation must be upload or download"}
    objects = payload.get("objects")
    if not isinstance(objects, list):
        return 422, {"message": "objects must be a list"}
    out_objects: list[dict] = []
    use_xet = False
    for obj in objects:
        oid = str(obj.get("oid", ""))
        size = int(obj.get("size", 0))
        info = store.get_object_info(oid)
        entry: dict = {"oid": oid, "size": size}
        if operation == "download":
            if info is None and store.get_object_bytes(oid) is None:
                entry["error"] = {"code": 404, "message": "object not found"}
            elif info is not None and info[1]:
                use_xet = True
                entry["actions"] = {
                    "download": {
                        "href": f"{base_url}/api/xet-transfer/{repo_id}/download/{oid}",
                        "expires_in": 3600,
                    }
                }
            else:
                entry["actions"] = {
                    "download": {
                        "href": f"{base_url}/lfs-objects/{oid}",
                        "expires_in": 3600,
                    }
                }
        elif info is not None and info[1]:
            pass  # already in CAS: no action needed
        elif store.get_object_bytes(oid) is not None:
            pass  # already stored: no action needed
        else:
            use_xet = True
            entry["actions"] = {
                "upload": {
                    "href": f"{base_url}/api/xet-transfer/{repo_id}/upload/{oid}",
                    "expires_in": 3600,
                }
            }
        out_objects.append(entry)
    return 200, {
        "transfer": "xet" if use_xet else "basic",
        "objects": out_objects,
    }


def verify_object_request(
    store: RepoStore, oid: str, size: Optional[int]
) -> Optional[str]:
    """Return an error message if an uploaded object fails verification."""
    data = store.get_object_bytes(oid)
    info = store.get_object_info(oid)
    if info is not None and info[1]:
        return None  # stored in CAS; bytes kept remotely
    if data is None:
        return "object bytes missing"
    if size is not None and len(data) != size:
        return "object size mismatch"
    return None
