"""Replace only the front cover's stepped window with a screen-level funnel."""
import math
import FreeCAD as App
import Part

TOL = 1e-6


def rounded_prism(width, depth, height, radius, z, cx=0.0):
    x0, y0 = cx - width / 2, -depth / 2
    parts = [Part.makeBox(width-2*radius, depth, height, App.Vector(x0+radius, y0, z)),
             Part.makeBox(width, depth-2*radius, height, App.Vector(x0, y0+radius, z))]
    parts += [Part.makeCylinder(radius, height, App.Vector(x, y, z))
              for x in (x0+radius, x0+width-radius)
              for y in (y0+radius, y0+depth-radius)]
    return parts[0].multiFuse(parts[1:]).removeSplitter()


def rounded_wire(width, depth, radius, z, cx):
    wafer = rounded_prism(width, depth, 0.01, radius, z, cx)
    face = max((f for f in wafer.Faces if isinstance(f.Surface, Part.Plane)
                and f.BoundBox.ZLength < TOL), key=lambda f: f.CenterOfMass.z)
    wire = face.OuterWire.copy()
    wire.translate(App.Vector(0, 0, z-face.CenterOfMass.z))
    return wire


def display_faces(doc):
    candidates = [s for s in doc.ESP32BoardAssembly.Shape.Solids
                  if s.BoundBox.XLength > 30 and s.BoundBox.YLength > 15]
    screen = max(candidates, key=lambda s: s.BoundBox.ZMax)
    faces = [f for f in screen.Faces if isinstance(f.Surface, Part.Plane)
             and f.BoundBox.ZLength < TOL and f.Area > 40
             and f.normalAt(0, 0).z > .99]
    glass = max(faces, key=lambda f: f.CenterOfMass.z)
    active = max((f for f in faces if f.CenterOfMass.z >= glass.CenterOfMass.z-.1),
                 key=lambda f: f.Area)
    assert active is not glass
    return glass, active


def make_flush_bezel(doc):
    p, old = doc.DesignParameters, doc.FrontBezel.Shape
    assert "ScreenWindowFlushRevision" not in p.PropertiesList, "Already updated"
    horizontal = [f for f in old.Faces if isinstance(f.Surface, Part.Plane)
                  and f.BoundBox.ZLength < TOL and f.Area > 100]
    top = max((f for f in horizontal if f.normalAt(0, 0).z > .99), key=lambda f: f.Area)
    bottom = max((f for f in horizontal if f.normalAt(0, 0).z < -.99), key=lambda f: f.Area)
    z_top, z_base = top.CenterOfMass.z, bottom.CenterOfMass.z
    assert abs(z_top-z_base-3.0) < TOL
    glass, active = display_faces(doc)
    z_screen = glass.CenterOfMass.z
    assert 0 <= z_base-z_screen < .001, (z_base, z_screen)
    # Identify the old lower throat, not the wider underside relief.
    relief = [f for f in horizontal if f.normalAt(0,0).z < -.99
              and abs(f.CenterOfMass.z-z_base-1.0) < TOL]
    assert len(relief) == 1 and len(relief[0].Wires) == 2
    throat = min(relief[0].Wires, key=lambda w: w.BoundBox.XLength)
    b = throat.BoundBox
    width, depth, cx = b.XLength, b.YLength, (b.XMin+b.XMax)/2
    assert abs(width-32.85) < TOL and abs(depth-17.89) < TOL
    radius = 2.5

    # Preserve the old nominal aperture at the outer cover plane (before its
    # R0.4 edge blend), while lowering the funnel's throat by 1.71 mm.
    fraction = (3.0-1.71)/(3.21-1.71)
    top_w = width + (36.45-width)*fraction
    top_d = depth + (21.15-depth)*fraction
    top_r = radius + (4.05-radius)*fraction
    top_cx = cx + (-.85-cx)*fraction
    profiles = [rounded_wire(width, depth, radius, z_screen-.1, cx),
                rounded_wire(width, depth, radius, z_screen, cx),
                rounded_wire(top_w, top_d, top_r, z_top, top_cx),
                rounded_wire(top_w, top_d, top_r, z_top+.1, top_cx)]
    cutter = Part.makeLoft(profiles, True, True).removeSplitter()
    assert cutter.isValid() and len(cutter.Solids) == 1
    blank = Part.Face(bottom.OuterWire).extrude(App.Vector(0,0,z_top-z_base))
    # The model has a 0.000479 mm assembly offset. Extend only the window lip
    # through this tiny distance, leaving the cover-to-shell seating unchanged.
    lip_blank = rounded_prism(37.1, 21.6, z_base-z_screen+.02, 4.1, z_screen, -.6)
    result = blank.fuse(lip_blank).cut(cutter).removeSplitter()
    edges = [e for e in result.Edges if e.BoundBox.ZLength < TOL
             and abs(e.CenterOfMass.z-z_top) < TOL
             and e.BoundBox.XLength < 37 and e.BoundBox.YLength < 22
             and abs(e.CenterOfMass.x) < 20 and abs(e.CenterOfMass.y) < 12]
    assert len(edges) == 8, ("Top aperture blend edge count", len(edges))
    result = result.makeFillet(.4, edges)

    # Reuse each existing bore axis, diameter and depth from its actual face.
    hole_faces = [f for f in old.Faces if isinstance(f.Surface, Part.Cylinder)
                  and abs(f.Surface.Axis.z) > .99
                  and any(abs(f.Surface.Radius-r) < TOL for r in (1.45, 2.55))]
    assert len(hole_faces) == 8
    for f in hole_faces:
        axis, r = f.Surface.Center, f.Surface.Radius
        z0, z1 = f.BoundBox.ZMin, f.BoundBox.ZMax
        if r < 2:
            z0 -= .1
        else:
            z1 += .1
        result = result.cut(Part.makeCylinder(r, z1-z0, App.Vector(axis.x, axis.y, z0)))
    result = result.removeSplitter()
    assert result.isValid() and len(result.Solids) == 1
    roi = rounded_prism(38.2, 22.7, 5, 4.2, z_base-.1, -.6)
    assert old.cut(result).cut(roi).Volume < TOL
    assert result.cut(old).cut(roi).Volume < TOL, "Changed geometry outside window"
    for f in hole_faces:
        axis, r = f.Surface.Center, f.Surface.Radius
        bore = Part.makeCylinder(r-1e-4, f.BoundBox.ZLength,
                                 App.Vector(axis.x, axis.y, f.BoundBox.ZMin))
        assert result.common(bore).Volume < TOL, "Bore changed"
    active_projection = Part.Face(active.OuterWire).extrude(App.Vector(0,0,z_top-active.CenterOfMass.z+.1))
    assert result.common(active_projection).Volume < TOL, "Display area masked"
    overlap = result.common(doc.ESP32BoardAssembly.Shape).Volume
    shell_overlap = result.common(doc.RearShell.Shape).Volume
    assert overlap < TOL, ("Display collision", overlap)
    assert shell_overlap < TOL, ("Shell collision", shell_overlap)
    assert result.distToShape(glass)[0] < TOL, "Lip must meet glass datum"
    z_lip = min(f.BoundBox.ZMin for f in result.Faces)
    assert abs(z_lip-z_screen) < TOL
    angles = [math.degrees(math.atan2(z_top-z_screen, run))
              for run in ((top_d-depth)/2,
                          (cx-width/2)-(top_cx-top_w/2),
                          (top_cx+top_w/2)-(cx+width/2))]
    info = dict(screen_z=z_screen, cover_top=z_top, throat_cx=cx,
                long_angle=angles[0], left_angle=angles[1], right_angle=angles[2],
                slope_depth=z_top-z_screen, added=result.cut(old).Volume,
                removed=old.cut(result).Volume)
    print("FLUSH_BEZEL_VALIDATED", info, "DISPLAY_OVERLAP", overlap,
          "SHELL_OVERLAP", shell_overlap, "ACTIVE_AREA_MASKED", 0.0, flush=True)
    return result, info


def update_bezel_parameters(doc, info):
    p = doc.DesignParameters
    p.ScreenToLidGap = 0.0
    p.BezelInnerWallHeight = 0.0
    p.ScreenWindowCenterX = info["throat_cx"]
    for name, value, kind in (
        ("ScreenWindowFlushRevision", 1, "Integer"),
        ("ScreenWindowReliefDepth", 0.0, "Length"),
        ("ScreenWindowLowerEdgeZ", info["screen_z"], "Length"),
        ("ScreenWindowChamferDepth", info["slope_depth"], "Length"),
        ("ScreenWindowLongSideAngle", info["long_angle"], "Angle"),
        ("ScreenWindowLeftSideAngle", info["left_angle"], "Angle"),
        ("ScreenWindowRightSideAngle", info["right_angle"], "Angle"),
    ):
        if name not in p.PropertiesList:
            p.addProperty("App::Property"+kind, name, "Screen window")
        setattr(p, name, value)
    p.Layout += ("显示窗取消内侧1mm避让槽和0.7mm竖直壁；连续斜面下缘"
                 "与屏幕玻璃边缘上表面齐平，模型无压入；保留32.85×17.89mm"
                 "下口及有效显示区，外侧过渡圆角R0.4、外轮廓和螺丝孔不变。")
    doc.FrontBezel.Label = "前盖（齐平屏幕连续斜面，无内侧退让槽）"


def apply_flush_bezel(doc):
    result, info = make_flush_bezel(doc)
    obj = doc.FrontBezel
    pose = App.Placement(obj.Placement)
    local = result.transformed(pose.inverse().toMatrix(), copy=True)
    obj.Shape = local
    obj.Placement = pose
    update_bezel_parameters(doc, info)
    doc.recompute()
    return info
