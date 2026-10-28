"""Set the four ESP32 pedestal radii to 1.6 mm, preserving all other geometry."""

import os

import FreeCAD as App
import Part
import Mesh


OUT_DIR = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
MODEL_NAMES = (
    "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
    "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd",
)
PCB_MOUNTS = ((-16.814, -6.640), (-16.814, 6.640),
              (15.186, -8.160), (15.186, 8.160))
DECK_Z = 13.5
NEW_RADIUS = 1.6


def local_shape(obj):
    return obj.Shape.transformed(obj.Placement.inverse().toMatrix(), copy=True)


pending = []


for model_name in MODEL_NAMES:
    doc = App.openDocument(os.path.join(OUT_DIR, model_name))
    shell = doc.RearShell
    params = doc.DesignParameters
    old_radius = params.PCBBossDiameter.Value / 2.0
    deck_top = DECK_Z + params.InterLayerDeckThickness.Value
    contact_z = params.PCBMountContactHeight.Value
    boss_height = contact_z - deck_top
    slot_bottom_z = min(10.5, DECK_Z) - 0.5
    slot_top_z = max(params.BoardLayerStart.Value, contact_z) + 0.5
    slot_length = params.HeaderSlotLength.Value
    slot_width = params.HeaderSlotWidth.Value
    slot_cutters = [
        Part.makeBox(
            slot_length, slot_width, slot_top_z - slot_bottom_z,
            App.Vector(-3.889 - slot_length / 2.0, y - slot_width / 2.0, slot_bottom_z),
        )
        for y in (-params.HeaderRowSpacing.Value / 2.0, params.HeaderRowSpacing.Value / 2.0)
    ]
    hole_radius = params.PCBMountThroughHoleDiameter.Value / 2.0
    shell_pose = App.Placement(shell.Placement)
    before_shape = local_shape(shell)
    assert abs(old_radius - 2.0) < 1e-6, old_radius
    assert abs(hole_radius - 1.1) < 1e-6, hole_radius
    other_shapes = {
        obj.Name: (obj.Shape, obj.Placement.toMatrix().A)
        for obj in doc.Objects
        if "Shape" in obj.PropertiesList and obj.Name != "RearShell"
    }

    # The cover columns were fused after the PCB bosses. Preserve those
    # columns where their cylinders overlap the old PCB pedestals.
    cover_columns = Part.makeCompound([
        Part.makeCylinder(
            params.SideBodyColumnDiameter.Value / 2.0,
            boss_height,
            App.Vector(x, y, deck_top),
        )
        for x in (-params.SideBodyColumnCenterX.Value, params.SideBodyColumnCenterX.Value)
        for y in (-params.SideBodyColumnCenterY.Value, params.SideBodyColumnCenterY.Value)
    ])
    after_shape = before_shape.copy()
    annular_cutters = []
    for x, y in PCB_MOUNTS:
        base = App.Vector(x, y, deck_top)
        outer = Part.makeCylinder(old_radius + 0.01, boss_height, base)
        inner = Part.makeCylinder(NEW_RADIUS, boss_height, base)
        annular_cut = outer.cut(inner).cut(cover_columns)
        annular_cutters.append(annular_cut)
        after_shape = after_shape.cut(annular_cut)
    slot_residual_before = [after_shape.common(cut).Volume for cut in slot_cutters]
    for cut in slot_cutters:
        after_shape = after_shape.cut(cut)
    after_shape = after_shape.removeSplitter()
    if not after_shape.isValid() or len(after_shape.Solids) != 1:
        raise RuntimeError("缩小 ESP32 凸台后侧壁几何无效")
    if after_shape.cut(before_shape).Volume > 1e-7:
        raise RuntimeError("缩小凸台时意外增加材料")
    if before_shape.cut(after_shape).cut(Part.makeCompound(annular_cutters)).Volume > 1e-7:
        raise RuntimeError("修改范围超出了四个凸台外圈")
    if before_shape.common(cover_columns).cut(after_shape).Volume > 1e-7:
        raise RuntimeError("上下盖螺丝柱发生意外变化")
    slot_residual_after = [after_shape.common(cut).Volume for cut in slot_cutters]
    if any(volume > 1e-7 for volume in slot_residual_after):
        raise RuntimeError("长条孔未完全切穿凸台")

    for x, y in PCB_MOUNTS:
        side_faces = [
            face for face in after_shape.Faces
            if isinstance(face.Surface, Part.Cylinder)
            and abs(face.Surface.Radius - NEW_RADIUS) < 1e-6
            and abs(face.Surface.Center.x - x) < 1e-6
            and abs(face.Surface.Center.y - y) < 1e-6
            and abs(face.BoundBox.ZMin - deck_top) < 1e-6
            and abs(face.BoundBox.ZMax - contact_z) < 1e-6
        ]
        if not side_faces:
            raise RuntimeError("凸台直径或接触高度不符")
        for face in after_shape.Faces:
            if isinstance(face.Surface, Part.Cylinder):
                surface = face.Surface
                if (abs(surface.Center.x-x)<1e-6 and abs(surface.Center.y-y)<1e-6
                        and abs(surface.Radius-old_radius)<1e-6
                        and face.BoundBox.ZMax > deck_top+1e-6):
                    raise RuntimeError("凸台残留旧直径的外表面")
        hole = Part.makeCylinder(
            hole_radius - 0.001,
            contact_z - DECK_Z + 0.6,
            App.Vector(x, y, DECK_Z - 0.3),
        )
        if after_shape.common(hole).Volume > 1e-7:
            raise RuntimeError("M2 贯穿孔被堵塞")

    shell.Shape = after_shape
    shell.Placement = shell_pose
    params.PCBBossDiameter = NEW_RADIUS * 2.0
    if "PCBBossRadius" not in params.PropertiesList:
        params.addProperty("App::PropertyLength", "PCBBossRadius", "Dimensions")
    params.PCBBossRadius = NEW_RADIUS
    params.Layout += "四个ESP32固定凸台外半径1.6mm（直径3.2mm），M2贯穿孔直径2.2mm、孔位及接触高度保持不变。"
    for name, value in (("HeaderSlotCutBottomZ", slot_bottom_z),
                        ("HeaderSlotCutTopZ", slot_top_z)):
        if name not in params.PropertiesList:
            params.addProperty("App::PropertyLength", name, "Dimensions")
        setattr(params, name, value)
    doc.recompute()
    for name, (shape_before, placement_before) in other_shapes.items():
        obj = doc.getObject(name)
        if not obj.Shape.isSame(shape_before) or obj.Placement.toMatrix().A != placement_before:
            raise RuntimeError("其他零件发生意外变化：" + name)
    print("VALIDATED", model_name, flush=True)
    print("PCB_BOSS_DIAMETER_MM", params.PCBBossDiameter.Value)
    print("M2_THROUGH_HOLE_MM", hole_radius * 2.0)
    print("PCB_CONTACT_Z_MM", contact_z)
    print("HEADER_SLOT_CUT_Z_MM", slot_bottom_z, slot_top_z)
    print("SLOT_RESIDUAL_BEFORE_RECUT_MM3", slot_residual_before)
    print("SLOT_RESIDUAL_AFTER_RECUT_MM3", slot_residual_after)
    print("REMOVED_VOLUME_MM3", before_shape.Volume - after_shape.Volume)
    print("VERIFIED_FOUR_BOSSES_AND_HOLES", True)
    print("UNCHANGED_OTHER_SHAPES", len(other_shapes))
    pending.append(doc)

first = local_shape(pending[0].RearShell)
second = local_shape(pending[1].RearShell)
assert first.cut(second).Volume < 1e-7 and second.cut(first).Volume < 1e-7
for doc in pending:
    doc.save()
stl = os.path.join(OUT_DIR,"ESP32-S3-LCD-1.47B_紧凑双层外壳_后壳.stl")
Part.export([pending[0].RearShell], stl)
mesh = Mesh.Mesh(stl)
assert mesh.isSolid()
print("STL_CLOSED",mesh.CountFacets,flush=True)
for doc in pending:
    path = doc.FileName
    App.closeDocument(doc.Name)
    check = App.openDocument(path)
    assert check.RearShell.Shape.isValid() and len(check.RearShell.Shape.Solids) == 1
    assert abs(check.DesignParameters.PCBBossDiameter.Value - 3.2) < 1e-6
    print("SAVED_REOPENED",path,flush=True)
    App.closeDocument(check.Name)
