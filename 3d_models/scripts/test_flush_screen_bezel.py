"""Exercise the new window without modifying any deliverable."""
import sys
import FreeCAD as App
sys.path.insert(0, "/Users/bytedance/Documents/New project")
from flush_screen_bezel import make_flush_bezel
path = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd"
doc = App.openDocument(path)
shape, info = make_flush_bezel(doc)
print("TEST_SUCCESS", "SOLIDS", len(shape.Solids), "VOLUME", shape.Volume,
      "FACES", len(shape.Faces), flush=True)
App.closeDocument(doc.Name)
