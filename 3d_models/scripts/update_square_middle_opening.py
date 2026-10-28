"""Remove the four R2 middle-deck opening corners in existing CAD files.

Change the saved shell in place to preserve every other component and each
exploded-view placement. The main generator uses the same rectangular cut.
"""

import os

import FreeCAD as App
import Part


OUT_DIR = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
MODEL_NAMES = (
    "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
    "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd",
)
DECK_Z = 13.5


def central_arcs(shape):
    return [
        face for face in shape.Faces
        if isinstance(face.Surface, Part.Cylinder)
        and abs(face.Surface.Radius - 2.0) < 1e-6
        and abs(abs(face.Surface.Center.x) - 11.0) < 1e-6
        and abs(abs(face.Surface.Center.y) - 5.74) < 1e-6
        and abs(face.BoundBox.ZMin - DECK_Z) < 1e-6
    ]


for model_name in MODEL_NAMES:
    path = os.path.join(OUT_DIR, model_name)
    doc = App.openDocument(path)
    shell = doc.getObject("RearShell")
    params = doc.getObject("DesignParameters")
    unchanged_shapes = {
        obj.Name: (obj.Shape, obj.Placement.toMatrix().A)
        for obj in doc.Objects
        if "Shape" in obj.PropertiesList and obj.Name != "RearShell"
    }
    old_shape = shell.Shape.copy()
    length = params.CentralOpeningLength.Value
    width = params.CentralOpeningWidth.Value
    thickness = params.InterLayerDeckThickness.Value
    cut = Part.makeBox(
        length, width, thickness,
        App.Vector(-length / 2.0, -width / 2.0, DECK_Z),
    )
    new_shape = old_shape.cut(cut).removeSplitter()
    if not new_shape.isValid() or len(new_shape.Solids) != 1:
        raise RuntimeError("中层板去圆角后几何无效")
    if central_arcs(new_shape):
        raise RuntimeError("中层板中央孔仍有 R2 圆角")
    if new_shape.common(cut).Volume > 1e-7:
        raise RuntimeError("中央方形开孔内仍有残留材料")
    if new_shape.cut(old_shape).Volume > 1e-7:
        raise RuntimeError("去圆角操作意外增加了材料")
    shell.Shape = new_shape
    if "CentralOpeningCornerRadius" not in params.PropertiesList:
        params.addProperty("App::PropertyLength", "CentralOpeningCornerRadius", "Dimensions")
    params.CentralOpeningCornerRadius = 0.0
    doc.recompute()
    for name, (shape_before, placement_before) in unchanged_shapes.items():
        obj = doc.getObject(name)
        if not obj.Shape.isSame(shape_before) or obj.Placement.toMatrix().A != placement_before:
            raise RuntimeError("其他零件发生意外变化：" + name)
    doc.save()
    if model_name == MODEL_NAMES[0]:
        Part.export(
            [shell],
            os.path.join(OUT_DIR, "ESP32-S3-LCD-1.47B_紧凑双层外壳_后壳.stl"),
        )
    print("UPDATED", model_name)
    print("R2_ARCS_BEFORE_AFTER", len(central_arcs(old_shape)), len(central_arcs(new_shape)))
    print("REMOVED_VOLUME_MM3", old_shape.Volume - new_shape.Volume)
    print("HEADER_SLOT_LENGTH_MM", params.HeaderSlotLength.Value)
    print("UNCHANGED_OTHER_SHAPES", len(unchanged_shapes))
    App.closeDocument(doc.Name)
