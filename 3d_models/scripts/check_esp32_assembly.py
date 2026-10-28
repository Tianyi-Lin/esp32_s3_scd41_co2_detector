import FreeCAD as App

path = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/ESP32-S3-LCD-1.47B_外壳_装配预览.FCStd"
doc = App.openDocument(path)
board = doc.getObject("ESP32BoardAssembly")
bottom = doc.getObject("BottomCase")
sensor = doc.getObject("SensorKeepout")
dupont = doc.getObject("DupontWireKeepout")

for obj in (board, bottom, sensor, dupont):
    bb = obj.Shape.BoundBox
    print(
        obj.Name,
        round(bb.XMin, 2), round(bb.XMax, 2),
        round(bb.YMin, 2), round(bb.YMax, 2),
        round(bb.ZMin, 2), round(bb.ZMax, 2),
    )

print("ASSEMBLY_OK", board.Shape.isValid(), len(board.Shape.Solids))
