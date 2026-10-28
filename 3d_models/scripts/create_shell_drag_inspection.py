import os
import FreeCAD as App


OUT_DIR = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
SOURCE_PATH = os.path.join(OUT_DIR, "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd")
OUTPUT_PATH = os.path.join(
    OUT_DIR, "ESP32-S3-LCD-1.47B_三件外壳对齐拖动检查.FCStd"
)

source = App.openDocument(SOURCE_PATH)
try:
    old = App.getDocument("ShellDragInspection")
except NameError:
    old = None
if old is not None:
    App.closeDocument(old.Name)
doc = App.newDocument("ShellDragInspection", "三件外壳对齐拖动检查")

parts_group = doc.addObject("App::DocumentObjectGroup", "AlignedShellParts")
parts_group.Label = "三件外壳（四孔同轴，可沿 Z 轴拖动）"


def copy_shell(source_name, target_name, label, color):
    source_obj = source.getObject(source_name)
    if source_obj is None:
        raise RuntimeError("Missing source object: " + source_name)
    obj = doc.addObject("PartDesign::Feature", target_name)
    obj.Label = label
    obj.Shape = source_obj.Shape.copy()
    obj.addProperty("App::PropertyString", "DragInstructions", "Inspection")
    obj.DragInstructions = (
        "右键选择‘变换’，只拖动蓝色 Z 轴；保持 X=0、Y=0，四个边缘孔即始终同轴。"
    )
    obj.addProperty("App::PropertyLength", "ExplodeOffsetZ", "Inspection")
    obj.ExplodeOffsetZ = 0.0
    parts_group.addObject(obj)
    if App.GuiUp:
        obj.ViewObject.ShapeColor = color
        obj.ViewObject.LineColor = (0.16, 0.20, 0.24)
    return obj


top_cover = copy_shell(
    "FrontBezel", "TopCover", "1 上盖（可沿蓝色 Z 轴上拉）", (0.78, 0.84, 0.88)
)
center_body = copy_shell(
    "RearShell", "CenterBody", "2 侧壁＋中层板（对齐基准，不动）", (0.68, 0.76, 0.81)
)
bottom_cover = copy_shell(
    "RemovableBottomCover",
    "BottomCover",
    "3 下盖（可沿蓝色 Z 轴下拉）",
    (0.72, 0.80, 0.85),
)

cover_screw_x = 18.1
cover_screw_y = 12.2

info = doc.addObject("App::FeaturePython", "DragInspectionInstructions")
info.Label = "拖动检查说明"
info.addProperty("App::PropertyString", "Alignment", "Instructions")
info.Alignment = (
    "上盖、侧壁中层、下盖的四个边缘孔中心均为 X=±18.1 mm、Y=±12.2 mm。"
)
info.addProperty("App::PropertyString", "HowToDrag", "Instructions")
info.HowToDrag = (
    "在左侧树选中上盖或下盖，右键‘变换’，拖蓝色 Z 轴。"
    "不要拖红色 X 或绿色 Y 轴，即可保持四孔同轴。"
)
info.addProperty("App::PropertyString", "Reset", "Instructions")
info.Reset = "装回时把所选零件 Placement 的 Position Z 恢复为 0 mm。"

doc.recompute()
if App.GuiUp:
    top_cover.ViewObject.Visibility = True
    center_body.ViewObject.Visibility = True
    bottom_cover.ViewObject.Visibility = True
    App.Gui.activeDocument().activeView().viewAxonometric()
    App.Gui.activeDocument().activeView().fitAll()
doc.saveAs(OUTPUT_PATH)
print("SHELL_DRAG_INSPECTION_CREATED", OUTPUT_PATH)
