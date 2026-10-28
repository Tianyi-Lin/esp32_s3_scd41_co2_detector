"""Finish mesh export, restore inspection styles, and verify saved files."""
import os
import shutil
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
import FreeCAD as App
import Part
import Mesh

WORK = "/Users/bytedance/Documents/New project"
ROOT = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
BACKUP = os.path.join(WORK, ".cad-recovery/before-horizontal-feet-u0j78ist")
sys.path.insert(0, WORK)
from horizontal_supports import export_closed_button, TOL
from raise_co2_layer import pcb_substrate, floor_z
FILES = ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
         "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd",
         "ESP32-S3-LCD-1.47B_紧凑装配_五色半透明检查.FCStd")
for filename in FILES:
    path = os.path.join(ROOT, filename)
    with zipfile.ZipFile(os.path.join(BACKUP, filename)) as z:
        styles = {n: z.read(n) for n in z.namelist()
                  if n == "GuiDocument.xml"
                  or n.startswith(("LineColorArray", "PointColorArray", "ShapeAppearance"))}
    if styles:
        with zipfile.ZipFile(path) as z:
            entries = {n: z.read(n) for n in z.namelist()}
        entries.update(styles)
        fd, temp = tempfile.mkstemp(prefix=".cad-feet-style-", suffix=".FCStd", dir=ROOT)
        os.close(fd)
        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as z:
            for n, data in entries.items():
                z.writestr(n, data)
        os.replace(temp, path)
        print("STYLES_RESTORED", filename, len(styles), flush=True)
    doc = App.openDocument(path)
    for name in ("RearShell", "ButtonPlungerPositive", "ButtonPlungerNegative"):
        shape = doc.getObject(name).Shape
        assert shape.isValid() and len(shape.Solids) == 1
        shape.check(True)
    p = doc.DesignParameters
    assert p.HorizontalFootCount == 4
    assert abs(p.ButtonOuterProjection.Value - 0.5) < TOL
    shell = doc.RearShell.Shape
    supports = [f for f in shell.Faces if isinstance(f.Surface, Part.Plane)
                and f.BoundBox.YLength < TOL
                and abs(f.CenterOfMass.y - 18.45) < TOL]
    assert len(supports) == 4
    for name, side in (("ButtonPlungerPositive", 1), ("ButtonPlungerNegative", -1)):
        b = doc.getObject(name).Shape
        yy = b.BoundBox.YMax if side > 0 else -b.BoundBox.YMin
        assert abs(yy - 17.45) < TOL
        assert any(isinstance(f.Surface, Part.Sphere) and abs(f.Surface.Radius - 1.5) < TOL
                   for f in b.Faces)
    if filename != FILES[1]:
        assert abs(pcb_substrate(doc).BoundBox.ZMin - floor_z(doc) - 20) < TOL
    if filename == FILES[0]:
        export_closed_button(doc.ButtonPlungerPositive, os.path.join(
            ROOT, "ESP32-S3-LCD-1.47B_紧凑双层外壳_按键顶杆_打印2件.stl"))
        for suffix in ("后壳", "按键顶杆_打印2件"):
            mesh = Mesh.Mesh(os.path.join(ROOT, "ESP32-S3-LCD-1.47B_紧凑双层外壳_" + suffix + ".stl"))
            assert mesh.isSolid()
            print("PRINT_MESH_VERIFIED", suffix, mesh.CountFacets, flush=True)
    print("REOPEN_GEOMETRY_VERIFIED", filename, flush=True)
    App.closeDocument(doc.Name)
    for entry in os.listdir(ROOT):
        if entry.startswith(os.path.splitext(filename)[0] + ".") and entry.endswith(".FCBak"):
            target = os.path.join(BACKUP, entry)
            if not os.path.exists(target):
                shutil.move(os.path.join(ROOT, entry), target)
print("HORIZONTAL_SUPPORTS_COMPLETE", flush=True)
