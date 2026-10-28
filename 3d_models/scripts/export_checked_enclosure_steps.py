"""Read-only checks of current models, then export three native STEP solids."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import FreeCAD as App
import Mesh
import Part

ROOT = Path("/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)")
WORK = Path("/Users/bytedance/Documents/New project")
SOURCE = ROOT/"ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd"
DEST = ROOT/"打印文件"/"STEP"
PARTS = (
    ("上盖", "FrontBezel", "前盖"),
    ("下盖", "RemovableBottomCover", "可拆底盖"),
    ("中间件", "RearShell", "后壳"),
)
PREFIX = "ESP32-S3-LCD-1.47B_"
STL_PREFIX = PREFIX+"紧凑双层外壳_"
stage = Path(tempfile.mkdtemp(prefix="checked-step-export-", dir=WORK/".cad-recovery"))
inputs = [SOURCE] + [ROOT/"打印文件"/(STL_PREFIX+p[2]+".stl") for p in PARTS]
hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
doc = App.openDocument(str(SOURCE))
assert doc.DesignParameters.ScreenWindowPlanarUndersideRevision == 1
assert doc.DesignParameters.AllCornerColumnFlatCount == 8
exports = []
for label, obj_name, stl_suffix in PARTS:
    mesh = Mesh.Mesh(str(ROOT/"打印文件"/(STL_PREFIX+stl_suffix+".stl")))
    intersections = mesh.getSelfIntersections()
    mesh_result = dict(part=label, facets=mesh.CountFacets,
                       inverted=mesh.countNonUniformOrientedFacets(),
                       self_intersections=len(intersections),
                       closed=mesh.isSolid(), components=mesh.countComponents(),
                       nonmanifold=mesh.hasNonManifolds(),
                       corrupt=mesh.hasCorruptedFacets())
    print("STL_CHECK", json.dumps(mesh_result, ensure_ascii=False), flush=True)
    assert mesh_result["inverted"] == 0 and not intersections
    assert mesh_result["closed"] and mesh_result["components"] == 1
    assert not mesh_result["nonmanifold"] and not mesh_result["corrupt"]
    obj = doc.getObject(obj_name)
    shape = obj.Shape
    assert shape.isValid() and len(shape.Solids) == 1
    shape.check()
    filename = PREFIX+label+".step"
    assert not (DEST/filename).exists(), ("Existing export must be preserved", DEST/filename)
    path = stage/filename
    Part.export([obj], str(path))
    assert path.is_file() and path.stat().st_size > 1000
    reread = Part.Shape()
    reread.read(str(path))
    assert reread.isValid() and len(reread.Solids) == 1
    reread.check()
    volume_error = abs(reread.Volume-shape.Volume)
    assert volume_error < .01, ("STEP volume difference", label, volume_error)
    center_error = (reread.Solids[0].CenterOfMass-shape.Solids[0].CenterOfMass).Length
    assert center_error < 1e-5, ("STEP center difference", label, center_error)
    b1, b2 = shape.optimalBoundingBox(False, False), reread.optimalBoundingBox(False, False)
    bounds_error = max(abs(getattr(b1, a)-getattr(b2, a))
                       for a in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax"))
    assert bounds_error < 1e-5, ("STEP bounds difference", label, bounds_error)
    print("STEP_ROUNDTRIP", json.dumps(dict(
        part=label, file=filename, valid=True, solids=len(reread.Solids),
        faces_before=len(shape.Faces), faces_after=len(reread.Faces),
        volume_mm3=reread.Volume, volume_error_mm3=volume_error,
        bounds_error_mm=bounds_error, center_error_mm=center_error,
        bytes=path.stat().st_size), ensure_ascii=False), flush=True)
    exports.append(path)
App.closeDocument(doc.Name)
for path, digest in hashes.items():
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, ("Input changed", path)
DEST.mkdir(exist_ok=True)
for path in exports:
    target = DEST/path.name
    assert not target.exists()
    shutil.copy2(path, target)
    assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(target.read_bytes()).digest()
    print("EXPORTED", target, flush=True)
print("COMPLETE_ALL_THREE_CHECKED_AND_EXPORTED", flush=True)
