import os
import FreeCAD as App
import Part
import Mesh
import MeshPart

ROOT = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
doc = App.openDocument(os.path.join(ROOT, "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd"))
button = doc.ButtonPlungerPositive.Shape
print("BUTTON_VALID_SOLIDS", button.isValid(), len(button.Solids),
      "CHECK", button.check(True), flush=True)
oldmesh = Mesh.Mesh(os.path.join(ROOT, "ESP32-S3-LCD-1.47B_紧凑双层外壳_按键顶杆_打印2件.stl"))
print("EXPORTED_MESH", oldmesh.CountFacets, oldmesh.isSolid(), flush=True)
for linear, angular in ((0.05, 0.3), (0.03, 0.2), (0.02, 0.15), (0.01, 0.1)):
    shape = button.Solids[0].copy()
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=linear,
                                  AngularDeflection=angular, Relative=False)
    print("REMESH", linear, angular, mesh.CountFacets, mesh.isSolid(),
          "VOLUME", mesh.Volume, flush=True)
    if mesh.isSolid():
        target = os.path.join(ROOT, "ESP32-S3-LCD-1.47B_紧凑双层外壳_按键顶杆_打印2件.stl")
        mesh.write(target)
        readback = Mesh.Mesh(target)
        assert readback.isSolid()
        print("BUTTON_STL_REPAIRED_AND_CLOSED", readback.CountFacets, flush=True)
        break
else:
    raise RuntimeError("All remeshing candidates are open")
App.closeDocument(doc.Name)
