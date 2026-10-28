"""Native sketch-driven files, with ordinary dimensions rather than spreadsheet drivers."""
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import FreeCAD as App
import Part
import Sketcher

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rebuild_editable_enclosure as base

STAGE = base.STAGE
OriginalModel = base.Model


class DirectModel(OriginalModel):
    def __init__(self, name, label):
        super().__init__(name, label.replace("参数化", "草图编辑"))
        self.handles = {}
        self.profiles = {}

    def dimension(self, sk, constraint, value):
        # Actual Sketcher dimensional constraints; no spreadsheet expressions.
        return sk.addConstraint(constraint)

    def named(self, sk, constraint, name):
        idx = sk.addConstraint(constraint)
        sk.renameConstraint(idx, name)
        self.handles[(sk.Name, name)] = idx
        return idx

    def suffix(self, sk):
        count = self.profiles.get(sk.Name, 0) + 1
        self.profiles[sk.Name] = count
        return "" if count == 1 else "_%d" % count

    def center(self, sk, x, y, suffix=""):
        idx = sk.addGeometry(Part.Point(App.Vector(x, y, 0)), True)
        self.named(sk, Sketcher.Constraint("DistanceX", idx, 1, x), "CenterX"+suffix)
        self.named(sk, Sketcher.Constraint("DistanceY", idx, 1, y), "CenterY"+suffix)
        return idx

    def rounded(self, sk, width, height, radius, cx=0, cy=0):
        w, h, r, x, y = [base.e(v).v for v in (width, height, radius, cx, cy)]
        points = [(x-w/2+r, y-h/2), (x+w/2-r, y-h/2),
                  (x+w/2, y-h/2+r), (x+w/2, y+h/2-r),
                  (x+w/2-r, y+h/2), (x-w/2+r, y+h/2),
                  (x-w/2, y+h/2-r), (x-w/2, y-h/2+r)]
        centers = {1: (x+w/2-r, y-h/2+r), 3: (x+w/2-r, y+h/2-r),
                   5: (x-w/2+r, y+h/2-r), 7: (x-w/2+r, y-h/2+r)}
        angles = {1: -45, 3: 45, 5: 135, 7: 225}
        g = []
        for i in range(8):
            a, b = points[i], points[(i+1) % 8]
            if i % 2 == 0:
                geom = Part.LineSegment(base.vec(a), base.vec(b))
            else:
                cc = centers[i]
                mid = (cc[0]+r*math.cos(math.radians(angles[i])),
                       cc[1]+r*math.sin(math.radians(angles[i])))
                geom = Part.Arc(base.vec(a), base.vec(mid), base.vec(b))
            g.append(sk.addGeometry(geom, False))
        for i in range(8):
            j = (i+1) % 8
            sk.addConstraint(Sketcher.Constraint("Tangent", g[i], 2, g[j], 1))
        for i in (0, 4):
            sk.addConstraint(Sketcher.Constraint("Horizontal", g[i]))
        for i in (2, 6):
            sk.addConstraint(Sketcher.Constraint("Vertical", g[i]))
        for i in (3, 5, 7):
            sk.addConstraint(Sketcher.Constraint("Equal", g[1], g[i]))
        suffix = self.suffix(sk)
        self.named(sk, Sketcher.Constraint("Radius", g[1], r), "CornerRadius"+suffix)
        center = self.center(sk, x, y, suffix)
        sk.addConstraint(Sketcher.Constraint("Symmetric", g[6], 1, g[2], 1, center, 1))
        self.named(sk, Sketcher.Constraint("DistanceX", g[6], 1, g[2], 1, w),
                   "Length"+suffix)
        self.named(sk, Sketcher.Constraint("DistanceY", g[0], 1, g[4], 1, h),
                   "Width"+suffix)

    def rect(self, sk, width, height, cx=0, cy=0):
        w, h, x, y = [base.e(v).v for v in (width, height, cx, cy)]
        points = [(x-w/2, y-h/2), (x+w/2, y-h/2),
                  (x+w/2, y+h/2), (x-w/2, y+h/2)]
        g = [sk.addGeometry(Part.LineSegment(base.vec(points[i]),
                                            base.vec(points[(i+1) % 4])), False)
             for i in range(4)]
        for i in range(4):
            sk.addConstraint(Sketcher.Constraint("Coincident", g[i], 2, g[(i+1)%4], 1))
            sk.addConstraint(Sketcher.Constraint("Horizontal" if i%2 == 0 else "Vertical",
                                                g[i]))
        suffix = self.suffix(sk)
        center = self.center(sk, x, y, suffix)
        sk.addConstraint(Sketcher.Constraint("Symmetric", g[0], 1, g[2], 1, center, 1))
        self.named(sk, Sketcher.Constraint("Distance", g[0], w), "Length"+suffix)
        self.named(sk, Sketcher.Constraint("Distance", g[1], h), "Width"+suffix)

    def capsule(self, sk, length, height, cx=0, cy=0):
        length, h, x, y = [base.e(v).v for v in (length, height, cx, cy)]
        r, a = h/2, (length-h)/2
        pts = [(x-a, y-r), (x+a, y-r), (x+a, y+r), (x-a, y+r)]
        geom = [Part.LineSegment(base.vec(pts[0]), base.vec(pts[1])),
                Part.Arc(base.vec(pts[1]), base.vec((x+a+r, y)), base.vec(pts[2])),
                Part.LineSegment(base.vec(pts[2]), base.vec(pts[3])),
                Part.Arc(base.vec(pts[3]), base.vec((x-a-r, y)), base.vec(pts[0]))]
        g = [sk.addGeometry(item, False) for item in geom]
        for i in range(4):
            sk.addConstraint(Sketcher.Constraint("Tangent", g[i], 2, g[(i+1)%4], 1))
        for i in (0, 2):
            sk.addConstraint(Sketcher.Constraint("Horizontal", g[i]))
        suffix = self.suffix(sk)
        self.named(sk, Sketcher.Constraint("Radius", g[1], r), "EndRadius"+suffix)
        center = self.center(sk, x, y, suffix)
        sk.addConstraint(Sketcher.Constraint("Symmetric", g[3], 3, g[1], 3, center, 1))
        self.named(sk, Sketcher.Constraint("DistanceX", g[3], 3, g[1], 3, length-h),
                   "StraightLength"+suffix)

    def circles(self, sk, centers, diameter):
        diameter = base.e(diameter).v
        first = None
        for i, center in enumerate(centers):
            x, y = [base.e(v).v for v in center]
            ix = sk.addGeometry(Part.Circle(App.Vector(x, y, 0), App.Vector(0,0,1),
                                            diameter/2), False)
            self.named(sk, Sketcher.Constraint("DistanceX", ix, 3, x), "Hole%d_X"%(i+1))
            self.named(sk, Sketcher.Constraint("DistanceY", ix, 3, y), "Hole%d_Y"%(i+1))
            if first is None:
                self.named(sk, Sketcher.Constraint("Diameter", ix, diameter), "Diameter")
                first = ix
            else:
                sk.addConstraint(Sketcher.Constraint("Equal", first, ix))


def detach(model):
    # Remove *all* remaining expressions, including pad depths and placement.
    # Their evaluated numerical values remain stored in the native properties.
    for obj in list(model.doc.Objects):
        if "ExpressionEngine" in obj.PropertiesList:
            for prop, expression in list(obj.ExpressionEngine):
                obj.setExpression(prop, None)
    model.doc.removeObject("Parameters")
    model.doc.ReadMe.Label = "使用方法：展开实体和特征，双击草图直接修改；特征深度也可直接改"
    model.doc.Label = model.doc.Label.replace("参数化", "草图编辑")
    model.body.Label = model.body.Label.replace("参数化", "草图编辑")
    model.doc.recompute()
    assert all(not o.ExpressionEngine for o in model.doc.Objects
               if "ExpressionEngine" in o.PropertiesList)
    assert not any(o.TypeId in ("Spreadsheet::Sheet", "PartDesign::Feature",
                               "PartDesign::FeaturePython", "App::FeaturePython")
                   for o in model.doc.Objects)


def test_dimension(model, sketch_name, constraint_name, delta):
    sk = model.doc.getObject(sketch_name)
    index = model.handles[(sketch_name, constraint_name)]
    old_value = sk.getDatum(index)
    old_shape = model.tip.Shape.copy()
    sk.setDatum(index, App.Units.Quantity(old_value.Value+delta, App.Units.Length))
    model.doc.recompute()
    assert all("Invalid" not in o.State for o in model.doc.Objects), [
        (o.Name, o.State) for o in model.doc.Objects if "Invalid" in o.State]
    assert model.tip.Shape.isValid() and len(model.tip.Shape.Solids) == 1
    changed = abs(model.tip.Shape.Volume-old_shape.Volume)
    if changed < 1e-6:
        changed = model.tip.Shape.cut(old_shape).Volume + old_shape.cut(model.tip.Shape).Volume
    assert changed > 1e-5
    sk.setDatum(index, old_value)
    model.doc.recompute()
    assert abs(model.tip.Shape.Volume-old_shape.Volume) < .003
    assert all(s.FullyConstrained for s in model.sketches)
    print("DIRECT_SKETCH_EDIT_PASS", model.doc.Name, sketch_name,
          constraint_name, delta, flush=True)
    return dict(sketch=sketch_name, dimension=constraint_name, change_mm=delta)


def main():
    print("DIRECT_STAGE", STAGE, flush=True)
    base.Model = DirectModel
    source_hash = hashlib.sha256(base.SOURCE.read_bytes()).hexdigest()
    src = App.openDocument(str(base.SOURCE))
    records = []
    selected = os.environ.get("DIRECT_PART", "all")
    specs = [
        ("bottom", base.bottom, "RemovableBottomCover", "下盖_草图编辑.FCStd",
         [("SensorHolesSketch", "Diameter", .1), ("SensorHolesSketch", "Hole1_X", .05),
          ("OuterProfile", "Length", .1)]),
        ("middle", base.middle, "RearShell", "中间外壳_草图编辑.FCStd",
         [("BossHolesSketch", "Diameter", .1), ("BossHolesSketch", "Hole1_X", .05),
          ("HeaderSketch", "Width", .1), ("VentSketchPositive", "StraightLength", .1)]),
        ("top", base.top, "FrontBezel", "上盖_草图编辑.FCStd",
         [("ThroughHolesSketch", "Diameter", .1), ("WindowSection1", "Width", .05),
          ("OuterProfile", "Length", .1)]),
    ]
    for key, builder, source_name, filename, tests in specs:
        if selected not in ("all", key):
            continue
        model = builder()
        detach(model)
        model.doc.saveAs(str(STAGE/("candidate_"+filename)))
        report = base.compare(model, src.getObject(source_name))
        report["direct_sketch_edit_tests"] = [test_dimension(model, *test) for test in tests]
        report["spreadsheet_drivers"] = 0
        report["expressions"] = 0
        for obj in model.doc.Objects:
            if hasattr(obj, "Visibility"):
                obj.Visibility = obj in (model.body, model.tip)
        model.doc.recompute()
        path = STAGE/filename
        model.doc.saveAs(str(path))
        name = model.doc.Name
        App.closeDocument(name)
        check = App.openDocument(str(path))
        check.recompute()
        assert check.Body.Tip.Shape.isValid()
        assert len(check.Body.Tip.Shape.Solids) == 1
        assert all("Invalid" not in o.State for o in check.Objects)
        assert all(o.FullyConstrained for o in check.Objects
                   if o.TypeId == "Sketcher::SketchObject")
        assert all(not o.ExpressionEngine for o in check.Objects
                   if "ExpressionEngine" in o.PropertiesList)
        App.closeDocument(check.Name)
        report["file"] = str(path)
        report["reopen_valid"] = True
        records.append(report)
        print("DIRECT_SAVED", path, flush=True)
    assert hashlib.sha256(base.SOURCE.read_bytes()).hexdigest() == source_hash
    App.closeDocument(src.Name)
    (STAGE/"direct_verification.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2))
    print("DIRECT_DONE", STAGE, flush=True)


if __name__ == "__main__":
    main()
