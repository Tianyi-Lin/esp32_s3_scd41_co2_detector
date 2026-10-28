"""Correct only the two simplified CO2 connectors to the PCB's left/right ends.

Run with FreeCAD Python. Outputs go to a recovery stage; sources are not saved.
The PCB, its holes, sensor body, enclosure and all their placements stay intact.
Connector dimensions remain placeholders, not measured plug/cable envelopes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import FreeCAD as App
import Part

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))


def bounds(shape):
    box = shape.BoundBox
    return [getattr(box, key) for key in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")]


def centers(shape):
    return sorted([[solid.CenterOfMass.x, solid.CenterOfMass.y, solid.CenterOfMass.z]
                   for solid in shape.Solids])


def assign_world_shape(obj, shape):
    pose = App.Placement(obj.Placement)
    local = shape.transformed(pose.inverse().toMatrix(), copy=True)
    detached = Part.Shape()
    detached.importBrepFromString(local.exportBrepToString())
    obj.Shape = detached
    obj.Placement = pose
    assert max(abs(a-b) for a, b in zip(bounds(obj.Shape), bounds(shape))) < 1e-6


def correct_connectors(doc):
    pcb = doc.CO2SensorPCB.Shape.BoundBox
    obj = doc.CO2SensorConnectors
    solids = obj.Shape.Solids
    assert len(solids) == 2, "Expected two connector placeholders"
    dimensions = sorted([solids[0].BoundBox.XLength, solids[0].BoundBox.YLength])
    depth, width = dimensions
    height = solids[0].BoundBox.ZLength
    assert abs(pcb.XLength-25.4) < 1e-5 and abs(pcb.YLength-22.86) < 1e-5
    assert abs(depth-3.7) < 1e-5 and abs(width-7.2) < 1e-5 and abs(height-2.5) < 1e-5
    z = obj.Shape.BoundBox.ZMin
    cy = (pcb.YMin+pcb.YMax)/2
    before = centers(obj.Shape)
    shape = Part.makeCompound([
        Part.makeBox(depth, width, height, App.Vector(x, cy-width/2, z))
        for x in (pcb.XMin, pcb.XMax-depth)
    ])
    assign_world_shape(obj, shape)
    obj.Label = "SCD41 左右接线插座（简化外形，沿长边X）"
    assign_world_shape(doc.CO2SensorEnvelope, Part.makeCompound([
        doc.getObject(n).Shape for n in ("CO2SensorPCB", "CO2SensorCan", "CO2SensorConnectors")
    ]))
    p = doc.DesignParameters
    if "CO2ConnectorArrangement" not in p.PropertiesList:
        p.addProperty("App::PropertyString", "CO2ConnectorArrangement", "Dimensions")
    p.CO2ConnectorArrangement = "Left/right along PCB long X axis; simplified 3.7 x 7.2 x 2.5 mm placeholders; plug and cable not modeled"
    doc.recompute()
    after = centers(obj.Shape)
    assert all(abs(c[1]-cy) < 1e-6 for c in after)
    assert after[0][0] < 0 < after[1][0]
    assert all(s.isValid() for s in obj.Shape.Solids)
    obj.Shape.check(True)
    return dict(before_connector_centers_mm=before, connector_centers_mm=after,
                arrangement="left/right, PCB long X axis",
                connector_placeholder_size_xyz_mm=[depth, width, height],
                connector_size_source="previous simplified model, not a hardware measurement",
                connector_z_mm=[z, z+height], plugged_connector_and_wire_space_validated=False)


def restore_appearance(reference, generated, destination, modified_names=None):
    """Restore views and untouched BREP payloads normalized by FreeCADCmd."""
    with zipfile.ZipFile(reference) as original, zipfile.ZipFile(generated) as updated:
        gui = original.read("GuiDocument.xml")
        resources = {e.get("file") for e in ET.fromstring(gui).iter() if e.get("file")}
        assert not resources & set(updated.namelist())
        if modified_names is None:
            modified_names = {"CO2SensorConnectors", "CO2SensorEnvelope"}
        modified_breps = {name+".Shape.brp" for name in modified_names}
        unchanged_breps = {name for name in original.namelist() if name.endswith(".brp")
            and name not in modified_breps}
        assert unchanged_breps <= set(updated.namelist())
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as result:
            for item in updated.infolist():
                data = original.read(item.filename) if item.filename in unchanged_breps else updated.read(item.filename)
                result.writestr(item, data)
            result.writestr("GuiDocument.xml", gui)
            for name in sorted(resources):
                result.writestr(name, original.read(name))
    with zipfile.ZipFile(destination) as result, zipfile.ZipFile(reference) as original:
        assert result.read("GuiDocument.xml") == original.read("GuiDocument.xml")
        assert all(result.read(n) == original.read(n) for n in resources)
        assert all(result.read(n) == original.read(n) for n in unchanged_breps)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = SCRIPTS.parent if (SCRIPTS.parent/"盖板2.5mm_中壳加深_20261028").is_dir() else (
        Path.home()/"Downloads/ESP32-S3-LCD-1.47B_20260204 (1)")
    parser.add_argument("--root", type=Path, default=default_root)
    args = parser.parse_args()
    root = args.root.resolve()
    source = root/"盖板2.5mm_中壳加深_20261028/装配检查_盖板2.5mm_中间壳加深.FCStd"
    (root/".cad-recovery").mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="co2-connectors-", dir=root/".cad-recovery"))
    print("STAGE", stage, flush=True)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    doc = App.openDocument(str(source))
    modified = {"CO2SensorConnectors", "CO2SensorEnvelope"}
    before = {o.Name: (o.Shape.exportBrepToString(), tuple(o.Placement.toMatrix().A))
              for o in doc.Objects if "Shape" in o.PropertiesList and o.Name not in modified}
    report = correct_connectors(doc)
    from redesign_uniform_covers import validate_assembly
    report["assembly"] = validate_assembly(doc)
    for name, (brep, pose) in before.items():
        obj = doc.getObject(name)
        assert obj.Shape.exportBrepToString() == brep, name
        assert tuple(obj.Placement.toMatrix().A) == pose, name
    raw = stage/"headless.FCStd"
    doc.saveAs(str(raw))
    App.closeDocument(doc.Name)
    final = stage/source.name
    restore_appearance(source, raw, final)
    check = App.openDocument(str(final))
    validate_assembly(check)
    assert max(abs(a-b) for actual, expected in zip(centers(check.CO2SensorConnectors.Shape),
        report["connector_centers_mm"]) for a, b in zip(actual, expected)) < 1e-7
    for name, (brep, pose) in before.items():
        obj = check.getObject(name)
        # Serialization can normalize insignificant decimal spelling on reopen.
        prior = Part.Shape()
        prior.importBrepFromString(brep)
        assert abs(prior.Volume-obj.Shape.Volume) < 1e-6, name
        assert max(abs(a-b) for a, b in zip(bounds(prior), bounds(obj.Shape))) < 1e-6, name
        assert tuple(obj.Placement.toMatrix().A) == pose, name
    App.closeDocument(check.Name)
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(final) as new:
        data = ET.fromstring(old.read("Document.xml"))
        unchanged_files = []
        for obj in data.findall("./ObjectData/Object"):
            if obj.get("name") not in modified:
                unchanged_files.extend(e.get("file") for e in obj.iter() if e.get("file") and e.get("file").endswith(".brp"))
        assert all(old.read(n) == new.read(n) for n in unchanged_files)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    report.update(other_geometry_and_placements_unchanged=True, appearance_preserved=True,
                  assembly_reopen="PASS", source_unchanged=True)
    (stage/"接线插座布局检查.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print("DONE", final, flush=True)


if __name__ == "__main__":
    main()
