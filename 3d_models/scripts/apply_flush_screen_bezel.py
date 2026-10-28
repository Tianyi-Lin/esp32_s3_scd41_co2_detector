"""Update only the front cover in the three current delivery documents."""
import os
import shutil
import sys
import tempfile
import zipfile
import FreeCAD as App
import Mesh
import Part
import MeshPart

WORK = "/Users/bytedance/Documents/New project"
ROOT = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
BACKUP = WORK + "/.cad-recovery/before-flush-screen-bezel-g6xs2Z"
sys.path.insert(0, WORK)
from flush_screen_bezel import apply_flush_bezel, update_bezel_parameters, display_faces
from raise_co2_layer import local_shape, equal_volume, pcb_substrate, co2_pcb_top_z

FILES = ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
         "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd",
         "ESP32-S3-LCD-1.47B_紧凑装配_五色半透明检查.FCStd")
STL = "ESP32-S3-LCD-1.47B_紧凑双层外壳_前盖.stl"
stage = tempfile.mkdtemp(prefix="flush-bezel-stage-", dir=WORK+"/.cad-recovery")
payloads = {}
for name in FILES:
    assert os.path.isfile(os.path.join(BACKUP, name))
    with zipfile.ZipFile(os.path.join(ROOT, name)) as z:
        payloads[name] = {n: z.read(n) for n in z.namelist()
                          if n == "GuiDocument.xml"
                          or n.startswith(("LineColorArray", "PointColorArray", "ShapeAppearance"))}
docs = []
info = None
for filename in FILES:
    doc = App.openDocument(os.path.join(ROOT, filename))
    untouched = {o.Name: (o.Shape, o.Placement.toMatrix().A)
                 for o in doc.Objects if "Shape" in o.PropertiesList and o.Name != "FrontBezel"}
    pose = App.Placement(doc.FrontBezel.Placement)
    if info is None:
        info = apply_flush_bezel(doc)
        finished_local = local_shape(doc.FrontBezel)
        finished_shape = doc.FrontBezel.Shape.copy()
    else:
        # Shape carries the main object's native location. Reassigning the
        # recipient's existing Placement then changes only its assembly offset.
        doc.FrontBezel.Shape = finished_shape.copy()
        doc.FrontBezel.Placement = pose
        update_bezel_parameters(doc, info)
        doc.recompute()
    assert doc.FrontBezel.Placement.toMatrix().A == pose.toMatrix().A
    for name, (shape, placement) in untouched.items():
        obj = doc.getObject(name)
        assert obj.Shape.isSame(shape), ("Unexpected other-part edit", name)
        assert obj.Placement.toMatrix().A == placement, name
    assert doc.FrontBezel.Shape.isValid() and len(doc.FrontBezel.Shape.Solids) == 1
    local_check = local_shape(doc.FrontBezel)
    equal_volume(local_check, finished_local)
    if filename != FILES[1]:
        glass, active = display_faces(doc)
        assert doc.FrontBezel.Shape.distToShape(glass)[0] < 1e-6
        assert abs(pcb_substrate(doc).BoundBox.ZMin - co2_pcb_top_z(doc) - 20) < 1e-6
        for part in ("ESP32BoardAssembly", "RearShell", "ButtonPlungerPositive", "ButtonPlungerNegative"):
            overlap = doc.FrontBezel.Shape.common(doc.getObject(part).Shape).Volume
            assert overlap < 1e-6, (part, overlap)
        downward = [f.CenterOfMass.z for f in doc.FrontBezel.Shape.Faces
                    if isinstance(f.Surface, Part.Plane) and f.BoundBox.ZLength < 1e-6
                    and f.normalAt(0,0).z < -.99]
        assert max(downward) <= doc.DesignParameters.RearShellDepth.Value + 1e-6
        print("VERIFIED", filename, "LIP_GAP", doc.FrontBezel.Shape.distToShape(glass)[0],
              "NO_UNDERSIDE_RECESS", downward, "PCB_SPACING", 20, flush=True)
    docs.append(doc)
for filename, doc in zip(FILES, docs):
    doc.saveAs(os.path.join(stage, filename))
Part.export([docs[0].FrontBezel], os.path.join(stage, STL))
mesh = Mesh.Mesh(os.path.join(stage, STL))
if not mesh.isSolid():
    mesh = MeshPart.meshFromShape(Shape=docs[0].FrontBezel.Shape.Solids[0].copy(),
                                  LinearDeflection=.03, AngularDeflection=.15, Relative=False)
    assert mesh.isSolid()
    mesh.write(os.path.join(stage, STL))
assert Mesh.Mesh(os.path.join(stage, STL)).isSolid()
print("FRONT_COVER_STL_CLOSED", mesh.CountFacets, flush=True)
volume = docs[0].FrontBezel.Shape.Volume
for doc in docs:
    App.closeDocument(doc.Name)
for filename in FILES:
    path = os.path.join(stage, filename)
    with zipfile.ZipFile(path) as z:
        contents = {n: z.read(n) for n in z.namelist()}
    contents.update(payloads[filename])
    fd, temp = tempfile.mkstemp(prefix="styled-", suffix=".FCStd", dir=stage)
    os.close(fd)
    with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in contents.items():
            z.writestr(name, data)
    os.replace(temp, path)
    with zipfile.ZipFile(path) as z:
        assert all(z.read(n) == data for n, data in payloads[filename].items())
    doc = App.openDocument(path)
    assert doc.FrontBezel.Shape.isValid() and len(doc.FrontBezel.Shape.Solids) == 1
    assert abs(doc.FrontBezel.Shape.Volume-volume) < 1e-6
    assert doc.DesignParameters.ScreenWindowFlushRevision == 1
    assert doc.DesignParameters.ScreenToLidGap.Value == 0
    if filename != FILES[1]:
        assert doc.FrontBezel.Shape.distToShape(display_faces(doc)[0])[0] < 1e-6
    App.closeDocument(doc.Name)
    print("REOPEN_AND_STYLE_VERIFIED", filename, flush=True)
for filename in FILES + (STL,):
    fd, temp = tempfile.mkstemp(prefix=".flush-bezel-", dir=ROOT)
    os.close(fd)
    shutil.copy2(os.path.join(stage, filename), temp)
    os.replace(temp, os.path.join(ROOT, filename))
    print("UPDATED", filename, flush=True)
print("FLUSH_BEZEL_COMPLETE", "BACKUP", BACKUP, "STAGE", stage, flush=True)
