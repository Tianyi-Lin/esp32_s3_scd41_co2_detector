import FreeCAD as App
import FreeCADGui as Gui


path = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd"

for existing in list(App.listDocuments().values()):
    if getattr(existing, "FileName", "") == path:
        App.closeDocument(existing.Name)

doc = App.openDocument(path)
App.setActiveDocument(doc.Name)

base = doc.getObject("RearShell")
bottom = doc.getObject("RemovableBottomCover")
lid = doc.getObject("FrontBezel")
base.ViewObject.ShapeColor = (0.72, 0.84, 0.90)
base.ViewObject.LineColor = (0.20, 0.32, 0.40)
base.ViewObject.Transparency = 55
bottom.ViewObject.ShapeColor = (0.66, 0.79, 0.86)
bottom.ViewObject.LineColor = (0.18, 0.29, 0.36)
bottom.ViewObject.Transparency = 45
lid.ViewObject.ShapeColor = (0.72, 0.84, 0.90)
lid.ViewObject.Transparency = 45
lid.ViewObject.Visibility = True

doc.getObject("ESP32BoardAssembly").ViewObject.ShapeColor = (0.14, 0.46, 0.22)
sensor_envelope = doc.getObject("CO2SensorEnvelope")
if sensor_envelope:
    sensor_envelope.ViewObject.Visibility = False
sensor_pcb = doc.getObject("CO2SensorPCB")
sensor_can = doc.getObject("CO2SensorCan")
sensor_connectors = doc.getObject("CO2SensorConnectors")
if sensor_pcb:
    sensor_pcb.ViewObject.ShapeColor = (0.05, 0.07, 0.06)
    sensor_pcb.ViewObject.LineColor = (0.35, 0.42, 0.38)
    sensor_pcb.ViewObject.Visibility = True
if sensor_can:
    sensor_can.ViewObject.ShapeColor = (0.72, 0.74, 0.72)
    sensor_can.ViewObject.LineColor = (0.28, 0.30, 0.28)
    sensor_can.ViewObject.Visibility = True
if sensor_connectors:
    sensor_connectors.ViewObject.ShapeColor = (0.92, 0.92, 0.88)
    sensor_connectors.ViewObject.LineColor = (0.45, 0.45, 0.42)
    sensor_connectors.ViewObject.Visibility = True
doc.getObject("HeaderPinsKeepout").ViewObject.ShapeColor = (0.96, 0.74, 0.12)
for name in ("ButtonPlungerPositive", "ButtonPlungerNegative"):
    button = doc.getObject(name)
    button.ViewObject.ShapeColor = (0.96, 0.62, 0.12)
    button.ViewObject.LineColor = (0.35, 0.20, 0.04)

doc.recompute()
Gui.activeDocument().activeView().viewAxonometric()
Gui.activeDocument().activeView().fitAll()
doc.save()
print("SCD41_BOTTOM_MOUNT_PREVIEW_READY")
