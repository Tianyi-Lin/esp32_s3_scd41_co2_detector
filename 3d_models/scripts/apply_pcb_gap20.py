"""Extend the lower layer by the measured PCB-to-PCB shortfall."""
import math
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
BACKUP = os.path.join(WORK, ".cad-recovery/before-pcb-to-pcb20-ewxcfis4")
sys.path.insert(0, WORK)
from raise_co2_layer import (UPPER_OBJECTS, TOL, equal_volume, floor_z,
                             local_shape, pcb_substrate, co2_pcb_top_z,
                             raise_lower_layer)

FILES = ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
         "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd",
         "ESP32-S3-LCD-1.47B_紧凑装配_五色半透明检查.FCStd")
STL = "ESP32-S3-LCD-1.47B_紧凑双层外壳_后壳.stl"
stage = tempfile.mkdtemp(prefix="pcb-to-pcb20-stage-", dir=os.path.join(WORK, ".cad-recovery"))
gui_payloads = {}
for filename in FILES:
    assert os.path.isfile(os.path.join(BACKUP, filename))
    with zipfile.ZipFile(os.path.join(ROOT, filename)) as z:
        gui_payloads[filename] = {n: z.read(n) for n in z.namelist()
                                 if n == "GuiDocument.xml"
                                 or n.startswith(("LineColorArray", "PointColorArray", "ShapeAppearance"))}


def verify_compact(doc):
    p = doc.DesignParameters
    back_z = pcb_substrate(doc).BoundBox.ZMin
    co2_z = co2_pcb_top_z(doc)
    assert abs(back_z - 24.2) < TOL
    assert abs(co2_z - 4.2) < TOL
    assert abs(back_z - co2_z - 20) < TOL
    assert abs(back_z - floor_z(doc) - 22.2) < TOL
    print("DATUM_VERIFIED", doc.Label, "ESP32_PCB_BACK", back_z,
          "CO2_PCB_TOP", co2_z, "PCB_TO_PCB", back_z - co2_z,
          "PCB_TO_FLOOR", back_z - floor_z(doc), flush=True)
    for name in ("ESP32BoardAssembly", "HeaderPinsKeepout", "CO2SensorEnvelope",
                 "FrontBezel", "RemovableBottomCover", "ButtonPlungerPositive",
                 "ButtonPlungerNegative"):
        overlap = doc.RearShell.Shape.common(doc.getObject(name).Shape).Volume
        print("SHELL_INTERFERENCE", name, overlap, flush=True)
        assert overlap < TOL, name
    for a, b in (("ESP32BoardAssembly", "CO2SensorEnvelope"),
                 ("ESP32BoardAssembly", "ButtonPlungerPositive"),
                 ("ESP32BoardAssembly", "ButtonPlungerNegative"),
                 ("CO2SensorEnvelope", "HeaderPinsKeepout"),
                 ("CO2SensorEnvelope", "RemovableBottomCover")):
        assert doc.getObject(a).Shape.common(doc.getObject(b).Shape).Volume < TOL, (a, b)
    wall = p.OuterWidth.Value / 2
    feet = [f for f in doc.RearShell.Shape.Faces
            if isinstance(f.Surface, Part.Plane) and f.BoundBox.YLength < TOL
            and abs(f.CenterOfMass.y - wall - 1.5) < TOL]
    assert len(feet) == 4
    assert all(abs(f.Area - math.pi * 1.65**2) < TOL for f in feet)
    actual = sorted((round(f.CenterOfMass.x, 6), round(f.CenterOfMass.z, 6)) for f in feet)
    expected = sorted((x, round(z, 6)) for x in (-15.0, 15.0)
                      for z in (5.5, p.HorizontalFootFrontCenterZ.Value))
    assert actual == expected, (actual, expected)
    for name in ("ButtonPlungerPositive", "ButtonPlungerNegative"):
        button = doc.getObject(name)
        assert button.Shape.isValid() and len(button.Shape.Solids) == 1
        sphere = [f for f in button.Shape.Faces if isinstance(f.Surface, Part.Sphere)]
        assert len(sphere) == 1 and abs(sphere[0].Surface.Radius - 1.5) < TOL
        tip = max(abs(button.Shape.BoundBox.YMin), abs(button.Shape.BoundBox.YMax))
        assert abs(tip - wall - 0.5) < TOL
    assert abs(p.HorizontalSupportPlaneY.Value -
               doc.ButtonPlungerPositive.Shape.BoundBox.YMax - 1.0) < TOL
    print("FEET_BUTTONS_PRESERVED", actual, "TABLE_CLEARANCE", 1.0, flush=True)


docs = []
delta = None
for filename in FILES:
    doc = App.openDocument(os.path.join(ROOT, filename))
    before = {o.Name: (o.Shape.copy(), App.Placement(o.Placement))
              for o in doc.Objects if "Shape" in o.PropertiesList}
    if delta is None:
        gap = pcb_substrate(doc).BoundBox.ZMin - co2_pcb_top_z(doc)
        assert abs(gap - 17.8) < TOL, ("Unexpected source version", gap)
        delta = 20.0 - gap
    raise_lower_layer(doc, delta=delta, reference="co2_pcb_top", allow_existing=True)
    for name, (shape, pose) in before.items():
        if name == "RearShell":
            continue
        obj = doc.getObject(name)
        if name in UPPER_OBJECTS:
            shape.translate(App.Vector(0, 0, delta))
            pose.Base.z += delta
        assert obj.Placement.toMatrix().A == pose.toMatrix().A
        assert abs(obj.Shape.Volume - shape.Volume) < TOL
        assert len(obj.Shape.Faces) == len(shape.Faces)
        for attr in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax"):
            assert abs(getattr(obj.Shape.BoundBox, attr) -
                       getattr(shape.BoundBox, attr)) < TOL, name
    docs.append(doc)

main, exploded, colored = docs
for doc in (main, colored):
    verify_compact(doc)
for doc in (exploded, colored):
    equal_volume(local_shape(main.RearShell), local_shape(doc.RearShell))
for name in UPPER_OBJECTS:
    assert main.getObject(name).Placement.toMatrix().A == colored.getObject(name).Placement.toMatrix().A
for name, offset in (("FrontBezel", 30.0), ("ESP32BoardAssembly", 15.0),
                     ("RemovableBottomCover", -32.0), ("CO2SensorPCB", -18.0),
                     ("CO2SensorCan", -18.0), ("CO2SensorConnectors", -18.0)):
    assert abs(exploded.getObject(name).Shape.BoundBox.ZMin -
               main.getObject(name).Shape.BoundBox.ZMin - offset) < TOL, name
print("EXPLODED_OFFSETS_UNCHANGED", flush=True)

# Validate staged deliverables before replacing any current file.
for filename, doc in zip(FILES, docs):
    doc.saveAs(os.path.join(stage, filename))
Part.export([main.RearShell], os.path.join(stage, STL))
mesh = Mesh.Mesh(os.path.join(stage, STL))
assert mesh.isSolid()
print("REAR_SHELL_STL_CLOSED", mesh.CountFacets, flush=True)
volume = main.RearShell.Shape.Volume
for doc in docs:
    App.closeDocument(doc.Name)

for filename, payloads in gui_payloads.items():
    path = os.path.join(stage, filename)
    with zipfile.ZipFile(path) as z:
        current = {n: z.read(n) for n in z.namelist()}
    current.update(payloads)
    fd, tmp = tempfile.mkstemp(prefix="styled-", suffix=".FCStd", dir=stage)
    os.close(fd)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in current.items():
            z.writestr(name, data)
    os.replace(tmp, path)
    with zipfile.ZipFile(path) as z:
        assert all(z.read(n) == data for n, data in payloads.items())
    print("GUI_STYLE_PRESERVED", filename, len(payloads), flush=True)
    doc = App.openDocument(path)
    assert doc.RearShell.Shape.isValid() and len(doc.RearShell.Shape.Solids) == 1
    assert abs(doc.RearShell.Shape.Volume - volume) < TOL
    p = doc.DesignParameters
    assert abs(p.PCBBackToCO2PCBTopDistance.Value - 20.0) < TOL
    assert abs(p.PCBBackToBottomInnerDistance.Value - 22.2) < TOL
    assert abs(p.LatestLowerLayerHeightIncrease.Value - 2.2) < TOL
    if filename != FILES[1]:
        assert abs(pcb_substrate(doc).BoundBox.ZMin - co2_pcb_top_z(doc) - 20.0) < TOL
    App.closeDocument(doc.Name)
    print("STAGED_REOPEN_VERIFIED", filename, flush=True)

for filename in FILES + (STL,):
    # Same-volume temporary file makes each individual replacement atomic.
    fd, tmp = tempfile.mkstemp(prefix=".pcb-gap20-", dir=ROOT)
    os.close(fd)
    shutil.copy2(os.path.join(stage, filename), tmp)
    os.replace(tmp, os.path.join(ROOT, filename))
    print("UPDATED", filename, flush=True)
print("PCB_GAP20_COMPLETE", "DELTA", delta, "BACKUP", BACKUP,
      "STAGED_COPY", stage, flush=True)
