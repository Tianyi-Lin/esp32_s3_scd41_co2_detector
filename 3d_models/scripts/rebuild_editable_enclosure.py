"""Rebuild the three current parts using native, constrained FreeCAD features.

No source CAD, STL or STEP is overwritten. No FeaturePython/proxy is required
to reopen or edit the resulting documents.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

import FreeCAD as App
import Part
import Sketcher

ROOT = Path("/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)")
SOURCE = ROOT / "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd"
RECOVERY = Path("/Users/bytedance/Documents/New project/.cad-recovery")
STAGE = Path(tempfile.mkdtemp(prefix="editable-parametric-", dir=RECOVERY))
ZSHIFT = 4.250478785792438
ZTOP = 25 + ZSHIFT


class E:
    def __init__(self, value, expression=None):
        self.v = float(value)
        self.s = expression if expression is not None else "%.16g mm" % value

    def __add__(self, other):
        other = e(other)
        return E(self.v + other.v, "(%s + %s)" % (self.s, other.s))

    __radd__ = __add__

    def __neg__(self):
        return E(-self.v, "(-%s)" % self.s)

    def __sub__(self, other):
        return self + -e(other)

    def __rsub__(self, other):
        return e(other) - self

    def __mul__(self, scalar):
        return E(self.v * scalar, "(%s * %.16g)" % (self.s, scalar))

    __rmul__ = __mul__

    def __truediv__(self, scalar):
        return self * (1.0 / scalar)


def e(value):
    return value if isinstance(value, E) else E(value)


def vec(point):
    return App.Vector(e(point[0]).v, e(point[1]).v, 0)


class Model:
    def __init__(self, name, label):
        self.doc = App.newDocument(name)
        self.doc.Label = label
        self.sheet = self.doc.addObject("Spreadsheet::Sheet", "Parameters")
        self.sheet.Label = "尺寸参数（双击，修改 B 列）"
        self.sheet.set("A1", "参数名称")
        self.sheet.set("B1", "尺寸 / 公式")
        self.sheet.set("C1", "说明")
        self.sheet.setStyle("A1:C1", "bold", "add")
        self.sheet.setBackground("A1:C1", (0.78, 0.87, 0.98))
        self.sheet.setColumnWidth("A", 240)
        self.sheet.setColumnWidth("B", 170)
        self.sheet.setColumnWidth("C", 400)
        self.params = {}
        self.cells = {}
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        self.body.Label = label + "（可编辑实体）"
        self.tip = None
        self.sketches = []
        self.features = []
        self.doc.addObject("App::DocumentObjectGroup", "ReadMe").Label = (
            "说明：尺寸表驱动草图；原装配坐标保留；修改后需重新检查配合"
        )

    def param(self, alias, label, value, note="", formula=None):
        row = len(self.params) + 2
        self.sheet.set("A%d" % row, label)
        content = ("=" if value < 0 else "") + "%.16g mm" % value
        self.sheet.set("B%d" % row, formula if formula else content)
        self.sheet.setAlias("B%d" % row, alias)
        self.sheet.set("C%d" % row, note)
        self.sheet.setBackground("B%d" % row,
                                 (0.94, 0.94, 0.94) if formula else (1.0, 0.97, 0.80))
        self.params[alias] = E(value, "Parameters." + alias)
        self.cells[alias] = "B%d" % row
        return self.params[alias]

    def p(self, alias):
        return self.params[alias]

    def sketch(self, name, label, z=0, rotation=None, x=0, y=0):
        self.doc.recompute()
        sk = self.body.newObject("Sketcher::SketchObject", name)
        sk.Label = label
        sk.Placement = App.Placement(App.Vector(e(x).v, e(y).v, e(z).v),
                                     rotation or App.Rotation())
        for axis, value in (("x", x), ("y", y), ("z", z)):
            sk.setExpression("Placement.Base." + axis, e(value).s)
        self.sketches.append(sk)
        return sk

    def dimension(self, sk, constraint, value):
        idx = sk.addConstraint(constraint)
        sk.setExpression("Constraints[%d]" % idx, e(value).s)
        return idx

    def point(self, sk, pt):
        ix = sk.addGeometry(Part.Point(vec(pt)), True)
        for axis, value in (("DistanceX", pt[0]), ("DistanceY", pt[1])):
            self.dimension(sk, Sketcher.Constraint(axis, ix, 1, e(value).v), value)
        return ix

    def line(self, sk, pa, pb, ia, ib):
        ix = sk.addGeometry(Part.LineSegment(vec(pa), vec(pb)), False)
        sk.addConstraint(Sketcher.Constraint("Coincident", ix, 1, ia, 1))
        sk.addConstraint(Sketcher.Constraint("Coincident", ix, 2, ib, 1))
        return ix

    def arc(self, sk, pa, pm, pb, ia, ib, radius):
        ix = sk.addGeometry(Part.Arc(vec(pa), vec(pm), vec(pb)), False)
        sk.addConstraint(Sketcher.Constraint("Coincident", ix, 1, ia, 1))
        sk.addConstraint(Sketcher.Constraint("Coincident", ix, 2, ib, 1))
        self.dimension(sk, Sketcher.Constraint("Radius", ix, e(radius).v), radius)
        return ix

    def polygon(self, sk, points):
        ids = [self.point(sk, pt) for pt in points]
        for i, pt in enumerate(points):
            j = (i + 1) % len(points)
            self.line(sk, pt, points[j], ids[i], ids[j])

    def rect(self, sk, width, height, cx=0, cy=0):
        w, h, x, y = map(e, (width, height, cx, cy))
        self.polygon(sk, [(x-w/2, y-h/2), (x+w/2, y-h/2),
                          (x+w/2, y+h/2), (x-w/2, y+h/2)])

    def rounded(self, sk, width, height, radius, cx=0, cy=0):
        w, h, r, x, y = map(e, (width, height, radius, cx, cy))
        points = [(x-w/2+r, y-h/2), (x+w/2-r, y-h/2),
                  (x+w/2, y-h/2+r), (x+w/2, y+h/2-r),
                  (x+w/2-r, y+h/2), (x-w/2+r, y+h/2),
                  (x-w/2, y+h/2-r), (x-w/2, y-h/2+r)]
        ids = [self.point(sk, pt) for pt in points]
        for i in (0, 2, 4, 6):
            self.line(sk, points[i], points[i+1], ids[i], ids[i+1])
        centers = [(x+w/2-r, y-h/2+r), (x+w/2-r, y+h/2-r),
                   (x-w/2+r, y+h/2-r), (x-w/2+r, y-h/2+r)]
        for i, (cx2, cy2), angle in zip((1, 3, 5, 7), centers, (-45, 45, 135, 225)):
            j = (i + 1) % 8
            mid = (cx2+r*math.cos(math.radians(angle)),
                   cy2+r*math.sin(math.radians(angle)))
            self.arc(sk, points[i], mid, points[j], ids[i], ids[j], r)

    def capsule(self, sk, length, height, cx=0, cy=0):
        w, h, x, y = map(e, (length, height, cx, cy))
        r, a = h/2, (w-h)/2
        points = [(x-a, y-r), (x+a, y-r), (x+a+r, y),
                  (x+a, y+r), (x-a, y+r), (x-a-r, y)]
        ids = [self.point(sk, pt) for pt in points]
        for i in (0, 3):
            self.line(sk, points[i], points[i+1], ids[i], ids[i+1])
        for i, center, angle in ((1, (x+a, y), -45), (2, (x+a, y), 45),
                                  (4, (x-a, y), 135), (5, (x-a, y), 225)):
            j = (i+1) % 6
            mid = (center[0]+r*math.cos(math.radians(angle)),
                   center[1]+r*math.sin(math.radians(angle)))
            self.arc(sk, points[i], mid, points[j], ids[i], ids[j], r)

    def circles(self, sk, centers, diameter):
        radius = e(diameter)/2
        for center in centers:
            ix = sk.addGeometry(Part.Circle(vec(center), App.Vector(0, 0, 1),
                                            radius.v), False)
            for axis, value in (("DistanceX", center[0]), ("DistanceY", center[1])):
                self.dimension(sk, Sketcher.Constraint(axis, ix, 3, e(value).v), value)
            self.dimension(sk, Sketcher.Constraint("Diameter", ix, radius.v*2),
                           diameter)

    def check_sketch(self, sk):
        self.doc.recompute()
        assert sk.FullyConstrained, (sk.Name, "Not fully constrained", sk.SolverMessages
                                    if "SolverMessages" in sk.PropertiesList else sk.State)
        assert "Invalid" not in sk.State, (sk.Name, sk.State)

    def finish(self, feature, sketches):
        self.doc.recompute()
        assert not feature.Shape.isNull(), (feature.Name, feature.State)
        assert feature.Shape.isValid() and len(feature.Shape.Solids) == 1, (
            feature.Name, feature.State, len(feature.Shape.Solids))
        if self.tip:
            self.tip.Visibility = False
        for sk in sketches:
            sk.Visibility = False
        feature.Visibility = True
        self.tip = feature
        self.body.Tip = feature
        self.features.append(feature)
        print("FEATURE", self.doc.Name, feature.Name,
              round(feature.Shape.Volume, 8), len(feature.Shape.Faces), flush=True)
        return feature

    def extrude(self, sk, name, label, length, pocket=False, reversed=False,
                through=False):
        self.check_sketch(sk)
        f = self.body.newObject("PartDesign::Pocket" if pocket else "PartDesign::Pad",
                                name)
        f.Label = label
        f.Profile = sk
        f.Length = e(length).v
        f.setExpression("Length", e(length).s)
        f.Reversed = reversed
        if through:
            f.Type = 1
        f.Refine = True
        return self.finish(f, [sk])

    def fillet(self, name, label, indices, radius):
        f = self.body.newObject("PartDesign::Fillet", name)
        f.Label = label
        f.Base = (self.tip, ["Edge%d" % i for i in indices])
        f.Radius = e(radius).v
        f.setExpression("Radius", e(radius).s)
        f.Refine = True
        return self.finish(f, [])


def shared(m):
    for alias, label, value, note in (
        ("OuterLength", "外轮廓长 X", 45.4, "三件独立文件；改变配合尺寸时三件需同步"),
        ("OuterWidth", "外轮廓宽 Y", 33.9, ""),
        ("OuterRadius", "外轮廓圆角半径", 4, "R，单位 mm"),
        ("CoverHoleX", "四角孔轴心 X 半间距", 18.86, "孔轴心为 ±X、±Y"),
        ("CoverHoleY", "四角孔轴心 Y 半间距", 12.82, ""),
    ):
        m.param(alias, label, value, note)


def cover_centers(m):
    return [(m.p("CoverHoleX")*sx, m.p("CoverHoleY")*sy)
            for sx in (-1, 1) for sy in (-1, 1)]


def outer_sketch(m, z=0):
    sk = m.sketch("OuterProfile", "01 外轮廓草图", z)
    m.rounded(sk, m.p("OuterLength"), m.p("OuterWidth"), m.p("OuterRadius"))
    return sk


def bottom():
    m = Model("EditableBottom", "下盖_参数化")
    shared(m)
    values = [
        ("Thickness", "底板厚度", 2),
        ("BossHeight", "CO2 支撑凸台高度", 1),
        ("BossDiameter", "CO2 支撑凸台直径", 5),
        ("SensorSpacingX", "CO2 孔距 X（短边）", 18),
        ("SensorSpacingY", "CO2 孔距 Y（长边）", 20),
        ("CoverHoleDiameter", "四角通孔直径", 2.9),
        ("SensorHoleDiameter", "CO2 通孔直径", 2.8),
        ("CounterboreDiameter", "八个沉孔直径", 5.1),
        ("CounterboreDepth", "沉孔深度（从底面向内）", 1.4),
        ("VentDiameter", "底部透气孔直径", 1.5),
        ("VentPitch", "透气孔中心间距", 3),
    ]
    for a, l, v in values:
        m.param(a, l, v)
    m.extrude(outer_sketch(m), "BasePad", "02 底板拉伸", m.p("Thickness"))
    sensors = [(m.p("SensorSpacingX")*sx/2, m.p("SensorSpacingY")*sy/2)
               for sx in (-1, 1) for sy in (-1, 1)]
    ztop = m.p("Thickness")+m.p("BossHeight")
    sk = m.sketch("SensorBossSketch", "03 CO2 凸台草图", m.p("Thickness"))
    m.circles(sk, sensors, m.p("BossDiameter"))
    m.extrude(sk, "SensorBossPad", "04 CO2 凸台拉伸", m.p("BossHeight"))
    for name, label, centers, diam in (
        ("CoverHoles", "四角通孔", cover_centers(m), m.p("CoverHoleDiameter")),
        ("SensorHoles", "CO2 通孔", sensors, m.p("SensorHoleDiameter")),
    ):
        sk = m.sketch(name+"Sketch", label+"草图", ztop)
        m.circles(sk, centers, diam)
        m.extrude(sk, name, label+"（贯穿）", ztop+1, pocket=True, through=True)
    sk = m.sketch("CounterboreSketch", "八个底面沉孔草图")
    m.circles(sk, cover_centers(m)+sensors, m.p("CounterboreDiameter"))
    m.extrude(sk, "Counterbores", "底面沉孔", m.p("CounterboreDepth"),
              pocket=True, reversed=True)
    sk = m.sketch("VentSketch", "37 个底部通气孔草图", ztop)
    vent_indices = [(x, y) for x in range(-3, 4) for y in range(-3, 4)
                    if all((x*3-mx)**2+(y*3-my)**2 >= 4.8**2
                           for mx in (-9, 9) for my in (-10, 10))]
    assert len(vent_indices) == 37
    m.circles(sk, [(m.p("VentPitch")*x, m.p("VentPitch")*y) for x, y in vent_indices],
              m.p("VentDiameter"))
    m.extrude(sk, "Vents", "底部通气孔（贯穿）", ztop+1, pocket=True, through=True)
    return m


def top():
    m = Model("EditableTop", "上盖_参数化")
    shared(m)
    values = [
        ("BaseZ", "装配底面 Z", ZTOP),
        ("Thickness", "上盖厚度", 3),
        ("WindowLength", "显示窗下口长度", 32.85),
        ("WindowWidth", "显示窗下口宽度", 17.89),
        ("WindowRadius", "显示窗下口圆角半径", 2.5),
        ("WindowX", "显示窗下口中心 X", -1.5675),
        ("TopWindowLength", "显示窗上口长度（圆角前）", 35.946),
        ("TopWindowWidth", "显示窗上口宽度（圆角前）", 20.6936),
        ("TopWindowRadius", "显示窗上口圆角半径", 3.833),
        ("TopWindowX", "显示窗上口中心 X", -.95045),
        ("ScreenOffset", "下口基准相对底面 Z", -.000479185792438),
        ("EdgeRadius", "显示窗外口过渡圆角 R", .4),
        ("HoleDiameter", "四角通孔直径", 2.9),
        ("CounterboreDiameter", "四角沉孔直径", 5.1),
        ("CounterboreDepth", "四角沉孔深度", 1.35),
    ]
    for a, l, v in values:
        m.param(a, l, v)
    m.extrude(outer_sketch(m, m.p("BaseZ")), "BasePad", "02 上盖拉伸", m.p("Thickness"))
    bottom_z = m.p("BaseZ")+m.p("ScreenOffset")
    top_z = m.p("BaseZ")+m.p("Thickness")
    profiles = []
    for i, (z, prefix) in enumerate(((bottom_z, "Window"), (top_z, "TopWindow"))):
        sk = m.sketch("WindowSection%d" % (i+1), "显示窗斜面截面 %d" % (i+1), z)
        m.rounded(sk, m.p(prefix+"Length"), m.p(prefix+"Width"),
                  m.p(prefix+"Radius"), m.p(prefix+"X"))
        m.check_sketch(sk)
        profiles.append(sk)
    f = m.body.newObject("PartDesign::SubtractiveLoft", "WindowLoft")
    f.Label = "显示窗贯穿斜面（两截面减料放样）"
    f.Profile = profiles[0]
    f.Sections = profiles[1:]
    f.Ruled = True
    f.Refine = True
    m.finish(f, profiles)
    edges = [i+1 for i, edge in enumerate(m.tip.Shape.Edges)
             if edge.BoundBox.ZLength < 1e-6
             and abs(edge.CenterOfMass.z-top_z.v) < 1e-6
             and edge.BoundBox.XLength < 37 and edge.BoundBox.YLength < 22
             and abs(edge.CenterOfMass.x) < 20 and abs(edge.CenterOfMass.y) < 12]
    assert len(edges) == 8, edges
    m.fillet("WindowFillet", "显示窗上口圆角", edges, m.p("EdgeRadius"))
    for name, label, diam, length, through in (
        ("ThroughHoles", "四角通孔", m.p("HoleDiameter"), m.p("Thickness")+1, True),
        ("Counterbores", "四角沉孔", m.p("CounterboreDiameter"),
         m.p("CounterboreDepth"), False),
    ):
        sk = m.sketch(name+"Sketch", label+"草图", top_z)
        m.circles(sk, cover_centers(m), diam)
        m.extrude(sk, name, label, length, pocket=True, through=through)
    return m


def corner_segments(m, sk):
    r, off = m.p("ColumnDiameter")/2, m.p("FlatOffset")
    chord = E(math.sqrt(r.v*r.v-off.v*off.v),
              "sqrt((Parameters.ColumnDiameter / 2)^2 - Parameters.FlatOffset^2)")
    for center in cover_centers(m):
        sx, sy = (1 if center[0].v > 0 else -1), (1 if center[1].v > 0 else -1)
        nx, ny = -sx/math.sqrt(2), -sy/math.sqrt(2)
        tx, ty = -ny, nx
        a = (center[0]+off*nx+chord*tx, center[1]+off*ny+chord*ty)
        b = (center[0]+off*nx-chord*tx, center[1]+off*ny-chord*ty)
        mid = (center[0]+r*nx, center[1]+r*ny)
        ia, ib = m.point(sk, a), m.point(sk, b)
        m.line(sk, a, b, ia, ib)
        m.arc(sk, b, mid, a, ib, ia, r)


def middle():
    m = Model("EditableMiddle", "中间外壳_参数化")
    shared(m)
    values = [
        ("BaseZ", "中间件底面 Z", 2.05),
        ("TopZ", "中间件顶面 Z", ZTOP),
        ("Wall", "侧壁厚度", 2.2),
        ("InnerRadius", "内腔圆角半径", 3),
        ("DeckZ", "中层板底面 Z", 13.5+ZSHIFT),
        ("DeckThickness", "中层板厚度", 2),
        ("DeckOverlap", "中层板与侧壁布尔搭接", .2),
        ("ColumnDiameter", "四角螺丝柱外径", 7.1),
        ("ColumnHoleDiameter", "四角柱贯穿孔直径", 2.3),
        ("FlatOffset", "45 度切面距孔轴心", 2.7818530470919226),
        ("BossHeight", "ESP32 小凸台高度", 1.936),
        ("BossDiameter", "ESP32 小凸台外径", 3.4),
        ("BossHoleDiameter", "ESP32 通孔直径", 2.2),
        ("BossLeftX", "ESP32 左孔列 X", -16.814),
        ("BossLeftY", "ESP32 左孔列 Y 半间距", 6.64),
        ("BossRightX", "ESP32 右孔列 X", 15.186),
        ("BossRightY", "ESP32 右孔列 Y 半间距", 8.16),
        ("OpeningLength", "中央开口长", 26),
        ("OpeningWidth", "中央开口宽", 15.48),
        ("HeaderPitch", "排针针距", 2.54),
        ("HeaderEndMargin", "槽端到最外针轴心", 1.3),
        ("HeaderWidth", "排针长槽宽", 2.6),
        ("HeaderX", "排针长槽中心 X", -3.889),
        ("HeaderY", "两排排针中心半间距", 8.89),
        ("HeaderCutBottom", "排针槽切削底面 Z", 10+ZSHIFT),
        ("HeaderCutTop", "排针槽切削顶面 Z", 17.936+ZSHIFT),
        ("USBLength", "Type-C 开口总长", 12),
        ("USBHeight", "Type-C 开口高度", 6.2),
        ("USBZ", "Type-C 开口中心 Z", 18.8+ZSHIFT),
        ("ButtonX", "按钮孔中心 X", 10.55),
        ("ButtonZ", "按钮孔中心 Z", 19.25+ZSHIFT),
        ("GuideDiameter", "按钮导向凸台外径", 6.2),
        ("GuideHeight", "按钮导向凸台高度", 1.5),
        ("ButtonHoleDiameter", "按钮滑动孔直径", 3.4),
        ("VentLength", "侧面通风槽总长", 14),
        ("VentHeight", "侧面通风槽高度", .9),
        ("VentPitch", "通风槽中心间距", 2.6),
        ("VentBottomZ", "最下通风槽底面 Z", 5),
        ("FootDiameter", "脚钉直径", 4),
        ("FootHeight", "脚钉突出侧壁高度", 1.5),
        ("FootRadius", "脚端过渡圆角 R", .35),
        ("FootX", "脚钉 X 半间距", 15),
        ("FootLowerZ", "下排脚钉中心 Z", 5.5),
        ("FootTopInset", "上排脚钉距顶面", 3),
    ]
    for a, l, v in values:
        note = "保持剩余孔壁厚度，不宜任意减小" if a == "FlatOffset" else ""
        m.param(a, l, v, note)
    m.param("HeaderLength", "排针槽长（9 针）", 22.92,
            "公式：8 × 针距 + 2 × 端距", "=HeaderPitch * 8 + HeaderEndMargin * 2")
    h = m.p("TopZ")-m.p("BaseZ")
    w = m.p("OuterLength")-m.p("Wall")*2
    d = m.p("OuterWidth")-m.p("Wall")*2
    dz = m.p("DeckZ")
    dt = m.p("DeckThickness")
    deck_top = dz+dt
    m.extrude(outer_sketch(m, m.p("BaseZ")), "OuterPad", "外形拉伸", h)
    sk = m.sketch("CavitySketch", "贯穿内腔草图", m.p("TopZ"))
    m.rounded(sk, w, d, m.p("InnerRadius"))
    m.extrude(sk, "CavityPocket", "贯穿内腔", h+1, pocket=True, through=True)
    sk = m.sketch("DeckSketch", "中层板草图", dz)
    ov = m.p("DeckOverlap")
    m.rounded(sk, w+ov*2, d+ov*2, m.p("InnerRadius")+ov)
    m.extrude(sk, "DeckPad", "中层板拉伸连接四壁", dt)
    sk = m.sketch("ColumnSketch", "四角螺丝柱草图", m.p("BaseZ"))
    m.circles(sk, cover_centers(m), m.p("ColumnDiameter"))
    m.extrude(sk, "ColumnPad", "四角螺丝柱", h)
    bosses = [(m.p("BossLeftX"), m.p("BossLeftY")*sy) for sy in (-1, 1)]
    bosses += [(m.p("BossRightX"), m.p("BossRightY")*sy) for sy in (-1, 1)]
    sk = m.sketch("BossSketch", "ESP32 安装凸台草图", deck_top)
    m.circles(sk, bosses, m.p("BossDiameter"))
    m.extrude(sk, "BossPad", "ESP32 安装凸台", m.p("BossHeight"))
    sk = m.sketch("CentralSketch", "中央矩形开口草图", deck_top)
    m.rect(sk, m.p("OpeningLength"), m.p("OpeningWidth"))
    m.extrude(sk, "CentralPocket", "中央开口贯穿中层板", dt, pocket=True)
    sk = m.sketch("HeaderSketch", "两条排针槽草图", m.p("HeaderCutTop"))
    for sy in (-1, 1):
        m.rect(sk, m.p("HeaderLength"), m.p("HeaderWidth"),
               m.p("HeaderX"), m.p("HeaderY")*sy)
    m.extrude(sk, "HeaderPocket", "排针槽与中央孔连通",
              m.p("HeaderCutTop")-m.p("HeaderCutBottom"), pocket=True)
    for name, label, centers, diam, z in (
        ("ColumnHoles", "四角柱通孔", cover_centers(m),
         m.p("ColumnHoleDiameter"), m.p("TopZ")),
        ("BossHoles", "ESP32 安装通孔", bosses,
         m.p("BossHoleDiameter"), deck_top+m.p("BossHeight")),
    ):
        sk = m.sketch(name+"Sketch", label+"草图", z)
        m.circles(sk, centers, diam)
        m.extrude(sk, name, label, h+10, pocket=True, through=True)
    for name, label, z, depth in (
        ("UpperFlats", "上层四柱 45 度单平面切削", m.p("TopZ"), m.p("TopZ")-deck_top),
        ("LowerFlats", "下层四柱 45 度单平面切削", dz, dz-m.p("BaseZ")),
    ):
        sk = m.sketch(name+"Sketch", label+"草图", z)
        corner_segments(m, sk)
        m.extrude(sk, name, label, depth, pocket=True)
    rot_yz = App.Rotation(App.Vector(1, 1, 1), 120)
    sk = m.sketch("USBSketch", "Type-C 胶囊形开口草图", x=m.p("OuterLength")/2,
                  rotation=rot_yz)
    m.capsule(sk, m.p("USBLength"), m.p("USBHeight"), 0, m.p("USBZ"))
    m.extrude(sk, "USBPocket", "Type-C 窗口", m.p("Wall"), pocket=True)
    for side in (-1, 1):
        suffix = "Negative" if side < 0 else "Positive"
        guide_rot = App.Rotation(App.Vector(1, 0, 0), side*90)
        sk = m.sketch("GuideSketch"+suffix, "按钮内导向凸台草图 "+suffix,
                      y=(m.p("OuterWidth")/2-m.p("Wall"))*side, rotation=guide_rot)
        m.circles(sk, [(m.p("ButtonX"), m.p("ButtonZ")*side)], m.p("GuideDiameter"))
        m.extrude(sk, "GuidePad"+suffix, "按钮导向凸台 "+suffix, m.p("GuideHeight"))
        outward_rot = App.Rotation(App.Vector(1, 0, 0), -side*90)
        sk = m.sketch("ButtonHoleSketch"+suffix, "按钮滑动孔草图 "+suffix,
                      y=m.p("OuterWidth")/2*side, rotation=outward_rot)
        m.circles(sk, [(m.p("ButtonX"), m.p("ButtonZ")*(-side))],
                  m.p("ButtonHoleDiameter"))
        m.extrude(sk, "ButtonHole"+suffix, "按钮滑动孔 "+suffix,
                  m.p("Wall")+m.p("GuideHeight"), pocket=True)
    for side in (-1, 1):
        suffix = "Negative" if side < 0 else "Positive"
        sk = m.sketch("VentSketch"+suffix, "五条圆弧通风槽草图 "+suffix,
                      x=m.p("OuterLength")/2*side, rotation=rot_yz)
        for i in range(5):
            m.capsule(sk, m.p("VentLength"), m.p("VentHeight"), 0,
                      m.p("VentBottomZ")+m.p("VentHeight")/2+m.p("VentPitch")*i)
        m.extrude(sk, "VentPocket"+suffix, "五条侧面通风槽 "+suffix,
                  m.p("Wall"), pocket=True, reversed=side < 0)
    sk = m.sketch("FootSketch", "四个侧脚钉草图", y=m.p("OuterWidth")/2,
                  rotation=App.Rotation(App.Vector(1, 0, 0), -90))
    feet = [(m.p("FootX")*sx, -z) for sx in (-1, 1)
            for z in (m.p("FootLowerZ"), m.p("TopZ")-m.p("FootTopInset"))]
    m.circles(sk, feet, m.p("FootDiameter"))
    m.extrude(sk, "FootPad", "四个一体侧脚钉", m.p("FootHeight"))
    end_y = m.p("OuterWidth").v/2+m.p("FootHeight").v
    edges = [i+1 for i, edge in enumerate(m.tip.Shape.Edges)
             if edge.BoundBox.YLength < 1e-6
             and abs(edge.CenterOfMass.y-end_y) < 1e-6
             and isinstance(edge.Curve, Part.Circle)]
    assert len(edges) == 4, edges
    m.fillet("FootFillet", "四个脚端过渡圆角", edges, m.p("FootRadius"))
    return m


def compare(model, source):
    a, b = model.tip.Shape, source.Shape
    removed, added = b.cut(a), a.cut(b)
    bounds = ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax")
    aa, bb = a.optimalBoundingBox(False, False), b.optimalBoundingBox(False, False)
    report = dict(label=model.doc.Label, source=source.Name,
                  volume_new=a.Volume, volume_source=b.Volume,
                  removed=removed.Volume, added=added.Volume,
                  bbox_difference={attr: getattr(aa, attr)-getattr(bb, attr) for attr in bounds},
                  sketches=len(model.sketches), native_features=len(model.features),
                  all_sketches_fully_constrained=all(s.FullyConstrained for s in model.sketches))
    print("COMPARISON", json.dumps(report, ensure_ascii=False), flush=True)
    # The inherited cover fillet has C0 B-spline warnings. OCC differences of
    # nearly coincident copies can return invalid full-body remnants; do not
    # accept that result or silently classify it as a real geometric change.
    if source.Name == "FrontBezel":
        assert abs(a.Volume-b.Volume) < .01, report
        distances = []
        for first, other in ((a, b), (b, a)):
            worst, count = 0., 0
            for face in first.Faces:
                points, triangles = face.tessellate(.02)
                points = points[::max(1, len(points)//100)]
                for point in points:
                    worst = max(worst, other.distToShape(Part.Vertex(point))[0])
                count += len(points)
            distances.append(dict(samples=count, maximum_mm=worst))
        assert max(x["maximum_mm"] for x in distances) < .001, distances
        def cylinders(shape):
            return sorted((round(f.Surface.Radius, 6), round(f.Surface.Center.x, 6),
                           round(f.Surface.Center.y, 6), round(f.BoundBox.ZMin, 6),
                           round(f.BoundBox.ZMax, 6))
                          for f in shape.Faces if isinstance(f.Surface, Part.Cylinder))
        assert cylinders(a) == cylinders(b), "Top cover circular features changed"
        report["comparison_method"] = (
            "Matched analytic cylinders and bounding box; bidirectional tessellation "
            "samples to exact opposite CAD surface, tolerance 0.001 mm. "
            "Boolean differences are unreliable for the inherited C0 fillet.")
        report["surface_distances"] = distances
        report["boolean_difference_valid"] = removed.isValid() and added.isValid()
        print("TOP_SURFACE_COMPARISON", distances, flush=True)
    else:
        assert removed.isValid() and added.isValid()
        assert removed.Volume < .003 and added.Volume < .003, report
    assert max(abs(x) for x in report["bbox_difference"].values()) < 2e-5, report
    for feature in model.features:
        assert feature.Shape.isValid() and len(feature.Shape.Solids) == 1
        assert "Invalid" not in feature.State, (feature.Name, feature.State)
    for sketch in model.sketches:
        model.check_sketch(sketch)
    try:
        a.check(True)
        report["extended_check"] = "PASS"
    except Exception as exc:
        report["extended_check"] = str(exc)
        assert source.Name == "FrontBezel"
        assert all(line.strip().endswith("BOPAlgo GeomAbs_C0")
                   for line in str(exc).splitlines() if line.startswith("Error"))
    print("VERIFIED", model.doc.Name, flush=True)
    return report


def modification_test(m, alias, delta):
    cell = m.cells[alias]
    old_content = m.sheet.getContents(cell)
    old_shape = m.tip.Shape.copy()
    changed_value = m.p(alias).v+delta
    m.sheet.set(cell, ("=" if changed_value < 0 else "")+"%.16g mm" % changed_value)
    m.doc.recompute()
    assert m.tip.Shape.isValid() and len(m.tip.Shape.Solids) == 1
    assert all("Invalid" not in obj.State for obj in m.doc.Objects), [
        (obj.Name, obj.State) for obj in m.doc.Objects if "Invalid" in obj.State]
    volume_delta = m.tip.Shape.Volume-old_shape.Volume
    changed_volume = (m.tip.Shape.cut(old_shape).Volume
                      + old_shape.cut(m.tip.Shape).Volume)
    assert changed_volume > 1e-5, (alias, "Shape did not respond")
    m.sheet.set(cell, old_content)
    m.doc.recompute()
    assert m.tip.Shape.cut(old_shape).Volume < .003
    assert old_shape.cut(m.tip.Shape).Volume < .003
    print("EDIT_AND_RESTORE_PASS", m.doc.Name, alias, delta, volume_delta, flush=True)
    return dict(parameter=alias, change=delta, volume_change=volume_delta,
                symmetric_difference_volume=changed_volume)


def main():
    print("STAGE", str(STAGE), flush=True)
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    src = App.openDocument(str(SOURCE))
    records = []
    selected = os.environ.get("EDITABLE_PART", "all")
    specs = [
        ("bottom", bottom, "RemovableBottomCover", "下盖_参数化.FCStd",
         [("SensorHoleDiameter", .1), ("SensorSpacingX", .1), ("OuterLength", .1)]),
        ("middle", middle, "RearShell", "中间外壳_参数化.FCStd",
         [("BossHoleDiameter", .1), ("VentPitch", .05), ("TopZ", .1),
          ("BossLeftX", .05), ("FlatOffset", .05), ("Wall", .05),
          ("HeaderWidth", .1)]),
        ("top", top, "FrontBezel", "上盖_参数化.FCStd",
         [("HoleDiameter", .1), ("WindowWidth", .05), ("OuterLength", .1)]),
    ]
    for key, builder, source_name, filename, tests in specs:
        if selected not in ("all", key):
            continue
        model = builder()
        # Keep diagnostic candidates private until all checks have passed.
        model.doc.saveAs(str(STAGE / ("candidate_" + filename)))
        report = compare(model, src.getObject(source_name))
        report["editing_tests"] = [modification_test(model, alias, delta) for alias, delta in tests]
        for obj in model.doc.Objects:
            if hasattr(obj, "Visibility") and obj != model.body and obj != model.tip:
                obj.Visibility = False
        model.body.Visibility = True
        model.tip.Visibility = True
        path = STAGE / filename
        model.doc.recompute()
        model.doc.saveAs(str(path))
        model_name = model.doc.Name
        App.closeDocument(model_name)
        reopened = App.openDocument(str(path))
        reopened.recompute()
        tip = reopened.Body.Tip
        assert tip.Shape.isValid() and len(tip.Shape.Solids) == 1
        assert all("Invalid" not in o.State for o in reopened.Objects)
        report["reopen_valid"] = True
        report["file"] = str(path)
        records.append(report)
        App.closeDocument(reopened.Name)
        print("SAVED_AND_REOPENED", path, flush=True)
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == digest
    App.closeDocument(src.Name)
    (STAGE / "verification.json").write_text(json.dumps(records, ensure_ascii=False, indent=2))
    print("DONE", STAGE, flush=True)


if __name__ == "__main__":
    main()
