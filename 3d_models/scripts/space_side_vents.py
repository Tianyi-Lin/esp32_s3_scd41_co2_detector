"""Redistribute the existing capsule grilles, without rebuilding the enclosure."""
import math
import FreeCAD as App
import Part

TOL = 1e-6


def capsule(x, cy, cz, length, height, depth=3.0):
    r = height / 2
    straight = length - height
    box = Part.makeBox(depth, straight, height,
                       App.Vector(x, cy-straight/2, cz-r))
    ends = [Part.makeCylinder(r, depth, App.Vector(x, cy+sign*straight/2, cz),
                              App.Vector(1, 0, 0)) for sign in (-1, 1)]
    return box.multiFuse(ends).removeSplitter()


def vent_faces(shape, radius):
    return [f for f in shape.Faces if isinstance(f.Surface, Part.Cylinder)
            and abs(f.Surface.Axis.x) > .999999
            and abs(f.Surface.Radius-radius) < TOL]


def space_side_vents(doc, pitch=2.6):
    p = doc.DesignParameters
    shell = doc.RearShell
    original = shell.Shape.copy()
    pose = App.Placement(shell.Placement)
    assert pose.toMatrix().A == App.Placement().toMatrix().A
    old_pitch = p.ConvectionSlotPitch.Value
    length, height = p.ConvectionSlotWidth.Value, p.ConvectionSlotHeight.Value
    z0 = p.USBCVentSlotStartZ.Value
    count = p.USBCVentSlotCount
    assert abs(old_pitch-1.7) < TOL
    assert count == 5 and abs(length-14) < TOL and abs(height-.9) < TOL
    assert len(vent_faces(original, height/2)) == 20
    old_top = z0+(count-1)*old_pitch+height
    new_top = z0+(count-1)*pitch+height
    deck_gap = p.InterLayerDeckBottomZ.Value-new_top
    usb_gap = p.USBCVentToConnectorGap.Value-(new_top-old_top)
    assert deck_gap >= 1.4 and usb_gap >= 3.6
    old_voids, new_cuts = [], []
    for side in (-1, 1):
        x0 = -23.0 if side < 0 else 20.0
        wall_x = -22.7 if side < 0 else 20.5
        wall = Part.makeBox(2.2, 16, new_top-z0+2,
                            App.Vector(wall_x, -8, z0-1))
        for i in range(count):
            old = capsule(x0, 0, z0+i*old_pitch+height/2, length, height)
            assert original.common(old).Volume < TOL
            old_voids.append(old.common(wall))
            new_cuts.append(capsule(x0, 0, z0+i*pitch+height/2, length, height))
    fills = Part.makeCompound(old_voids)
    cuts = Part.makeCompound(new_cuts)
    result = original.multiFuse(old_voids).cut(cuts).removeSplitter()
    assert result.isValid() and len(result.Solids) == 1
    assert abs(result.Volume-original.Volume) < TOL
    assert result.cut(original).cut(fills).Volume < TOL
    assert original.cut(result).cut(cuts).Volume < TOL
    assert result.common(cuts).Volume < TOL
    assert len(vent_faces(result, height/2)) == 20
    records = sorted(round(f.Surface.Center.z, 6) for f in vent_faces(result, height/2))
    expected = sorted(round(z0+i*pitch+height/2, 6) for i in range(count) for _ in range(4))
    assert records == expected
    for key in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax"):
        assert abs(getattr(result.BoundBox, key)-getattr(original.BoundBox, key)) < TOL
    # The entire upper structure, including USB and the deck, is unchanged.
    upper = Part.makeBox(100, 100, 100, App.Vector(-50, -50, p.InterLayerDeckBottomZ.Value))
    a, b = original.common(upper), result.common(upper)
    assert a.cut(b).Volume < TOL and b.cut(a).Volume < TOL
    shell.Shape = result
    shell.Placement = pose
    p.ConvectionSlotPitch = pitch
    p.USBCVentToConnectorGap = usb_gap
    for key, val in (("ConvectionSlotWeb", pitch-height),
                     ("ConvectionSlotTopZ", new_top),
                     ("ConvectionSlotToDeckGap", deck_gap),
                     ("ConvectionGrilleHeight", new_top-z0)):
        if key not in p.PropertiesList:
            p.addProperty("App::PropertyLength", key, "Dimensions")
        setattr(p, key, val)
    p.Layout += (
        "加高后两短侧各5条圆端通风槽重新均布：槽14×0.9mm、端R0.45不变；"
        "中心距2.6mm，槽间实体筋1.7mm，下沿Z5、上沿Z16.3；"
        "距中层板下表面1.450479mm，距C口下沿3.650479mm。"
    )
    doc.recompute()
    area = count*2*((length-height)*height+math.pi*(height/2)**2)
    print("VENTS_SPACED", doc.Label, "PITCH", pitch, "WEB", pitch-height,
          "TOP", new_top, "DECK_GAP", deck_gap, "USB_GAP", usb_gap,
          "TOTAL_OPEN_AREA", area, "VOLUME", result.Volume, flush=True)
    return result
