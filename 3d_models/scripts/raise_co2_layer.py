"""Extend the lower enclosure without scaling or rebuilding existing details."""
import re
import FreeCAD as App
import Part

UPPER_OBJECTS = ("FrontBezel", "ESP32BoardAssembly", "HeaderPinsKeepout",
                 "ButtonPlungerPositive", "ButtonPlungerNegative")
TOL = 1e-6


def pcb_substrate(doc):
    candidates = [s for s in doc.ESP32BoardAssembly.Shape.Solids
                  if s.BoundBox.XLength > 30 and s.BoundBox.YLength > 18
                  and abs(s.BoundBox.ZLength - 0.8) < 0.005]
    assert len(candidates) == 1, "PCB substrate must be unambiguous"
    return candidates[0]


def floor_z(doc):
    faces = [f for f in doc.RemovableBottomCover.Shape.Faces
             if isinstance(f.Surface, Part.Plane)
             and f.BoundBox.ZLength < TOL and f.Area > 100
             and f.normalAt(0, 0).z > 0.99]
    assert len(faces) == 1, "Bottom inner floor must be unambiguous"
    return faces[0].CenterOfMass.z


def co2_pcb_top_z(doc):
    faces = [f for f in doc.CO2SensorPCB.Shape.Faces
             if isinstance(f.Surface, Part.Plane)
             and f.BoundBox.ZLength < TOL and f.Area > 100
             and f.normalAt(0, 0).z > 0.99]
    assert len(faces) == 1, "CO2 PCB top must be unambiguous"
    return faces[0].CenterOfMass.z


def local_shape(obj):
    return obj.Shape.transformed(obj.Placement.inverse().toMatrix(), copy=True)


def equal_volume(a, b):
    assert a.cut(b).Volume < TOL and b.cut(a).Volume < TOL


def raise_lower_layer(doc, target=20.0, delta=None, split_z=13.0,
                      reference="bottom_inner", allow_existing=False):
    assert reference in ("bottom_inner", "co2_pcb_top")
    p = doc.DesignParameters
    extended = "LowerLayerHeightIncrease" in p.PropertiesList
    assert not extended or allow_existing, "Already extended; explicit repeat required"
    old_floor_gap = (p.PCBBackToBottomInnerDistance.Value if extended else
                     pcb_substrate(doc).BoundBox.ZMin - floor_z(doc))
    cumulative = p.LowerLayerHeightIncrease.Value if extended else 0.0
    deck_bottom = p.InterLayerDeckBottomZ.Value if extended else 13.5
    deck_top = p.InterLayerDeckTopZ.Value if extended else 15.5
    if delta is None:
        datum = co2_pcb_top_z(doc) if reference == "co2_pcb_top" else floor_z(doc)
        delta = target - (pcb_substrate(doc).BoundBox.ZMin - datum)
    assert 0.0 < delta < 5.0, ("Unexpected height correction", delta)
    shell = doc.RearShell
    pose = App.Placement(shell.Placement)
    original = local_shape(shell)
    lower_box = Part.makeBox(200, 200, split_z + 100, App.Vector(-100, -100, -100))
    upper_box = Part.makeBox(200, 200, 100, App.Vector(-100, -100, split_z))
    lower = original.common(lower_box).removeSplitter()
    upper = original.common(upper_box).removeSplitter()
    caps = [f for f in lower.Faces if isinstance(f.Surface, Part.Plane)
            and f.BoundBox.ZLength < TOL
            and abs(f.CenterOfMass.z - split_z) < TOL
            and f.normalAt(0, 0).z > 0.99]
    assert len(caps) == 1, ("Unexpected section topology", len(caps))
    band = caps[0].extrude(App.Vector(0, 0, delta))
    assert band.isValid() and len(band.Solids) == 1
    upper.translate(App.Vector(0, 0, delta))
    result = lower.multiFuse([band, upper]).removeSplitter()
    assert result.isValid() and len(result.Solids) == 1
    assert abs(result.Volume - original.Volume - band.Volume) < TOL
    equal_volume(result.common(lower_box), lower)
    moved_upper_box = upper_box.copy()
    moved_upper_box.translate(App.Vector(0, 0, delta))
    equal_volume(result.common(moved_upper_box), upper)
    # Through-column bores must remain open across the newly added band.
    for x in (-p.SideBodyColumnCenterX.Value, p.SideBodyColumnCenterX.Value):
        for y in (-p.SideBodyColumnCenterY.Value, p.SideBodyColumnCenterY.Value):
            bore = Part.makeCylinder(p.SideBodyTapHoleDiameter.Value / 2 - 0.001,
                                     result.BoundBox.ZLength + 0.2,
                                     App.Vector(x, y, result.BoundBox.ZMin - 0.1))
            assert result.common(bore).Volume < TOL
    shell.Shape = result
    shell.Placement = pose
    for name in UPPER_OBJECTS:
        obj = doc.getObject(name)
        placement = App.Placement(obj.Placement)
        placement.Base.z += delta
        obj.Placement = placement
    for name in ("RearShellDepth", "BoardLayerStart", "PCBMountContactHeight",
                 "HeaderSlotCutBottomZ", "HeaderSlotCutTopZ", "ButtonCenterZ",
                 "PCBColumnReliefBottomZ", "USBCVentToConnectorGap"):
        setattr(p, name, getattr(p, name).Value + delta)
    if "HorizontalFootFrontCenterZ" in p.PropertiesList:
        p.HorizontalFootFrontCenterZ = p.HorizontalFootFrontCenterZ.Value + delta
    # Parameters describe the compact assembly, including in the exploded copy.
    co2_above_floor = p.CO2BottomStandoffHeight.Value + doc.CO2SensorPCB.Shape.BoundBox.ZLength
    new_floor_gap = old_floor_gap + delta
    new_pcb_gap = new_floor_gap - co2_above_floor
    assert abs((new_pcb_gap if reference == "co2_pcb_top" else new_floor_gap) - target) < TOL
    for name, value in (("PCBBackToBottomInnerDistance", new_floor_gap),
                        ("PCBBackToCO2PCBTopDistance", new_pcb_gap),
                        ("CO2PCBTopZ", p.BottomCoverThickness.Value + co2_above_floor),
                        ("PCBBackPlaneZ", p.BottomCoverThickness.Value + new_floor_gap),
                        ("LowerLayerHeightIncrease", cumulative + delta),
                        ("LatestLowerLayerHeightIncrease", delta),
                        ("LowerLayerExtensionPlaneZ", split_z),
                        ("InterLayerDeckBottomZ", deck_bottom + delta),
                        ("InterLayerDeckTopZ", deck_top + delta)):
        if name not in p.PropertiesList:
            p.addProperty("App::PropertyLength", name, "Dimensions")
        setattr(p, name, value)
    if "LowerLayerHeightReference" not in p.PropertiesList:
        p.addProperty("App::PropertyString", "LowerLayerHeightReference", "Documentation")
    p.LowerLayerHeightReference = ("ESP32 PCB基材下表面至CO2 PCB基材上表面；"
                                  "不以SCD41传感器金属外壳顶面为基准。"
                                  if reference == "co2_pcb_top" else "ESP32 PCB基材下表面至底盖内侧大平面。")
    layout = re.sub(r"顶面Z[0-9.]+", "顶面Z%.6f" % (deck_top + delta), p.Layout)
    layout = re.sub(r"本次仅加高CO2下层.*?PCB背面至底盖内侧大平面垂直距离[0-9.]+mm。", "", layout)
    layout = re.sub(r"当前下层高度基准：.*?安装关系保持不变。", "", layout)
    p.Layout = layout + (
        "当前下层高度基准：ESP32 PCB下表面至CO2 PCB上表面%.6fmm，"
        "至下盖内侧平面%.6fmm；不以传感器顶部为基准。"
        "下盖和CO2总成不动，中层板及上层部件同步上移，安装关系保持不变。"
        % (new_pcb_gap, new_floor_gap))
    doc.recompute()
    print("LOWER_LAYER_EXTENDED", doc.Label, "DELTA", delta,
          "SECTION_AREA", caps[0].Area, "ADDED_VOLUME", band.Volume,
          "SHELL_VOLUME", result.Volume, flush=True)
    return delta
