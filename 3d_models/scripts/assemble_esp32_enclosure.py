import os

import FreeCAD as App
import Part
import Import


OUT_DIR = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
ENCLOSURE_PATH = os.path.join(OUT_DIR, "ESP32-S3-LCD-1.47B_外壳.FCStd")
STEP_PATH = os.path.join(OUT_DIR, "ESP32-S3-LCD-1.47B.stp")
ASSEMBLY_PATH = os.path.join(OUT_DIR, "ESP32-S3-LCD-1.47B_外壳_装配预览.FCStd")
PREVIEW_PATH = os.path.join(OUT_DIR, "ESP32-S3-LCD-1.47B_外壳_装配预览.png")


def document_or_none(name):
    try:
        return App.getDocument(name)
    except NameError:
        return None


# Use the already imported STEP document when available. This preserves the
# precise shape while avoiding another expensive STEP import on macOS.
source = document_or_none("Unnamed")
source_object = None
if source:
    source_object = source.getObject("ESP32_S3_LCD_1_47B_ASM")

if source_object is None or not hasattr(source_object, "Shape") or source_object.Shape.isNull():
    source = App.newDocument("ESP32_STEP_Source")
    Import.insert(STEP_PATH, source.Name)
    source_object = source.getObject("ESP32_S3_LCD_1_47B_ASM")

if source_object is None or not hasattr(source_object, "Shape") or source_object.Shape.isNull():
    raise RuntimeError("无法从原始 STEP 文件读取 ESP32 总成。")

doc = document_or_none("ESP32_S3_LCD_Enclosure")
if doc is None:
    doc = App.openDocument(ENCLOSURE_PATH)

# Remove an older preview object when rerunning this script.
old_board = doc.getObject("ESP32BoardAssembly")
if old_board:
    doc.removeObject(old_board.Name)
old_group = doc.getObject("AssemblyComponents")
if old_group:
    doc.removeObject(old_group.Name)

board = doc.addObject("PartDesign::Feature", "ESP32BoardAssembly")
board.Label = "ESP32-S3-LCD-1.47B STEP 电路板总成"
board.Shape = source_object.Shape.copy()

# Align the actual STEP bounding box with the enclosure's PCB keep-out volume.
bb = board.Shape.BoundBox
target_center_x = -18.0
target_center_y = 0.0
target_min_z = 5.0
board.Placement.Base = App.Vector(
    target_center_x - (bb.XMin + bb.XMax) / 2.0,
    target_center_y - (bb.YMin + bb.YMax) / 2.0,
    target_min_z - bb.ZMin,
)
board.addProperty("App::PropertyString", "PlacementNote", "Assembly")
board.PlacementNote = "STEP bounding box aligned to the left PCB bay; bottom Z = 5 mm."
gui_available = "Gui" in globals() and Gui.up
if gui_available:
    board.ViewObject.ShapeColor = (0.12, 0.42, 0.18)
    board.ViewObject.LineColor = (0.08, 0.12, 0.08)

assembly_group = doc.addObject("App::DocumentObjectGroup", "AssemblyComponents")
assembly_group.Label = "装配件"
assembly_group.addObject(board)

# Show the real board and the reserved regions; make the lid a transparent
# assembled overlay so internal clearances remain visible.
if gui_available:
    doc.getObject("PCBKeepout").ViewObject.Visibility = False
    doc.getObject("BottomCase").ViewObject.Visibility = True
    doc.getObject("SensorKeepout").ViewObject.Visibility = True
    doc.getObject("DupontWireKeepout").ViewObject.Visibility = True
    lid = doc.getObject("TopLid")
    lid.ViewObject.Visibility = True
    lid.ViewObject.Transparency = 82

doc.recompute()
doc.saveAs(ASSEMBLY_PATH)
print("ASSEMBLY_CREATED", ASSEMBLY_PATH)

if gui_available:
    Gui.activeDocument().activeView().viewAxonometric()
    Gui.activeDocument().activeView().fitAll()
    Gui.activeDocument().activeView().setNavigationType("Gui::SolidWorksNavigationStyle")
    Gui.activeDocument().activeView().saveImage(PREVIEW_PATH, 1600, 1200, "Current")
    print("PREVIEW_CREATED", PREVIEW_PATH)
