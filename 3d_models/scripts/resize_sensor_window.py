"""Fit the rear sensor window to the package at the cover, plus 0.3 mm/side.

The old 10.7 mm window incorrectly used the remote 10.1 mm PCB-side flange.
These dimensions reference the actual SCD41 STEP section at the inner cover
plane Z=2.5 mm. A rounded-rectangle sketch approximates its slightly elliptical
corners within 0.002 mm, retaining editable length/width/radius constraints.
Run in FreeCAD Python; outputs are staged without saving the source files.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

import FreeCAD as App
import Part

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0,str(SCRIPTS))
SIDE_GAP = .3
SECTION_Z = 2.5
# Measured from the assembly's real STEP package (not its 10.1 mm flange).
BODY_LENGTH = 7.822030878362911
BODY_WIDTH = 7.822030878362914
WINDOW_LENGTH = BODY_LENGTH+2*SIDE_GAP
WINDOW_WIDTH = BODY_WIDTH+2*SIDE_GAP
WINDOW_RADIUS = 1.704
CENTER_X = .000112610896522
CENTER_Y = -.000106993595547
ASSEMBLY = "装配检查_盖板2.5mm_中间壳加深.FCStd"
BACK = "后盖_2.5mm_无围边_草图编辑"


def apply_window(doc):
    sk = doc.SensorWindowSketch
    ids = {c.Name:i for i,c in enumerate(sk.Constraints) if c.Name}
    for name,value in [("Length",WINDOW_LENGTH),("Width",WINDOW_WIDTH),
        ("CornerRadius",WINDOW_RADIUS),("CenterX",CENTER_X),("CenterY",CENTER_Y)]:
        sk.setDatum(ids[name],App.Units.Quantity("%.17g mm" % value))
    sk.Label = "SCD41 实际穿板外形每边+0.3mm（约8.422×8.422，R1.704）"
    doc.recompute()


def measure_gap(sensor,sketch):
    section = sensor.section(Part.makePlane(40,40,App.Vector(-20,-20,SECTION_Z)))
    box = section.optimalBoundingBox(False,False)
    assert abs(box.XLength-BODY_LENGTH) < 1e-5
    assert abs(box.YLength-BODY_WIDTH) < 1e-5
    profile = sketch.Shape.copy()
    profile.translate(App.Vector(0,0,SECTION_Z-profile.BoundBox.ZMin))
    closest = profile.distToShape(section)[0]
    sample = [section.distToShape(Part.Vertex(point))[0]
              for edge in profile.Edges for point in edge.discretize(Number=41)]
    assert closest >= SIDE_GAP-.001
    assert max(sample) <= SIDE_GAP+.002
    return dict(reference_plane_z_mm=SECTION_Z, sensor_section_size_xy_mm=[box.XLength,box.YLength],
        window_size_xy_mm=[WINDOW_LENGTH,WINDOW_WIDTH],window_corner_radius_mm=WINDOW_RADIUS,
        nominal_clearance_per_side_mm=SIDE_GAP,section_min_clearance_mm=closest,
        sampled_max_clearance_mm=max(sample),rounded_rectangle_fit_tolerance_mm=.002)


def stamp_window_parameters(doc):
    p = doc.DesignParameters
    for name,value in [("CO2WindowLength",WINDOW_LENGTH),("CO2WindowWidth",WINDOW_WIDTH),
        ("CO2WindowCornerRadius",WINDOW_RADIUS),("CO2WindowSideGap",SIDE_GAP),
        ("CO2WindowReferencePlaneZ",SECTION_Z)]:
        if name not in p.PropertiesList:
            p.addProperty("App::PropertyLength",name,"Dimensions")
        setattr(p,name,value)
    p.Layout += " 后盖窗口按Z2.5处传感器实际穿板外形每边外扩0.3mm，约8.422x8.422/R1.704；不再按PCB侧10.1mm凸缘放大开口。"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default = SCRIPTS.parent if (SCRIPTS.parent/"盖板2.5mm_中壳加深_20261028").is_dir() else (
        Path.home()/"Downloads/ESP32-S3-LCD-1.47B_20260204 (1)")
    parser.add_argument("--root",type=Path,default=default)
    root = parser.parse_args().root.resolve()
    current = root/"盖板2.5mm_中壳加深_20261028"
    (root/".cad-recovery").mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="sensor-window03-",dir=root/".cad-recovery"))
    (stage/"打印文件").mkdir()
    print("STAGE",stage,flush=True)
    source = [current/(BACK+".FCStd"),current/ASSEMBLY]
    hashes = {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in source}
    from redesign_uniform_covers import validate,export_native,assign_shape,validate_assembly,clean
    from fix_co2_connector_layout import restore_appearance
    from shift_corner_mounts import check_corner_geometry
    assembly = App.openDocument(str(source[1]))
    sensor = assembly.CO2SensorCan.Shape
    before = {o.Name:(o.Shape.exportBrepToString(),tuple(o.Placement.toMatrix().A))
              for o in assembly.Objects if "Shape" in o.PropertiesList and o.Name != "RemovableBottomCover"}
    doc = App.openDocument(str(source[0]))
    old = clean(doc.Body.Tip.Shape)
    apply_window(doc)
    new = validate(doc)
    profile_report = measure_gap(sensor,doc.SensorWindowSketch)
    assert old.cut(new).Volume < 1e-6
    region = Part.makeBox(10.8,10.8,old.BoundBox.ZLength+.2,
        App.Vector(-5.4,-5.4,old.BoundBox.ZMin-.1))
    assert new.cut(old).cut(region).Volume < 1e-6
    assert sensor.common(new).Volume < 1e-7
    clearance = sensor.distToShape(new)[0]
    assert abs(clearance-SIDE_GAP) < .002
    corner_report = check_corner_geometry(doc,"back")
    doc.ReadMe.Label += "；传感器窗口改为实际穿板外形每边+0.3mm，不改传感器位置"
    shape,back_report = export_native(doc,stage,BACK)
    assign_shape(assembly.RemovableBottomCover,shape)
    stamp_window_parameters(assembly)
    report = validate_assembly(assembly)
    for name,(brep,pose) in before.items():
        obj = assembly.getObject(name)
        assert obj.Shape.exportBrepToString() == brep and tuple(obj.Placement.toMatrix().A) == pose,name
    raw = stage/"headless.FCStd"
    assembly.saveAs(str(raw))
    App.closeDocument(assembly.Name)
    final = stage/ASSEMBLY
    restore_appearance(source[1],raw,final,modified_names={"RemovableBottomCover"})
    check = App.openDocument(str(final))
    validate_assembly(check)
    assert abs(check.CO2SensorCan.Shape.distToShape(check.RemovableBottomCover.Shape)[0]-SIDE_GAP) < .002
    for name,(_,pose) in before.items():
        assert tuple(check.getObject(name).Placement.toMatrix().A) == pose,name
    App.closeDocument(check.Name)
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == v for p,v in hashes.items())
    records = json.loads((current/"检查记录.json").read_text())
    records["RemovableBottomCover"] = back_report
    records["assembly"] = dict(report,assembly_reopen="PASS")
    (stage/"检查记录.json").write_text(json.dumps(records,ensure_ascii=False,indent=2))
    result = dict(old_window_size_xy_mm=[10.7,10.7],new_profile=profile_report,
        sensor_to_cover_min_distance_mm=clearance,corner_mounts_unchanged=corner_report,
        sensor_membrane_recess_mm=report["membrane_recess_mm"],appearance_preserved=True,
        other_geometry_and_placements_unchanged=True,change_limited_to_central_window=True,
        source_files_unchanged=True,native=back_report,assembly_reopen="PASS",assembly=report)
    (stage/"传感器窗口每边0.3mm检查.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print("DONE",stage,flush=True)


if __name__ == "__main__":
    main()
