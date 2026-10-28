"""Stage, validate, back up and publish only the revised side ventilation."""
import os
import shutil
import sys
import tempfile
import zipfile
import FreeCAD as App
import Mesh
import MeshPart

WORK = "/Users/bytedance/Documents/New project"
ROOT = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
sys.path.insert(0, WORK)
from space_side_vents import space_side_vents
from raise_co2_layer import equal_volume, pcb_substrate, co2_pcb_top_z

FILES = ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
         "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd",
         "ESP32-S3-LCD-1.47B_紧凑装配_五色半透明检查.FCStd")
STL = "ESP32-S3-LCD-1.47B_紧凑双层外壳_后壳.stl"
backup = tempfile.mkdtemp(prefix="before-vent-pitch26-", dir=WORK+"/.cad-recovery")
stage = tempfile.mkdtemp(prefix="vent-pitch26-stage-", dir=WORK+"/.cad-recovery")
for name in FILES+(STL,):
    shutil.copy2(os.path.join(ROOT, name), os.path.join(backup, name))
shutil.copy2(WORK+"/create_compact_stacked_enclosure.py", backup)
print("BACKUP", backup, flush=True)
docs, styles, untouched_all = [], {}, []
for filename in FILES:
    with zipfile.ZipFile(os.path.join(ROOT, filename)) as z:
        styles[filename] = {n: z.read(n) for n in z.namelist()
                            if n == "GuiDocument.xml"
                            or n.startswith(("LineColorArray", "PointColorArray", "ShapeAppearance"))}
    doc = App.openDocument(os.path.join(ROOT, filename))
    unchanged = {o.Name: (o.Shape, o.Placement.toMatrix().A)
                 for o in doc.Objects if "Shape" in o.PropertiesList and o.Name != "RearShell"}
    space_side_vents(doc)
    for name, (shape, pose) in unchanged.items():
        obj = doc.getObject(name)
        assert obj.Shape.isSame(shape) and obj.Placement.toMatrix().A == pose, name
    if filename != FILES[1]:
        assert abs(pcb_substrate(doc).BoundBox.ZMin-co2_pcb_top_z(doc)-20) < 1e-6
        for name in ("ESP32BoardAssembly", "HeaderPinsKeepout", "CO2SensorEnvelope",
                     "FrontBezel", "RemovableBottomCover", "ButtonPlungerPositive",
                     "ButtonPlungerNegative"):
            overlap = doc.RearShell.Shape.common(doc.getObject(name).Shape).Volume
            assert overlap < 1e-6, (name, overlap)
    assert abs(doc.DesignParameters.ButtonOuterProjection.Value-1) < 1e-6
    print("OTHER_PARTS_UNCHANGED", filename, len(unchanged), flush=True)
    docs.append(doc)
    untouched_all.append(unchanged)
for doc in docs[1:]:
    equal_volume(doc.RearShell.Shape, docs[0].RearShell.Shape)
finished = docs[0].RearShell.Shape.copy()
for filename, doc in zip(FILES, docs):
    doc.saveAs(os.path.join(stage, filename))
mesh = MeshPart.meshFromShape(Shape=finished, LinearDeflection=.01,
                             AngularDeflection=.1, Relative=False)
assert mesh.isSolid()
mesh.write(os.path.join(stage, STL))
assert Mesh.Mesh(os.path.join(stage, STL)).isSolid()
print("SHELL_STL_CLOSED", mesh.CountFacets, flush=True)
for doc in docs:
    App.closeDocument(doc.Name)
for filename, unchanged in zip(FILES, untouched_all):
    path = os.path.join(stage, filename)
    with zipfile.ZipFile(path) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    entries.update(styles[filename])
    fd, tmp = tempfile.mkstemp(prefix="styled-", suffix=".FCStd", dir=stage)
    os.close(fd)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    os.replace(tmp, path)
    doc = App.openDocument(path)
    s = doc.RearShell.Shape
    assert s.isValid() and len(s.Solids) == 1
    equal_volume(s, finished)
    for name, (shape, pose) in unchanged.items():
        obj = doc.getObject(name)
        assert obj.Placement.toMatrix().A == pose
        assert abs(obj.Shape.Volume-shape.Volume) < 1e-6
        for attr in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax"):
            assert abs(getattr(obj.Shape.BoundBox, attr)-getattr(shape.BoundBox, attr)) < 1e-6
    assert abs(doc.DesignParameters.ConvectionSlotPitch.Value-2.6) < 1e-6
    App.closeDocument(doc.Name)
    print("REOPEN_VERIFIED", filename, flush=True)
for filename in FILES+(STL,):
    fd, tmp = tempfile.mkstemp(prefix=".vent26-", dir=ROOT)
    os.close(fd)
    shutil.copy2(os.path.join(stage, filename), tmp)
    os.replace(tmp, os.path.join(ROOT, filename))
    print("UPDATED", filename, flush=True)
print("VENT_SPACING_COMPLETE", "BACKUP", backup, "STAGE", stage, flush=True)
