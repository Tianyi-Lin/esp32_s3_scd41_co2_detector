import FreeCAD as App

path = "/Users/bytedance/Documents/New project/ESP32_S3_LCD_sensor_enclosure_LITE.FCStd"
doc = App.openDocument(path)
required = ["Board_Envelope", "Enclosure_Bottom", "Enclosure_Top", "Sensor_Placeholder", "Dupont_Clearance_Guide"]
for name in required:
    obj = doc.getObject(name)
    if obj is None or obj.Shape.isNull() or not obj.Shape.isValid():
        raise RuntimeError("Invalid or missing object: " + name)
print("REOPEN_OK", doc.Label, len(doc.Objects), ",".join(required))
App.closeDocument(doc.Name)
