"""Update the two button tips and preserve all other current geometry."""
import os
import shutil
import sys
import tempfile
import zipfile
import FreeCAD as App
import Mesh

WORK = "/Users/bytedance/Documents/New project"
ROOT = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
BACKUP = WORK + "/.cad-recovery/before-button-projection1-l9DnuE"
sys.path.insert(0, WORK)
from horizontal_supports import extend_hemispherical_buttons, export_closed_button
from raise_co2_layer import pcb_substrate, co2_pcb_top_z, equal_volume
from flush_screen_bezel import display_faces

FILES = ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
         "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd",
         "ESP32-S3-LCD-1.47B_紧凑装配_五色半透明检查.FCStd")
BUTTONS = ("ButtonPlungerPositive", "ButtonPlungerNegative")
STL = "ESP32-S3-LCD-1.47B_紧凑双层外壳_按键顶杆_打印2件.stl"
stage = tempfile.mkdtemp(prefix="button-projection1-stage-", dir=WORK+"/.cad-recovery")
styles = {}
docs = []
for filename in FILES:
    assert os.path.isfile(os.path.join(BACKUP, filename))
    with zipfile.ZipFile(os.path.join(ROOT, filename)) as z:
        styles[filename] = {n: z.read(n) for n in z.namelist()
                            if n == "GuiDocument.xml"
                            or n.startswith(("LineColorArray", "PointColorArray", "ShapeAppearance"))}
    doc = App.openDocument(os.path.join(ROOT, filename))
    untouched = {o.Name: (o.Shape, o.Placement.toMatrix().A)
                 for o in doc.Objects if "Shape" in o.PropertiesList and o.Name not in BUTTONS}
    extend_hemispherical_buttons(doc)
    for name, (shape, placement) in untouched.items():
        obj = doc.getObject(name)
        assert obj.Shape.isSame(shape) and obj.Placement.toMatrix().A == placement, name
    if filename != FILES[1]:
        assert abs(pcb_substrate(doc).BoundBox.ZMin - co2_pcb_top_z(doc) - 20) < 1e-6
        assert doc.FrontBezel.Shape.distToShape(display_faces(doc)[0])[0] < 1e-6
        gap = doc.DesignParameters.HorizontalSupportPlaneY.Value - doc.ButtonPlungerPositive.Shape.BoundBox.YMax
        assert abs(gap-.5) < 1e-6
        print("OTHER_GEOMETRY_UNCHANGED", filename, "TABLE_GAP", gap, flush=True)
    docs.append(doc)
for doc in docs[1:]:
    for name in BUTTONS:
        equal_volume(doc.getObject(name).Shape, docs[0].getObject(name).Shape)
for filename, doc in zip(FILES, docs):
    doc.saveAs(os.path.join(stage, filename))
export_closed_button(docs[0].ButtonPlungerPositive, os.path.join(stage, STL))
assert Mesh.Mesh(os.path.join(stage, STL)).isSolid()
volumes = {name: docs[0].getObject(name).Shape.Volume for name in BUTTONS}
for doc in docs:
    App.closeDocument(doc.Name)
for filename in FILES:
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
    with zipfile.ZipFile(path) as z:
        assert all(z.read(n) == data for n, data in styles[filename].items())
    doc = App.openDocument(path)
    for name, volume in volumes.items():
        shape = doc.getObject(name).Shape
        assert shape.isValid() and len(shape.Solids) == 1
        assert abs(shape.Volume-volume) < 1e-6
    assert abs(doc.DesignParameters.ButtonOuterProjection.Value-1.0) < 1e-6
    assert abs(doc.DesignParameters.HorizontalButtonGroundClearance.Value-.5) < 1e-6
    App.closeDocument(doc.Name)
    print("REOPEN_VERIFIED", filename, flush=True)
for filename in FILES + (STL,):
    fd, tmp = tempfile.mkstemp(prefix=".button1-", dir=ROOT)
    os.close(fd)
    shutil.copy2(os.path.join(stage, filename), tmp)
    os.replace(tmp, os.path.join(ROOT, filename))
    print("UPDATED", filename, flush=True)
print("BUTTON_PROJECTION1_COMPLETE", "BACKUP", BACKUP, flush=True)
