import FreeCAD as App
import FreeCADGui as Gui

source = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/ESP32-S3-LCD-1.47B_外壳_装配预览.FCStd"
preview = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/ESP32-S3-LCD-1.47B_外壳_装配预览.png"

Gui.showMainWindow()
doc = App.openDocument(source)
Gui.activeDocument().activeView().viewAxonometric()

board = doc.getObject("ESP32BoardAssembly")
board.ViewObject.ShapeColor = (0.10, 0.55, 0.20)
board.ViewObject.LineColor = (0.05, 0.12, 0.05)
doc.getObject("BottomCase").ViewObject.ShapeColor = (0.30, 0.55, 0.92)
doc.getObject("PCBKeepout").ViewObject.Visibility = False
doc.getObject("SensorKeepout").ViewObject.Visibility = True
doc.getObject("SensorKeepout").ViewObject.ShapeColor = (1.0, 0.55, 0.10)
doc.getObject("SensorKeepout").ViewObject.Transparency = 45
doc.getObject("DupontWireKeepout").ViewObject.Visibility = True
doc.getObject("DupontWireKeepout").ViewObject.ShapeColor = (0.92, 0.12, 0.12)
doc.getObject("DupontWireKeepout").ViewObject.Transparency = 45
doc.getObject("TopLid").ViewObject.Visibility = True
doc.getObject("TopLid").ViewObject.Transparency = 82

doc.recompute()
doc.save()
Gui.activeDocument().activeView().fitAll()
Gui.activeDocument().activeView().saveImage(preview, 1600, 1200, "Current")
print("PREVIEW_CREATED", preview)
Gui.getMainWindow().close()
