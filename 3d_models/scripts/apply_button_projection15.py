"""Stage 1.5 mm button projection and user-approved 2 mm integral side feet.

Preserve inner button contact/collar/travel, PCB layout, covers and appearance.
Export an updated editable middle shell and checked STEP/STL, plus two identical
button prints (one model to print twice). Never overwrite input files.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile

import FreeCAD as App
import Mesh
import Part

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from horizontal_supports import extend_hemispherical_buttons, export_closed_button
from fix_co2_connector_layout import restore_appearance, bounds

PROJECTION = 1.5
FOOT_HEIGHT = 2.0
ASSEMBLY = "装配检查_盖板2.5mm_中间壳加深.FCStd"
MIDDLE = "中间外壳_加深_草图编辑"
BUTTON = "按键顶杆_突出1.5mm_打印2件"
CHANGED = {"RearShell", "ButtonPlungerPositive", "ButtonPlungerNegative"}


def export_button_print(doc, folder):
    folder = Path(folder)
    folder.mkdir(exist_ok=True)
    a, b = doc.ButtonPlungerPositive.Shape, doc.ButtonPlungerNegative.Shape
    cx = (a.BoundBox.XMin+a.BoundBox.XMax)/2
    cz = (a.BoundBox.ZMin+a.BoundBox.ZMax)/2
    mirrored = b.copy()
    mirrored.rotate(App.Vector(cx, 0, cz), App.Vector(1, 0, 0), 180)
    assert a.cut(mirrored).Volume+mirrored.cut(a).Volume < 1e-6
    # Collar base lies on the print bed, hemisphere points up. Both mirrored
    # assembly instances use the exact same physical printed part.
    printable = a.copy()
    printable.translate(App.Vector(-cx, -a.BoundBox.YMin, -cz))
    printable.rotate(App.Vector(), App.Vector(1, 0, 0), 90)
    assert abs(printable.BoundBox.ZMin) < 1e-6
    assert abs(printable.Volume-a.Volume) < 1e-6
    printing = App.newDocument("ButtonPrint15")
    obj = printing.addObject("PartDesign::Feature", "Button")
    obj.Label = BUTTON
    detached = Part.Shape()
    detached.importBrepFromString(printable.exportBrepToString())
    obj.Shape = detached
    printing.recompute()
    obj.Shape.check(True)
    step = folder/(BUTTON+".step")
    stl = folder/(BUTTON+".stl")
    Part.export([obj], str(step))
    imported = Part.read(str(step))
    assert imported.isValid() and len(imported.Solids) == 1
    imported.check(True)
    assert abs(imported.Volume-printable.Volume) < 1e-5
    export_closed_button(obj, str(stl))
    mesh = Mesh.Mesh(str(stl))
    assert mesh.isSolid() and mesh.countComponents() == 1
    assert not mesh.hasNonManifolds() and not mesh.hasSelfIntersections()
    assert mesh.countNonUniformOrientedFacets() == 0 and mesh.Volume > 0
    record = dict(step=step.name, stl=stl.name, quantity=2,
        print_orientation="collar base Z=0, hemispherical tip upward",
        volume_mm3=printable.Volume, mesh_facets=mesh.CountFacets,
        mesh_closed=True, mesh_components=1, mesh_non_manifold=False,
        mesh_self_intersections=False, mesh_inconsistent_faces=0,
        step_roundtrip="PASS", symmetric_buttons_identical="PASS")
    App.closeDocument(printing.Name)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default = SCRIPTS.parent if (SCRIPTS.parent/"盖板2.5mm_中壳加深_20261028").is_dir() else (
        Path.home()/"Downloads/ESP32-S3-LCD-1.47B_20260204 (1)")
    parser.add_argument("--root", type=Path, default=default)
    root = parser.parse_args().root.resolve()
    current = root/"盖板2.5mm_中壳加深_20261028"
    (root/".cad-recovery").mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="button15-feet2-", dir=root/".cad-recovery"))
    (stage/"打印文件").mkdir()
    sources = [current/ASSEMBLY, current/(MIDDLE+".FCStd")]
    hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    print("STAGE", stage, flush=True)
    from redesign_uniform_covers import export_native, validate, validate_assembly, assign_shape

    native = App.openDocument(str(sources[1]))
    old = native.Body.Tip.Shape
    assert abs(native.FootPad.Length.Value-1.5) < 1e-6
    old_end = old.BoundBox.YMax
    pads = [f.CenterOfMass for f in old.Faces if isinstance(f.Surface, Part.Plane)
            and f.BoundBox.YLength < 1e-6 and abs(f.CenterOfMass.y-old_end) < 1e-6]
    assert len(pads) == 4
    native.FootPad.Length = FOOT_HEIGHT
    native.FootPad.Label = "四个一体侧脚钉 外伸2mm"
    native.ReadMe.Label += "；侧脚钉外伸2mm，配合1.5mm按钮保留0.5mm离桌间隙"
    new = validate(native)
    assert old.cut(new).Volume < 1e-6
    assert abs(new.Volume-old.Volume-4*math.pi*2**2*.5) < 1e-5
    affected = Part.makeCompound([Part.makeCylinder(2.01, .87,
        App.Vector(p.x, old_end-.36, p.z), App.Vector(0, 1, 0)) for p in pads])
    assert new.cut(old).cut(affected).Volume < 1e-6
    assert abs(new.BoundBox.YMax-18.95) < 1e-6
    new_pads = [f for f in new.Faces if isinstance(f.Surface, Part.Plane)
        and f.BoundBox.YLength < 1e-6 and abs(f.CenterOfMass.y-18.95) < 1e-6]
    assert len(new_pads) == 4
    assert all(abs(f.Area-math.pi*1.65**2) < 1e-5 for f in new_pads)
    middle_shape, middle_report = export_native(native, stage, MIDDLE)

    doc = App.openDocument(str(sources[0]))
    before = {o.Name: (o.Shape.exportBrepToString(), tuple(o.Placement.toMatrix().A))
              for o in doc.Objects if "Shape" in o.PropertiesList and o.Name not in CHANGED}
    # This native shape already carries the correct root placement.
    assign_shape(doc.RearShell, middle_shape)
    p = doc.DesignParameters
    p.HorizontalFootHeight = FOOT_HEIGHT
    p.HorizontalSupportPlaneY = p.OuterWidth.Value/2+FOOT_HEIGHT
    p.OverallWidthIncludingFeet = p.OuterWidth.Value+FOOT_HEIGHT
    extend_hemispherical_buttons(doc, projection=PROJECTION)
    assembly_report = validate_assembly(doc)
    button_report = export_button_print(doc, stage/"打印文件")
    for name, (brep, pose) in before.items():
        obj = doc.getObject(name)
        assert obj.Shape.exportBrepToString() == brep, name
        assert tuple(obj.Placement.toMatrix().A) == pose, name
    raw = stage/"headless.FCStd"
    doc.saveAs(str(raw))
    App.closeDocument(doc.Name)
    final = stage/ASSEMBLY
    restore_appearance(sources[0], raw, final, modified_names=CHANGED)
    check = App.openDocument(str(final))
    validate_assembly(check)
    for name in CHANGED:
        check.getObject(name).Shape.check(True)
    for name, (_, pose) in before.items():
        assert tuple(check.getObject(name).Placement.toMatrix().A) == pose, name
    assert max(abs(a-b) for a, b in zip(bounds(check.RearShell.Shape), bounds(middle_shape))) < 1e-6
    assert abs(check.RearShell.Shape.Volume-middle_shape.Volume) < 1e-5
    App.closeDocument(check.Name)
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == value for path, value in hashes.items())

    records = json.loads((current/"检查记录.json").read_text())
    records["RearShell"] = middle_report
    records["assembly"] = dict(assembly_report, assembly_reopen="PASS")
    records["ButtonPlunger"] = button_report
    (stage/"检查记录.json").write_text(json.dumps(records, ensure_ascii=False, indent=2))
    report = dict(button_projection_before_mm=1, button_projection_after_mm=PROJECTION,
        foot_height_before_mm=1.5, foot_height_after_mm=FOOT_HEIGHT,
        ground_clearance_mm=.5, tip_radius_mm=1.5, guide_travel_checked_mm=[.3,.5,.8],
        internal_contact_and_collar_unchanged=True, other_assembly_geometry_unchanged=True,
        four_coplanar_feet=True, foot_edge_radius_mm=.35, appearance_preserved=True,
        source_files_unchanged=True, assembly_reopen="PASS", middle=middle_report,
        button=button_report, assembly=assembly_report)
    (stage/"按钮1.5mm_脚钉2mm检查.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print("DONE", stage, flush=True)


if __name__ == "__main__":
    main()
