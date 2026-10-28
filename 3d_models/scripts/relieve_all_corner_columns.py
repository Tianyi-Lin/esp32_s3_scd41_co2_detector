"""Mirror the existing vertical 45-degree column flats into both cavities."""
import math
import FreeCAD as App
import Part

TOL = 1e-6


def flat_faces(shape, center, normal, offset, z0, z1):
    return [f for f in shape.Faces
            if isinstance(f.Surface, Part.Plane)
            and abs(abs(f.normalAt(0, 0).dot(normal))-1) < 1e-8
            and abs((f.CenterOfMass-center).dot(normal)-offset) < TOL
            and abs(f.BoundBox.ZMin-z0) < TOL
            and abs(f.BoundBox.ZMax-z1) < TOL]


def apply_all_corner_flats(doc):
    p = doc.DesignParameters
    obj = doc.RearShell
    before = obj.Shape.copy()
    pose = App.Placement(obj.Placement)
    assert pose.toMatrix().A == App.Placement().toMatrix().A
    radius = p.SideBodyColumnDiameter.Value/2
    hole_r = p.SideBodyTapHoleDiameter.Value/2
    offset = p.PCBColumnReliefPlaneOffset.Value
    assert abs(radius-3.55) < TOL and abs(hole_r-1.15) < TOL
    assert abs(offset-2.7818530470919226) < TOL
    assert not ("AllCornerColumnFlatRevision" in p.PropertiesList)
    zmin, zmax = before.BoundBox.ZMin, before.BoundBox.ZMax
    deck0, deck1 = p.InterLayerDeckBottomZ.Value, p.InterLayerDeckTopZ.Value
    cx, cy = p.SideBodyColumnCenterX.Value, p.SideBodyColumnCenterY.Value
    centers = [(x, y) for x in (-cx, cx) for y in (-cy, cy)]
    tools, records = [], []
    for x, y in centers:
        center = App.Vector(x, y, 0)
        inward = App.Vector(-math.copysign(1, x), -math.copysign(1, y), 0)
        inward.normalize()
        angle = math.degrees(math.atan2(inward.y, inward.x))
        for layer, z0, z1 in (("lower", zmin, deck0), ("upper", deck1, zmax)):
            existing = flat_faces(before, center, inward, offset, z0, z1)
            assert len(existing) == (1 if x < 0 and layer == "upper" else 0)
            column = Part.makeCylinder(radius, z1-z0, App.Vector(x, y, z0))
            halfspace = Part.makeBox(20, 40, z1-z0,
                                     App.Vector(offset, -20, z0))
            halfspace.rotate(App.Vector(), App.Vector(0, 0, 1), angle)
            halfspace.translate(center)
            tool = column.common(halfspace)
            assert tool.isValid() and len(tool.Solids) == 1
            if existing:
                assert before.common(tool).Volume < TOL
            else:
                assert abs(before.common(tool).Volume-tool.Volume) < TOL
            bore = Part.makeCylinder(hole_r, z1-z0, App.Vector(x, y, z0))
            nominal = Part.makeCylinder(1.25, z1-z0, App.Vector(x, y, z0))
            wall = bore.distToShape(tool)[0]
            thread_wall = nominal.distToShape(tool)[0]
            assert abs(wall-(offset-hole_r)) < TOL
            assert thread_wall >= 1.5-TOL
            tools.append(tool)
            records.append((x, y, layer, z0, z1, center, inward, wall, thread_wall))
    cutter = Part.makeCompound(tools)
    result = before.cut(cutter).removeSplitter()
    assert result.isValid() and len(result.Solids) == 1
    assert result.cut(before).Volume < TOL
    assert before.cut(result).cut(cutter).Volume < TOL
    assert result.common(cutter).Volume < TOL
    # Six new portions: four below the deck and the two remaining above it.
    cap_area = radius**2*math.acos(offset/radius)-offset*math.sqrt(radius**2-offset**2)
    expected_removed = cap_area*(4*(deck0-zmin)+2*(zmax-deck1))
    assert abs(before.Volume-result.Volume-expected_removed) < TOL
    deck = Part.makeBox(100, 100, deck1-deck0, App.Vector(-50, -50, deck0))
    assert before.common(deck).cut(result).Volume < TOL
    assert result.common(deck).cut(before).Volume < TOL
    for attr in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax"):
        assert abs(getattr(result.BoundBox, attr)-getattr(before.BoundBox, attr)) < TOL
    for x, y, layer, z0, z1, center, inward, wall, thread_wall in records:
        faces = flat_faces(result, center, inward, offset, z0, z1)
        assert len(faces) == 1, (x, y, layer, len(faces))
        assert abs(faces[0].Area-2*math.sqrt(radius**2-offset**2)*(z1-z0)) < TOL
        print("ONE_45_DEG_FLAT", x, y, layer, "Z", z0, z1,
              "HOLE_WALL", wall, "NOMINAL_M25_WALL", thread_wall, flush=True)
    # All circular bore walls and the small ESP32 mounting bosses are untouched.
    def bore_records(shape):
        return sorted((round(f.Surface.Radius, 6), round(f.Surface.Center.x, 6),
                       round(f.Surface.Center.y, 6), round(f.BoundBox.ZMin, 6),
                       round(f.BoundBox.ZMax, 6), round(f.Area, 6))
                      for f in shape.Faces if isinstance(f.Surface, Part.Cylinder)
                      and abs(f.Surface.Axis.z) > .999999
                      and f.Surface.Radius < 2)
    assert bore_records(result) == bore_records(before)
    obj.Shape = result
    obj.Placement = pose
    for name, value in (("AllCornerColumnFlatDepth", radius-offset),
                        ("AllCornerColumnFlatPlaneOffset", offset),
                        ("AllCornerColumnFlatMinHoleWall", offset-hole_r),
                        ("AllCornerColumnFlatMinNominalM25Wall", offset-1.25)):
        if name not in p.PropertiesList:
            p.addProperty("App::PropertyLength", name, "Dimensions")
        setattr(p, name, value)
    p.addProperty("App::PropertyInteger", "AllCornerColumnFlatRevision", "Dimensions")
    p.AllCornerColumnFlatRevision = 1
    p.addProperty("App::PropertyInteger", "AllCornerColumnFlatCount", "Dimensions")
    p.AllCornerColumnFlatCount = 8
    p.addProperty("App::PropertyString", "AllCornerColumnFlatScope", "Documentation")
    p.AllCornerColumnFlatScope = (
        "中间外壳四角外侧螺丝柱，朝内一侧在上下两个腔体各作竖直45°单平面切削；"
        "复用原左侧上层两柱的切平面偏移量，不改中层板厚度及连接。")
    p.Layout += (
        "四角外柱上下两层共8段均采用相同45°竖直单平面切削，"
        "径向切深%.6fmm；Ø2.3通孔至切面最薄%.6fmm，"
        "按M2.5公称外径计算仍保留%.6fmm。中层板及ESP32小凸台保持不变。"
        % (radius-offset, offset-hole_r, offset-1.25))
    doc.recompute()
    print("ALL_CORNER_FLATS_VALID", doc.Label, "REMOVED_VOLUME", before.Volume-result.Volume,
          "VOLUME", result.Volume, "DECK_UNCHANGED", True, flush=True)
    return result
