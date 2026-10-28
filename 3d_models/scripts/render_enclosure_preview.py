import FreeCAD as App
import FreeCADGui as Gui
import Mesh

base = "/Users/bytedance/Documents/New project"
doc = App.newDocument("EnclosurePreview")
obj = doc.addObject("Mesh::Feature", "Enclosure")
obj.Mesh = Mesh.Mesh(base + "/ESP32_S3_LCD_enclosure_preview.stl")
obj.ViewObject.ShapeColor = (0.25, 0.55, 0.90)
doc.recompute()
view = Gui.activeDocument().activeView()
view.viewAxonometric()
view.fitAll()
view.setAnimationEnabled(False)
view.saveImage(base + "/ESP32_S3_LCD_enclosure_preview.png", 1400, 1000, "White")
print("PREVIEW_RENDERED")
