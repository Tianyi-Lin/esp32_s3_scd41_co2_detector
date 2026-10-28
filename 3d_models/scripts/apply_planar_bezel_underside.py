"""Back up and update only the front cover, including its print-folder copy."""
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile
import FreeCAD as App
import Part
import Mesh
import MeshPart

WORK = Path("/Users/bytedance/Documents/New project")
ROOT = Path("/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)")
sys.path.insert(0, str(WORK))
from flatten_bezel_underside import apply_planar_underside, update_parameters, export_planar_bezel
from flush_screen_bezel import display_faces
from raise_co2_layer import equal_volume, local_shape, pcb_substrate, co2_pcb_top_z

FILES = ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
         "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd",
         "ESP32-S3-LCD-1.47B_紧凑装配_五色半透明检查.FCStd")
STL = "ESP32-S3-LCD-1.47B_紧凑双层外壳_前盖.stl"
backup = Path(tempfile.mkdtemp(prefix="before-planar-bezel-", dir=WORK/".cad-recovery"))
stage = Path(tempfile.mkdtemp(prefix="planar-bezel-stage-", dir=WORK/".cad-recovery"))
targets = [ROOT/f for f in FILES + (STL,)] + [ROOT/"打印文件"/STL]
digests = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in targets}
for p in targets:
    rel = p.relative_to(ROOT)
    (backup/rel).parent.mkdir(exist_ok=True)
    shutil.copy2(p, backup/rel)
shutil.copy2(WORK/"create_compact_stacked_enclosure.py", backup)
print("BACKUP", backup, flush=True)
docs, styles, untouched_shapes = [], {}, []
info = None
for filename in FILES:
    with zipfile.ZipFile(ROOT/filename) as z:
        styles[filename] = {n: z.read(n) for n in z.namelist()
                            if n == "GuiDocument.xml" or
                            n.startswith(("LineColorArray", "PointColorArray", "ShapeAppearance"))}
    doc = App.openDocument(str(ROOT/filename))
    pose = App.Placement(doc.FrontBezel.Placement)
    untouched = {o.Name: (o.Shape, o.Placement.toMatrix().A) for o in doc.Objects
                 if "Shape" in o.PropertiesList and o.Name != "FrontBezel"}
    if info is None:
        info = apply_planar_underside(doc)
        finished = doc.FrontBezel.Shape.copy()
        finished_local = local_shape(doc.FrontBezel)
    else:
        doc.FrontBezel.Shape = finished.copy()
        doc.FrontBezel.Placement = pose
        update_parameters(doc, info)
        doc.recompute()
    assert doc.FrontBezel.Placement.toMatrix().A == pose.toMatrix().A
    equal_volume(local_shape(doc.FrontBezel), finished_local)
    s = doc.FrontBezel.Shape
    assert s.isValid() and len(s.Solids) == 1
    down = [f for f in s.Faces if isinstance(f.Surface, Part.Plane)
            and f.BoundBox.ZLength < 1e-7 and f.normalAt(0, 0).z < -.99]
    assert len(down) == 1
    for name, (shape, matrix) in untouched.items():
        obj = doc.getObject(name)
        assert obj.Shape.isSame(shape), name
        assert obj.Placement.toMatrix().A == matrix, name
    if filename != FILES[1]:
        assert abs(pcb_substrate(doc).BoundBox.ZMin-co2_pcb_top_z(doc)-20) < 1e-6
        gap = s.distToShape(display_faces(doc)[0])[0]
        assert abs(gap-info["removed_height"]) < 1e-6, gap
        for name in ("ESP32BoardAssembly", "RearShell", "ButtonPlungerPositive", "ButtonPlungerNegative"):
            assert s.common(doc.getObject(name).Shape).Volume < 1e-6, name
        print("COMPACT_FIT", filename, "glass_gap", gap, flush=True)
    docs.append(doc)
    untouched_shapes.append(untouched)
    doc.saveAs(str(stage/filename))
    print("PLANAR_UNDERSIDE", filename, len(down), down[0].CenterOfMass.z, flush=True)

check = export_planar_bezel(docs[0].FrontBezel, stage/STL)
assert abs(check.BoundBox.ZMin-info["underside_z"]) < 1e-5
print("STL_VALID", check.CountFacets, "orientation_errors", 0, "self_intersections", 0, flush=True)
for doc in docs:
    App.closeDocument(doc.Name)
for filename, untouched in zip(FILES, untouched_shapes):
    path = stage/filename
    with zipfile.ZipFile(path) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    entries.update(styles[filename])
    fd, tmp = tempfile.mkstemp(prefix="styled-", suffix=".FCStd", dir=stage)
    os.close(fd)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    os.replace(tmp, path)
    doc = App.openDocument(str(path))
    s = doc.FrontBezel.Shape
    assert s.isValid() and len(s.Solids) == 1
    equal_volume(local_shape(doc.FrontBezel), finished_local)
    assert doc.DesignParameters.ScreenWindowPlanarUndersideRevision == 1
    for name, (shape, matrix) in untouched.items():
        obj = doc.getObject(name)
        assert obj.Placement.toMatrix().A == matrix
        if shape.isNull():
            assert obj.Shape.isNull()
        else:
            assert abs(obj.Shape.Volume-shape.Volume) < 1e-6
    App.closeDocument(doc.Name)
    with zipfile.ZipFile(path) as z:
        assert all(z.read(n) == data for n, data in styles[filename].items())
    print("REOPEN_VERIFIED", filename, flush=True)
for path, digest in digests.items():
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, ("Concurrent change", path)
for path in targets:
    fd, tmp = tempfile.mkstemp(prefix=".planar-bezel-", dir=path.parent)
    os.close(fd)
    shutil.copy2(stage/path.name, tmp)
    os.replace(tmp, path)
    print("UPDATED", path, flush=True)
assert (ROOT/STL).read_bytes() == (ROOT/"打印文件"/STL).read_bytes()
print("COMPLETE", info, "BACKUP", backup, flush=True)
