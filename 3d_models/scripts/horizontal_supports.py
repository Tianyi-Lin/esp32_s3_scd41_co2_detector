"""Four integral +Y side feet and recessed hemispherical button tips."""
import math
import FreeCAD as App
import Part
import Mesh
import MeshPart

TOL = 1e-6


def export_closed_button(obj, path):
    """Explicit remeshing avoids the default export's open sphere-pole seam."""
    shape = obj.Shape.Solids[0]
    for linear, angular in ((0.01, 0.1), (0.02, 0.15), (0.03, 0.2), (0.05, 0.3)):
        mesh = MeshPart.meshFromShape(Shape=shape.copy(), LinearDeflection=linear,
                                     AngularDeflection=angular, Relative=False)
        if mesh.isSolid():
            mesh.write(path)
            checked = Mesh.Mesh(path)
            assert checked.isSolid(), "Saved button mesh must stay closed"
            print("BUTTON_STL_CLOSED", checked.CountFacets, linear, angular, flush=True)
            return
    raise RuntimeError("Could not create a closed button STL")


def local_shape(obj):
    return obj.Shape.transformed(obj.Placement.inverse().toMatrix(), copy=True)


def add_horizontal_supports(doc):
    p = doc.DesignParameters
    assert "HorizontalFootCount" not in p.PropertiesList, "Feet already exist"
    assert abs(p.ButtonOuterProjection.Value - 2.0) < TOL
    wall_y = p.OuterWidth.Value / 2.0
    projection, tip_radius = 1.0, 1.5
    foot_height, foot_radius, edge_radius = 1.5, 2.0, 0.35
    shell = doc.RearShell
    old_shell = local_shape(shell)
    foot_zs = (5.5, old_shell.BoundBox.ZMax - 3.0)
    foot_centers = [(x, z) for x in (-15.0, 15.0) for z in foot_zs]
    feet = []
    for x, z in foot_centers:
        foot = Part.makeCylinder(foot_radius, foot_height + 0.2,
                                 App.Vector(x, wall_y - 0.2, z), App.Vector(0, 1, 0))
        rim = [e for e in foot.Edges if e.BoundBox.YLength < TOL
               and abs(e.CenterOfMass.y - wall_y - foot_height) < TOL]
        assert len(rim) == 1
        foot = foot.makeFillet(edge_radius, rim)
        assert foot.isValid() and len(foot.Solids) == 1
        assert old_shell.common(foot).Volume > 1.0, "Foot not firmly rooted"
        feet.append(foot)
    new_shell = old_shell.multiFuse(feet).removeSplitter()
    assert new_shell.isValid() and len(new_shell.Solids) == 1
    assert old_shell.cut(new_shell).Volume < TOL, "Existing shell was removed"
    added = new_shell.cut(old_shell)
    assert added.cut(Part.makeCompound(feet)).Volume < TOL
    assert abs(new_shell.BoundBox.YMax - wall_y - foot_height) < TOL
    support_faces = [f for f in new_shell.Faces if isinstance(f.Surface, Part.Plane)
                     and f.BoundBox.YLength < TOL
                     and abs(f.CenterOfMass.y - wall_y - foot_height) < TOL]
    assert len(support_faces) == 4, "Four coplanar foot pads are required"
    assert all(abs(f.Area - math.pi * (foot_radius-edge_radius)**2) < TOL
               for f in support_faces)
    pose = App.Placement(shell.Placement)
    shell.Shape = new_shell
    shell.Placement = pose

    for side, name in ((1, "ButtonPlungerPositive"), (-1, "ButtonPlungerNegative")):
        obj = doc.getObject(name)
        pose = App.Placement(obj.Placement)
        old = local_shape(obj)
        bb = old.BoundBox
        cx, cz = (bb.XMin + bb.XMax) / 2, (bb.ZMin + bb.ZMax) / 2
        equator = wall_y + projection - tip_radius
        center = App.Vector(cx, side * equator, cz)
        axis = App.Vector(0, side, 0)
        # The 3 mm hemisphere equator is recessed 0.5 mm behind the shell face.
        # Its circular tangent joins the existing 3 mm guiding stem smoothly.
        keep = Part.makeBox(100, 100 + equator, 100,
                            App.Vector(-50, -100 if side > 0 else -equator, -20))
        inner = old.common(keep).removeSplitter()
        dome = Part.makeSphere(tip_radius, center, axis, 0, 90, 360)
        assert abs(dome.Volume - 2 * math.pi * tip_radius**3 / 3) < TOL
        result = inner.fuse(dome).removeSplitter()
        assert result.isValid() and len(result.Solids) == 1
        assert result.cut(old).Volume < TOL, "Tip must fit in the previous stem"
        assert inner.cut(result).Volume < TOL, "Inner collar changed"
        assert result.common(keep).cut(inner).Volume < TOL
        tip_y = result.BoundBox.YMax if side > 0 else -result.BoundBox.YMin
        assert abs(tip_y - wall_y - projection) < TOL
        spherical = [f for f in result.Faces if isinstance(f.Surface, Part.Sphere)]
        assert len(spherical) == 1 and abs(spherical[0].Surface.Radius - tip_radius) < TOL
        obj.Shape = result
        obj.Placement = pose
        print("BUTTON_HEMISPHERE", name, "R", tip_radius, "PROJECTION", projection,
              "UNCHANGED_CONTACT_AND_COLLAR", True, flush=True)
    p.ButtonOuterProjection = projection
    for name, value in (("ButtonTipSphereRadius", tip_radius),
                        ("ButtonTipEquatorRecess", tip_radius - projection),
                        ("HorizontalFootHeight", foot_height),
                        ("HorizontalFootDiameter", foot_radius * 2),
                        ("HorizontalFootEdgeRadius", edge_radius),
                        ("HorizontalFootCenterX", 15.0),
                        ("HorizontalFootRearCenterZ", foot_zs[0]),
                        ("HorizontalFootFrontCenterZ", foot_zs[1]),
                        ("HorizontalSupportPlaneY", wall_y + foot_height),
                        ("HorizontalButtonGroundClearance", foot_height - projection),
                        ("OverallWidthIncludingFeet", p.OuterWidth.Value + foot_height)):
        p.addProperty("App::PropertyLength", name, "Horizontal placement")
        setattr(p, name, value)
    p.addProperty("App::PropertyInteger", "HorizontalFootCount", "Horizontal placement")
    p.HorizontalFootCount = 4
    p.addProperty("App::PropertyString", "HorizontalFootSide", "Horizontal placement")
    p.HorizontalFootSide = "+Y 长侧壁，屏幕朝前且 C 口朝左时的下侧"
    p.Layout += ("横放时C口朝左：+Y长侧壁增加4个一体式Ø4mm圆脚，外伸1.5mm，"
                 "脚端边缘R0.35圆角；两侧按钮保留Ø3导向轴和原内侧圆台，"
                 "外端改为R1.5半球，赤道收进壳面0.5mm，最高点外露1mm，离桌面0.5mm。")
    doc.recompute()
    print("FOUR_FEET", foot_centers, "SUPPORT_Y", wall_y + foot_height,
          "BUTTON_CLEARANCE", foot_height - projection, "ADDED_MM3", added.Volume,
          flush=True)


def extend_hemispherical_buttons(doc, projection=1.0):
    """Lengthen only the outer stem, leaving the internal contact stationary."""
    p = doc.DesignParameters
    previous = p.ButtonOuterProjection.Value
    delta = projection - previous
    assert .5-TOL <= previous < projection <= 1.5+TOL
    assert abs(delta-.5) < TOL, "Only the requested 0.5 mm outer extension is supported"
    wall = p.OuterWidth.Value / 2
    for side, name in ((1, "ButtonPlungerPositive"), (-1, "ButtonPlungerNegative")):
        obj = doc.getObject(name)
        old = obj.Shape
        pose = App.Placement(obj.Placement)
        spheres = [f for f in old.Faces if isinstance(f.Surface, Part.Sphere)]
        assert len(spheres) == 1
        radius = spheres[0].Surface.Radius
        center = spheres[0].Surface.Center
        assert abs(radius-1.5) < TOL
        assert abs(side*center.y + radius - wall - previous) < TOL
        keep = Part.makeBox(100, 100+abs(center.y), 200,
                            App.Vector(-50, -100 if side > 0 else center.y, -100))
        inner = old.common(keep).removeSplitter()
        axis = App.Vector(0, side, 0)
        cylinder = Part.makeCylinder(radius, delta, center, axis)
        new_center = center + axis*delta
        dome = Part.makeSphere(radius, new_center, axis, 0, 90, 360)
        result = inner.multiFuse([cylinder, dome]).removeSplitter()
        assert result.isValid() and len(result.Solids) == 1
        assert old.cut(result).Volume < TOL
        assert abs(result.Volume-old.Volume-math.pi*radius**2*delta) < TOL
        check_inner = result.common(keep)
        assert check_inner.cut(inner).Volume < TOL and inner.cut(check_inner).Volume < TOL
        tip = result.BoundBox.YMax if side > 0 else -result.BoundBox.YMin
        assert abs(tip-wall-projection) < TOL
        for bound in ("XMin", "XMax", "ZMin", "ZMax"):
            assert abs(getattr(result.BoundBox, bound)-getattr(old.BoundBox, bound)) < TOL
        assert result.Placement.toMatrix().A == App.Placement().toMatrix().A
        local = result.transformed(pose.inverse().toMatrix(), copy=True)
        obj.Shape = local
        obj.Placement = pose
        assert obj.Placement.toMatrix().A == pose.toMatrix().A, "Native placement changed"
        for bound in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax"):
            assert abs(getattr(obj.Shape.BoundBox, bound)-getattr(result.BoundBox, bound)) < TOL
        assert obj.Shape.common(doc.RearShell.Shape).Volume < TOL
        assert obj.Shape.common(doc.ESP32BoardAssembly.Shape).Volume < TOL
        for travel in (.3, .5, .8):
            moved = obj.Shape.copy()
            moved.translate(App.Vector(0, -side*travel, 0))
            assert moved.common(doc.RearShell.Shape).Volume < TOL, (name, travel)
        print("BUTTON_EXTENDED_VERIFIED", name, "PROJECTION", tip-wall,
              "GUIDE_TRAVEL_CLEAR", .8, "INNER_CONTACT_UNCHANGED", True, flush=True)
    p.ButtonOuterProjection = projection
    p.ButtonTipEquatorRecess = p.ButtonTipSphereRadius.Value - projection
    p.HorizontalButtonGroundClearance = p.HorizontalFootHeight.Value - projection
    p.Layout += (" 按钮更新：R1.5半球最高点外露%gmm，半球赤道内缩%gmm；"
                 "侧脚高度%gmm，按钮离支撑平面%gmm。" % (
                     projection, p.ButtonTipEquatorRecess.Value,
                     p.HorizontalFootHeight.Value, p.HorizontalButtonGroundClearance.Value))
    doc.recompute()
