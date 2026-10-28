import FreeCAD as App
import Part

base = "/Users/bytedance/Documents/New project"
doc = App.openDocument(base + "/ESP32_S3_LCD_sensor_enclosure_LITE.FCStd")

bottom = doc.getObject("Enclosure_Bottom")
top = doc.getObject("Enclosure_Top")
board = doc.getObject("Board_Envelope")
sensor = doc.getObject("Sensor_Placeholder")
dupont = doc.getObject("Dupont_Clearance_Guide")

Part.export([bottom], base + "/ESP32_S3_LCD_enclosure_bottom.step")
Part.export([top], base + "/ESP32_S3_LCD_enclosure_top.step")
Part.export([bottom, top, board, sensor, dupont], base + "/ESP32_S3_LCD_sensor_enclosure_assembly.step")

print("STEP_EXPORT_OK")
App.closeDocument(doc.Name)
