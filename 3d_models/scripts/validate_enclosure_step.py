import FreeCAD as App
import Import

path = "/Users/bytedance/Documents/New project/ESP32_S3_LCD_sensor_enclosure_assembly.step"
doc = App.newDocument("STEP_Validation")
Import.insert(path, doc.Name)
doc.recompute()
shape_objects = [obj for obj in doc.Objects if hasattr(obj, "Shape") and not obj.Shape.isNull()]
if not shape_objects:
    raise RuntimeError("No shapes imported")
for obj in shape_objects:
    if not obj.Shape.isValid():
        raise RuntimeError("Invalid STEP shape: " + obj.Name)
print("STEP_REOPEN_OK", len(shape_objects), sum(len(obj.Shape.Solids) for obj in shape_objects))
App.closeDocument(doc.Name)
