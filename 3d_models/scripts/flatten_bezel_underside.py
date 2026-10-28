"""Remove only the sub-micron lip below the front cover's seating plane."""
import FreeCAD as App
import Part


def flatten_shape(old):
    downward = [f for f in old.Faces if isinstance(f.Surface, Part.Plane)
                and f.BoundBox.ZLength < 1e-7 and f.normalAt(0, 0).z < -.99]
    seating = max(downward, key=lambda f: f.Area)
    z_base = seating.CenterOfMass.z
    thickness = z_base - old.BoundBox.ZMin
    assert 1e-5 < thickness < .001, ("Unexpected lip thickness", thickness)
    b = old.BoundBox
    tool = Part.makeBox(b.XLength + 2, b.YLength + 2, 1 + thickness,
                        App.Vector(b.XMin - 1, b.YMin - 1, b.ZMin - 1))
    result = old.cut(tool).removeSplitter()
    assert result.isValid() and len(result.Solids) == 1
    # Default B-spline bounding boxes may retain the untrimmed surface poles.
    tight = result.optimalBoundingBox(False, False)
    assert abs(tight.ZMin - z_base) < 1e-6, (
        "Boolean trim did not land on the seating plane", tight.ZMin, z_base)
    flat = [f for f in result.Faces if isinstance(f.Surface, Part.Plane)
            and f.BoundBox.ZLength < 1e-7 and f.normalAt(0, 0).z < -.99]
    assert len(flat) == 1, ("Underside must be one planar face", len(flat))
    assert abs(flat[0].CenterOfMass.z - z_base) < 1e-7
    assert result.cut(old).Volume < 1e-7
    removed = old.cut(result)
    assert removed.Volume < .2
    assert removed.optimalBoundingBox(False, False).ZMax <= z_base + 1e-6
    assert abs(result.BoundBox.ZMax - b.ZMax) < 1e-7
    info = dict(underside_z=z_base, removed_height=thickness,
                removed_volume=removed.Volume, underside_area=flat[0].Area,
                old_volume=old.Volume, new_volume=result.Volume)
    return result, info


def update_parameters(doc, info):
    p = doc.DesignParameters
    for name, value, kind in (
        ("ScreenWindowPlanarUndersideRevision", 1, "Integer"),
        ("ScreenWindowMicroLipHeight", 0.0, "Length"),
        ("ScreenWindowRemovedMicroLipHeight", info["removed_height"], "Length"),
        ("ScreenWindowLowerEdgeZ", info["underside_z"], "Length"),
    ):
        if name not in p.PropertiesList:
            p.addProperty("App::Property"+kind, name, "Screen window")
        setattr(p, name, value)
    p.ScreenToLidGap = info["removed_height"]
    p.ScreenWindowChamferDepth = 3.0
    p.Layout += ("已去掉屏幕窗下方约0.000479mm微小补偿台阶；"
                 "上盖内侧合并为同一平面，保留外侧倒角、外轮廓和螺丝孔；"
                 "与屏幕玻璃保留不足0.001mm的名义间隙。")
    doc.FrontBezel.Label = "前盖（内侧同平面，无微小环形台阶）"


def apply_planar_underside(doc):
    assert "ScreenWindowPlanarUndersideRevision" not in doc.DesignParameters.PropertiesList
    obj = doc.FrontBezel
    result, info = flatten_shape(obj.Shape)
    pose = App.Placement(obj.Placement)
    obj.Shape = result.transformed(pose.inverse().toMatrix(), copy=True)
    obj.Placement = pose
    update_parameters(doc, info)
    doc.recompute()
    return info


def export_planar_bezel(obj, path):
    import Mesh
    import MeshPart
    mesh = MeshPart.meshFromShape(Shape=obj.Shape.copy(), LinearDeflection=.001,
                                 AngularDeflection=.03, Relative=False)
    assert mesh.isSolid() and mesh.countComponents() == 1
    assert not mesh.hasNonManifolds() and mesh.countNonUniformOrientedFacets() == 0
    assert not mesh.hasSelfIntersections()
    mesh.write(str(path))
    check = Mesh.Mesh(str(path))
    assert check.isSolid() and check.countComponents() == 1
    assert not check.hasNonManifolds() and check.countNonUniformOrientedFacets() == 0
    assert not check.hasSelfIntersections()
    return check
