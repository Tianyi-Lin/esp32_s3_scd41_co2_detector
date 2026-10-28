import FreeCAD as App
import Import
import Part


STEP_PATH = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/ESP32-S3-LCD-1.47B.stp"

doc = App.newDocument("InspectButtons")
Import.insert(STEP_PATH, doc.Name)
doc.recompute()

shape_objects = [
    obj for obj in doc.Objects
    if hasattr(obj, "Shape") and not obj.Shape.isNull()
]
assembly_object = doc.getObject("ESP32_S3_LCD_1_47B_ASM")
print("ASSEMBLY_OBJECT", assembly_object)
assembly_shape = assembly_object.Shape.copy() if assembly_object else Part.makeCompound(
    [
        obj.Shape.copy() for obj in shape_objects
        if obj.Shape.BoundBox.XLength < 1000
        and obj.Shape.BoundBox.YLength < 1000
        and obj.Shape.BoundBox.ZLength < 1000
    ]
)
assembly_shape.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 90.0)
assembly_bb = assembly_shape.BoundBox
translation = App.Vector(
    -(assembly_bb.XMin + assembly_bb.XMax) / 2.0,
    -(assembly_bb.YMin + assembly_bb.YMax) / 2.0,
    16.7 - assembly_bb.ZMin,
)
print("ASSEMBLY_ROTATED_BBOX", assembly_bb.XMin, assembly_bb.XMax,
      assembly_bb.YMin, assembly_bb.YMax, assembly_bb.ZMin, assembly_bb.ZMax)
print("TRANSLATION", translation.x, translation.y, translation.z)

for obj in shape_objects:
    label = (obj.Label or "").lower()
    name = (obj.Name or "").lower()
    if not hasattr(obj, "Shape") or obj.Shape.isNull():
        continue
    if any(token in label or token in name for token in ("switch", "boot", "rst", "button", "ts24")):
        transformed = obj.Shape.copy()
        transformed.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 90.0)
        transformed.translate(translation)
        bb = transformed.BoundBox
        print(
            "BUTTON_OBJECT",
            obj.Name,
            repr(obj.Label),
            "BBOX",
            bb.XMin,
            bb.XMax,
            bb.YMin,
            bb.YMax,
            bb.ZMin,
            bb.ZMax,
        )

print("OBJECT_COUNT", len(doc.Objects))
