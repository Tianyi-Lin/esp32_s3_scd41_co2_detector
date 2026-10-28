"""In-memory geometry and tessellation tests; never saves delivery files."""
import sys
import time
import FreeCAD as App
import MeshPart
sys.path.insert(0, "/Users/bytedance/Documents/New project")
from flatten_bezel_underside import flatten_shape

doc = App.openDocument("/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd")
shape, info = flatten_shape(doc.FrontBezel.Shape)
print("FLAT_SHAPE", info, "faces", len(shape.Faces), flush=True)
for label, candidate in (("OLD", doc.FrontBezel.Shape), ("NEW", shape)):
    try:
        print("CAD_CHECK", label, candidate.check(True), flush=True)
    except ValueError as exc:
        print("CAD_EXTENDED_CHECK", label, str(exc), flush=True)
for linear, angular in ((.005, .05), (.001, .03), (.0005, .02)):
    start = time.monotonic()
    mesh = MeshPart.meshFromShape(Shape=shape.copy(), LinearDeflection=linear,
                                 AngularDeflection=angular, Relative=False)
    pairs = mesh.getSelfIntersections()
    print("MESH", linear, angular, "facets", mesh.CountFacets,
          "solid", mesh.isSolid(), "components", mesh.countComponents(),
          "bad_orient", mesh.countNonUniformOrientedFacets(),
          "self_intersection_pairs", len(pairs),
          "elapsed", time.monotonic()-start, flush=True)
    if pairs:
        print("SAMPLE", pairs[:2], flush=True)
    if mesh.isSolid() and not pairs and mesh.countNonUniformOrientedFacets() == 0:
        break
App.closeDocument(doc.Name)
