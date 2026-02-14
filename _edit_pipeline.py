
import pathlib

f = pathlib.Path(r"c:/skzy/Antigravity/music/api/services/mv_pipeline.py")
content = f.read_text(encoding="utf-8")

old_import = """from .mv_store import (
    MVStore,
    MV_STATUS_STORYBOARD,
    MV_STATUS_IMAGES,
    MV_STATUS_VIDEO,
    MV_STATUS_STITCHING,
    MV_STATUS_SUCCESS,
    MV_STATUS_FAILURE,
    get_mv_store,
)"""

new_import = """from .mv_store import (
    MVStore,
    MV_STATUS_PENDING,
    MV_STATUS_STORYBOARD,
    MV_STATUS_IMAGES,
    MV_STATUS_VIDEO,
    MV_STATUS_STITCHING,
    MV_STATUS_SUCCESS,
    MV_STATUS_FAILURE,
    MV_STATUS_INTERRUPTED,
    get_mv_store,
)"""

if old_import not in content:
    print("ERROR: old import block not found")
else:
    content = content.replace(old_import, new_import, 1)
    print("SUCCESS: import block updated")

f.write_text(content.rstrip() + chr(10), encoding="utf-8")
print("File written (import only). Append step next.")
