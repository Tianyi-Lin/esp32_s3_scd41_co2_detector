"""Surgically update current deliverables; no full-model regeneration."""
import os
import shutil
import sys
import tempfile
import zipfile
import FreeCAD as App
import Part
import Mesh

WORK = "/Users/bytedance/Documents/New project"
ROOT = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
sys.path.insert(0, WORK)
from horizontal_supports import add_horizontal_supports, local_shape, TOL, export_closed_button
from raise_co2_layer import pcb_substrate, floor_z

FILES = ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
         "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd",
         "ESP32-S3-LCD-1.47B_紧凑装配_五色半透明检查.FCStd")
STLS = ("ESP32-S3-LCD-1.47B_紧凑双层外壳_后壳.stl",
        "ESP32-S3-LCD-1.47B_紧凑双层外壳_按键顶杆_打印2件.stl")
backup = tempfile.mkdtemp(prefix="before-horizontal-feet-", dir=os.path.join(WORK, ".cad-recovery"))
for name in FILES + STLS:
    shutil.copy2(os.path.join(ROOT, name), backup)
shutil.copy2(os.path.join(WORK, "create_compact_stacked_enclosure.py"), backup)
print("BACKUP", backup, flush=True)
payloads = {}
for name in FILES:
    with zipfile.ZipFile(os.path.join(ROOT, name)) as z:
        payloads[name] = {n: z.read(n) for n in z.namelist()
                          if n == "GuiDocument.xml"
                          or n.startswith(("LineColorArray", "PointColorArray", "ShapeAppearance"))}

docs = []
for filename in FILES:
    doc = App.openDocument(os.path.join(ROOT, filename))
    untouched = {o.Name: (o.Shape, o.Placement.toMatrix().A) for o in doc.Objects
                 if "Shape" in o.PropertiesList
                 and o.Name not in ("RearShell", "ButtonPlungerPositive", "ButtonPlungerNegative")}
    add_horizontal_supports(doc)
    for name, (shape, matrix) in untouched.items():
        o = doc.getObject(name)
        assert o.Shape.isSame(shape) and o.Placement.toMatrix().A == matrix, name
    docs.append(doc)

main, exploded, colored = docs
for doc in docs[1:]:
    for name in ("RearShell", "ButtonPlungerPositive", "ButtonPlungerNegative"):
        a, b = local_shape(main.getObject(name)), local_shape(doc.getObject(name))
        assert a.cut(b).Volume < TOL and b.cut(a).Volume < TOL

# Detailed assembly checks on the compact master; the independent inspection
# copy has the same geometry and exact compact placements.
for name in ("ESP32BoardAssembly", "HeaderPinsKeepout", "CO2SensorEnvelope", "FrontBezel",
             "RemovableBottomCover", "ButtonPlungerPositive", "ButtonPlungerNegative"):
    a, b = main.getObject(name), colored.getObject(name)
    assert a.Placement.toMatrix().A == b.Placement.toMatrix().A
    overlap = main.RearShell.Shape.common(a.Shape).Volume
    print("SHELL_INTERFERENCE", name, overlap, flush=True)
    assert overlap < TOL, name
for side, name in ((1, "ButtonPlungerPositive"), (-1, "ButtonPlungerNegative")):
    obj = main.getObject(name)
    assert obj.Shape.common(main.ESP32BoardAssembly.Shape).Volume < TOL
    for travel in (0.3, 0.5, 0.8):
        moved = obj.Shape.copy()
        moved.translate(App.Vector(0, -side * travel, 0))
        assert moved.common(main.RearShell.Shape).Volume < TOL, (name, travel)
    print("BUTTON_GUIDE_CLEAR_AT_TRAVEL", name, "0 0.3 0.5 0.8", flush=True)

p = main.DesignParameters
assert abs(pcb_substrate(main).BoundBox.ZMin - floor_z(main) - 20) < TOL
assert abs(p.USBCutWidth.Value - 12) < TOL and abs(p.USBCutHeight.Value - 6.2) < TOL
# A half-space representing a flat table: only the four feet can touch it.
table_y = p.HorizontalSupportPlaneY.Value
for obj in main.Objects:
    if "Shape" in obj.PropertiesList and not obj.Shape.isNull():
        assert obj.Shape.BoundBox.YMax <= table_y + TOL, obj.Name
assert abs(table_y - main.ButtonPlungerPositive.Shape.BoundBox.YMax - 1.0) < TOL
print("GAP20_PRESERVED_AND_BUTTON_GROUND_GAP_1MM", flush=True)

for doc in docs:
    doc.save()
    print("SAVED", doc.FileName, flush=True)
Part.export([main.RearShell], os.path.join(ROOT, STLS[0]))
export_closed_button(main.ButtonPlungerPositive, os.path.join(ROOT, STLS[1]))
for name in STLS:
    mesh = Mesh.Mesh(os.path.join(ROOT, name))
    assert mesh.isSolid()
    print("STL_CLOSED", name, mesh.CountFacets, flush=True)
volumes = {name: main.getObject(name).Shape.Volume
           for name in ("RearShell", "ButtonPlungerPositive", "ButtonPlungerNegative")}
for doc in docs:
    App.closeDocument(doc.Name)

for filename, style in payloads.items():
    if style:
        path = os.path.join(ROOT, filename)
        with zipfile.ZipFile(path) as z:
            current = {n: z.read(n) for n in z.namelist()}
        current.update(style)
        fd, temp = tempfile.mkstemp(prefix=".cad-feet-", suffix=".FCStd", dir=ROOT)
        os.close(fd)
        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as z:
            for n, data in current.items():
                z.writestr(n, data)
        os.replace(temp, path)
        print("COLORS_PRESERVED", filename, len(style), flush=True)

for filename in FILES:
    doc = App.openDocument(os.path.join(ROOT, filename))
    for name, volume in volumes.items():
        shape = doc.getObject(name).Shape
        assert shape.isValid() and len(shape.Solids) == 1
        assert abs(shape.Volume - volume) < TOL
    assert doc.DesignParameters.HorizontalFootCount == 4
    assert abs(doc.DesignParameters.ButtonOuterProjection.Value - 0.5) < TOL
    if filename != FILES[1]:
        assert abs(pcb_substrate(doc).BoundBox.ZMin - floor_z(doc) - 20) < TOL
    App.closeDocument(doc.Name)
    for entry in os.listdir(ROOT):
        if entry.startswith(os.path.splitext(filename)[0] + ".") and entry.endswith(".FCBak"):
            shutil.move(os.path.join(ROOT, entry), os.path.join(backup, entry))
print("HORIZONTAL_SUPPORTS_COMPLETE", flush=True)
