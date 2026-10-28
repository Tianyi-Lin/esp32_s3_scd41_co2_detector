import sys
import FreeCAD as App
sys.path.insert(0, "/Users/bytedance/Documents/New project")
from relieve_all_corner_columns import apply_all_corner_flats
doc = App.openDocument("/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd")
apply_all_corner_flats(doc)
print("DRY_RUN_COMPLETE_NO_FILES_CHANGED", flush=True)
App.closeDocument(doc.Name)
