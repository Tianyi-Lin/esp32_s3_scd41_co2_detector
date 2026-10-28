"""Stage a 0.3 mm diagonal outward shift of the four shared enclosure mounts.

The column flats follow their master sketch without angle/depth changes. All
three native parts, print exports and the styled assembly are updated together.
Exterior size/R4, electronics, buttons, feet and sensor mounts stay unchanged.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile

import FreeCAD as App
import Part

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
SHIFT = .3
DELTA = SHIFT/math.sqrt(2)
CX, CY = 18.86+DELTA, 12.82+DELTA
CORNERS = [(x, y) for x in (-CX, CX) for y in (-CY, CY)]
OLD_CORNERS = [(x, y) for x in (-18.86, 18.86) for y in (-12.82, 12.82)]
SPECS = [("middle", "RearShell", "中间外壳_加深_草图编辑"),
         ("top", "FrontBezel", "上盖_2.5mm_草图编辑"),
         ("back", "RemovableBottomCover", "后盖_2.5mm_无围边_草图编辑")]
ASSEMBLY = "装配检查_盖板2.5mm_中间壳加深.FCStd"


def indices(sketch):
    return {c.Name: i for i, c in enumerate(sketch.Constraints) if c.Name}


def apply_corner_positions(doc, kind):
    name = {"middle": "ColumnSketch", "top": "ThroughHolesSketch", "back": "CoverHolesSketch"}[kind]
    sk = doc.getObject(name)
    ids = indices(sk)
    for i, (x, y) in enumerate(CORNERS, 1):
        for axis, value in [("X", x), ("Y", y)]:
            sk.setDatum(ids["Hole%d_%s" % (i, axis)], App.Units.Quantity("%.17g mm" % value))
    doc.recompute()


def check_corner_geometry(doc, kind):
    outer = doc.OuterProfile
    ids = indices(outer)
    assert all(abs(outer.getDatum(ids[n]).Value-v) < 1e-7
               for n, v in [("Length",45.4), ("Width",33.9), ("CornerRadius",4)])
    wire = outer.Shape.Wires[0]
    z = wire.BoundBox.ZMin
    rim = min(wire.distToShape(Part.makeCircle(2.55, App.Vector(x,y,z)))[0] for x,y in CORNERS)
    assert rim > 1.0
    record = dict(corner_centers_xy_mm=CORNERS, counterbore_outer_rim_mm=rim,
                  exterior_dimensions_xy_mm=[45.4,33.9], outer_corner_radius_mm=4)
    if kind == "middle":
        off = doc.UpperFlatsSketch.CutOffset.Value
        assert abs(off-2.7818530470919226) < 1e-8
        assert abs(doc.LowerFlatsSketch.CutOffset.Value-off) < 1e-8
        layers = [(doc.DeckSketch.Placement.Base.z, doc.Body.Tip.Shape.BoundBox.ZMin),
                  (doc.Body.Tip.Shape.BoundBox.ZMax, doc.DeckSketch.Placement.Base.z+doc.DeckPad.Length.Value)]
        found = 0
        for x, y in CORNERS:
            normal = App.Vector(-math.copysign(1,x),-math.copysign(1,y),0)
            normal.normalize()
            for za, zb in layers:
                z0,z1 = sorted([za,zb])
                faces = [f for f in doc.Body.Tip.Shape.Faces if isinstance(f.Surface,Part.Plane)
                    and abs(abs(f.normalAt(0,0).dot(normal))-1) < 1e-7
                    and abs((f.CenterOfMass-App.Vector(x,y,0)).dot(normal)-off) < 1e-6
                    and abs(f.BoundBox.ZMin-z0) < 1e-6 and abs(f.BoundBox.ZMax-z1) < 1e-6]
                assert len(faces) == 1, (x,y,z0,z1,len(faces))
                found += 1
        record.update(flat_count=found, flat_angle_degrees=45, flat_axis_offset_mm=off,
                      minimum_flat_to_bore_wall_mm=off-1.15,
                      minimum_flat_to_nominal_m25_wall_mm=off-1.25)
    return record


def stamp_corner_parameters(doc):
    p = doc.DesignParameters
    values = [("SideBodyColumnCenterX",CX),("SideBodyColumnCenterY",CY),
              ("CoverScrewCenterX",CX),("CoverScrewCenterY",CY),
              ("CoverScrewDiagonalShiftFromPrevious",SHIFT),
              ("CoverScrewRadialOutwardShift",math.hypot(CX-18.1,CY-12.2))]
    rim = 4-math.hypot(CX-18.7,CY-12.95)-2.55
    values += [("CoverHeadPocketOuterRim",rim), ("CoverScrewRadialOuterWallThickness",rim+2.55-1.15)]
    for name,value in values:
        if name not in p.PropertiesList:
            p.addProperty("App::PropertyLength",name,"Dimensions")
        setattr(p,name,value)
    p.Layout += " 四角外壳孔沿45度各向外平移0.3mm；柱体与上下两层45度切面同移；三件孔位同轴，外形45.4x33.9/R4保持。"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default = SCRIPTS.parent if (SCRIPTS.parent/"盖板2.5mm_中壳加深_20261028").is_dir() else (
        Path.home()/"Downloads/ESP32-S3-LCD-1.47B_20260204 (1)")
    parser.add_argument("--root", type=Path, default=default)
    root = parser.parse_args().root.resolve()
    current = root/"盖板2.5mm_中壳加深_20261028"
    (root/".cad-recovery").mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="corner-out03-",dir=root/".cad-recovery"))
    (stage/"打印文件").mkdir()
    print("STAGE",stage,flush=True)
    sources = [current/ASSEMBLY]+[current/(stem+".FCStd") for _,_,stem in SPECS]
    hashes = {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    import redesign_uniform_covers as geometry
    from fix_co2_connector_layout import restore_appearance
    geometry.CORNERS = CORNERS
    shapes, native_records, checks = {}, {}, {}
    for kind, name, stem in SPECS:
        doc = App.openDocument(str(current/(stem+".FCStd")))
        old = geometry.clean(doc.Body.Tip.Shape)
        apply_corner_positions(doc,kind)
        new = geometry.validate(doc)
        checks[name] = check_corner_geometry(doc,kind)
        # The only changed material must lie in small neighborhoods of the
        # old corner pillars/holes. Screens, sensor supports and side features
        # are not permitted to change.
        radius = 3.9 if kind == "middle" else 2.9
        region = Part.makeCompound([Part.makeCylinder(radius,old.BoundBox.ZLength+.2,
            App.Vector(x,y,old.BoundBox.ZMin-.1)) for x,y in OLD_CORNERS])
        assert new.cut(old).cut(region).Volume < 1e-5
        assert old.cut(new).cut(region).Volume < 1e-5
        assert max(abs(getattr(new.BoundBox,a)-getattr(old.BoundBox,a))
            for a in ["XMin","XMax","YMin","YMax","ZMin","ZMax"]) < 1e-5
        doc.ReadMe.Label += ("；四角孔、柱及上下层45度切面向外平移0.3mm，外形和R4不变"
            if kind == "middle" else "；四角孔及沉孔向外平移0.3mm，外形和R4不变")
        shapes[name],native_records[name] = geometry.export_native(doc,stage,stem)

    doc = App.openDocument(str(current/ASSEMBLY))
    before = {o.Name:(o.Shape.exportBrepToString(),tuple(o.Placement.toMatrix().A))
              for o in doc.Objects if "Shape" in o.PropertiesList and o.Name not in shapes}
    for name,shape in shapes.items():
        geometry.assign_shape(doc.getObject(name),shape)
    stamp_corner_parameters(doc)
    report = geometry.validate_assembly(doc)
    for name,(brep,pose) in before.items():
        obj = doc.getObject(name)
        assert obj.Shape.exportBrepToString() == brep and tuple(obj.Placement.toMatrix().A) == pose,name
    raw = stage/"headless.FCStd"
    doc.saveAs(str(raw))
    App.closeDocument(doc.Name)
    final = stage/ASSEMBLY
    restore_appearance(current/ASSEMBLY,raw,final,modified_names=set(shapes))
    check = App.openDocument(str(final))
    geometry.validate_assembly(check)
    for name,(_,pose) in before.items():
        assert tuple(check.getObject(name).Placement.toMatrix().A) == pose,name
    App.closeDocument(check.Name)
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == v for p,v in hashes.items())
    records = json.loads((current/"检查记录.json").read_text())
    records.update(native_records)
    records["assembly"] = dict(report,assembly_reopen="PASS")
    (stage/"检查记录.json").write_text(json.dumps(records,ensure_ascii=False,indent=2))
    record = dict(diagonal_outward_shift_mm=SHIFT, shift_per_axis_mm=DELTA,
        old_centers_xy_mm=OLD_CORNERS,new_centers_xy_mm=CORNERS,parts=checks,
        electronics_and_buttons_and_feet_unchanged=True,appearance_preserved=True,
        outside_corner_regions_unchanged=True,source_files_unchanged=True,
        assembly_reopen="PASS",assembly=report)
    (stage/"四角孔外移0.3mm检查.json").write_text(json.dumps(record,ensure_ascii=False,indent=2))
    print("DONE",stage,flush=True)


if __name__ == "__main__":
    main()
