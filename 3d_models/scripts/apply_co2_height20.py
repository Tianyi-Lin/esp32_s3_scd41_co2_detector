"""Back up, update, verify and save all three current enclosure documents."""
import hashlib
import os
import shutil
import sys
import tempfile
import zipfile

import FreeCAD as App
import Mesh
import Part

WORK = "/Users/bytedance/Documents/New project"
ROOT = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
sys.path.insert(0, WORK)
from raise_co2_layer import (UPPER_OBJECTS, TOL, equal_volume, floor_z,
                              local_shape, pcb_substrate, raise_lower_layer)

FILES = ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
         "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd",
         "ESP32-S3-LCD-1.47B_紧凑装配_五色半透明检查.FCStd")
STL = "ESP32-S3-LCD-1.47B_紧凑双层外壳_后壳.stl"
backup = tempfile.mkdtemp(prefix="before-co2-height20-", dir=os.path.join(WORK, ".cad-recovery"))
for name in FILES + (STL,):
    shutil.copy2(os.path.join(ROOT, name), backup)
shutil.copy2(os.path.join(WORK, "create_compact_stacked_enclosure.py"), backup)
print("BACKUP", backup, flush=True)

gui_payloads = {}
for filename in FILES:
    with zipfile.ZipFile(os.path.join(ROOT, filename)) as z:
        gui_payloads[filename] = {n: z.read(n) for n in z.namelist()
                                 if n == "GuiDocument.xml"
                                 or n.startswith(("LineColorArray", "PointColorArray", "ShapeAppearance"))}

docs = []
originals = {}
delta = None
for filename in FILES:
    doc = App.openDocument(os.path.join(ROOT, filename))
    originals[filename] = {o.Name: (o.Shape, App.Placement(o.Placement))
                           for o in doc.Objects if "Shape" in o.PropertiesList}
    delta = raise_lower_layer(doc, delta=delta)
    for name, (before, old_pose) in originals[filename].items():
        if name == "RearShell":
            continue
        obj = doc.getObject(name)
        expected_pose = App.Placement(old_pose)
        if name in UPPER_OBJECTS:
            before = before.copy()
            before.translate(App.Vector(0, 0, delta))
            expected_pose.Base.z += delta
        assert obj.Placement.toMatrix().A == expected_pose.toMatrix().A
        # Same topology with only the intended global translation.
        assert abs(obj.Shape.Volume - before.Volume) < TOL
        for attr in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax"):
            assert abs(getattr(obj.Shape.BoundBox, attr) - getattr(before.BoundBox, attr)) < TOL
        if name not in UPPER_OBJECTS:
            assert obj.Shape.isSame(before), ("Unmoved part changed", name)
    docs.append(doc)

main, exploded, colored = docs
for doc in (main, colored):
    measured = pcb_substrate(doc).BoundBox.ZMin - floor_z(doc)
    assert abs(measured - 20) < TOL, measured
    print("MEASURED_PCB_BACK_TO_INNER_FLOOR", doc.Label, measured, flush=True)
    assert abs(pcb_substrate(doc).BoundBox.ZMin - 22) < TOL
    assert abs(floor_z(doc) - 2) < TOL
    for name in ("ESP32BoardAssembly", "HeaderPinsKeepout", "CO2SensorEnvelope",
                 "FrontBezel", "RemovableBottomCover", "ButtonPlungerPositive",
                 "ButtonPlungerNegative"):
        overlap = doc.RearShell.Shape.common(doc.getObject(name).Shape).Volume
        print("SHELL_INTERFERENCE_MM3", doc.Label, name, overlap, flush=True)
        assert overlap < TOL, name
    for a, b in (("ESP32BoardAssembly", "CO2SensorEnvelope"),
                 ("ESP32BoardAssembly", "ButtonPlungerPositive"),
                 ("ESP32BoardAssembly", "ButtonPlungerNegative"),
                 ("CO2SensorEnvelope", "HeaderPinsKeepout"),
                 ("CO2SensorEnvelope", "RemovableBottomCover")):
        assert doc.getObject(a).Shape.common(doc.getObject(b).Shape).Volume < TOL, (a, b)

for doc in (exploded, colored):
    equal_volume(local_shape(main.RearShell), local_shape(doc.RearShell))
for name in UPPER_OBJECTS:
    a, b = main.getObject(name), colored.getObject(name)
    assert a.Placement.toMatrix().A == b.Placement.toMatrix().A

# Everything passed before saving any deliverable.
for doc in docs:
    doc.save()
    print("SAVED", doc.FileName, flush=True)
Part.export([main.RearShell], os.path.join(ROOT, STL))
mesh = Mesh.Mesh(os.path.join(ROOT, STL))
assert mesh.isSolid()
print("STL_CLOSED", mesh.CountFacets, flush=True)
shell_volume = main.RearShell.Shape.Volume
for doc in docs:
    App.closeDocument(doc.Name)

# Headless FreeCAD omits view providers. Keep the original independent-copy
# colors/transparency and every existing GUI material payload, not old BREP.
for filename, payloads in gui_payloads.items():
    if not payloads:
        continue
    path = os.path.join(ROOT, filename)
    with zipfile.ZipFile(path) as z:
        current = {n: z.read(n) for n in z.namelist()}
    current.update(payloads)
    fd, temp = tempfile.mkstemp(prefix=".cad-height-", suffix=".FCStd", dir=ROOT)
    os.close(fd)
    with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in current.items():
            z.writestr(name, data)
    os.replace(temp, path)
    with zipfile.ZipFile(path) as z:
        assert all(z.read(n) == data for n, data in payloads.items())
    print("GUI_STYLE_PRESERVED", filename, len(payloads), flush=True)

for filename in FILES:
    doc = App.openDocument(os.path.join(ROOT, filename))
    assert doc.RearShell.Shape.isValid() and len(doc.RearShell.Shape.Solids) == 1
    assert abs(doc.RearShell.Shape.Volume - shell_volume) < TOL
    if filename != FILES[1]:
        assert abs(pcb_substrate(doc).BoundBox.ZMin - floor_z(doc) - 20) < TOL
    assert abs(doc.DesignParameters.LowerLayerHeightIncrease.Value - delta) < TOL
    print("REOPEN_VERIFIED", filename, "GAP20", "HEIGHT_ADDED", delta, flush=True)
    App.closeDocument(doc.Name)
    # Move FreeCAD's automatic old-version snapshots into the recovery folder.
    for entry in os.listdir(ROOT):
        if entry.startswith(os.path.splitext(filename)[0] + ".") and entry.endswith(".FCBak"):
            shutil.move(os.path.join(ROOT, entry), os.path.join(backup, entry))
print("HEIGHT20_COMPLETE", flush=True)
