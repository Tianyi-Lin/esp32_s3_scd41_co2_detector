"""Narrow the current two square-ended header slots without regenerating CAD."""
import os
import FreeCAD as App
import Part
import Mesh

OUT_DIR = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
NAMES = ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
         "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd")
PCB_MOUNTS = [(-16.814, -6.640), (-16.814, 6.640),
              (15.186, -8.160), (15.186, 8.160)]
NEW_WIDTH, END_MARGIN = 2.6, 1.3
DECK_Z = 13.5
TOL = 1e-7

def rounded_prism(w, d, h, r, z):
    shape = Part.makeBox(w-2*r, d, h, App.Vector(-w/2+r, -d/2, z))
    shape = shape.fuse(Part.makeBox(w, d-2*r, h, App.Vector(-w/2, -d/2+r, z)))
    for x in (-w/2+r, w/2-r):
        for y in (-d/2+r, d/2-r):
            shape = shape.fuse(Part.makeCylinder(r, h, App.Vector(x,y,z)))
    return shape.removeSplitter()

pending = []
for filename in NAMES:
    doc = App.openDocument(os.path.join(OUT_DIR, filename))
    p, shell = doc.DesignParameters, doc.RearShell
    assert shell.Placement.toMatrix().A == App.Placement().toMatrix().A
    before = shell.Shape.copy()
    others = {o.Name:(o.Shape,o.Placement.toMatrix().A) for o in doc.Objects
              if "Shape" in o.PropertiesList and o != shell}
    centers = [(s.BoundBox.Center.x,s.BoundBox.Center.y)
               for s in doc.HeaderPinsKeepout.Shape.Solids]
    rows = sorted({round(y,6) for x,y in centers})
    assert len(rows)==2 and len(centers)==18
    first_x,last_x = min(x for x,y in centers),max(x for x,y in centers)
    xmin,xmax = first_x-END_MARGIN,last_x+END_MARGIN
    length,center_x = xmax-xmin,(xmin+xmax)/2
    assert abs(length-22.92)<TOL
    assert abs(p.HeaderSlotLength.Value-23.1)<TOL
    assert abs(p.HeaderSlotWidth.Value-2.7)<TOL
    cut_z,cut_top = p.HeaderSlotCutBottomZ.Value,p.HeaderSlotCutTopZ.Value
    def row_cuts(slot_length,slot_width):
        return Part.makeCompound([Part.makeBox(slot_length,slot_width,cut_top-cut_z,
            App.Vector(center_x-slot_length/2,y-slot_width/2,cut_z)) for y in rows])
    old_cuts = row_cuts(p.HeaderSlotLength.Value,p.HeaderSlotWidth.Value)
    new_cuts = row_cuts(length,NEW_WIDTH)
    allowed = old_cuts.cut(new_cuts)

    # Restore material only where the original structural deck or pedestals
    # existed. Do not fill the empty space below the deck or above each boss.
    thickness = p.InterLayerDeckThickness.Value
    cavity_w = p.OuterLength.Value-2*p.WallThickness.Value
    cavity_d = p.OuterWidth.Value-2*p.WallThickness.Value
    cavity_r = 5.0-p.WallThickness.Value
    overlap = p.InterLayerDeckWallOverlap.Value
    deck = rounded_prism(cavity_w+2*overlap,cavity_d+2*overlap,thickness,
                         cavity_r+overlap,DECK_Z)
    envelope = deck
    deck_top = DECK_Z+thickness
    for x,y in PCB_MOUNTS:
        envelope = envelope.fuse(Part.makeCylinder(p.PCBBossDiameter.Value/2,
            p.PCBMountContactHeight.Value-deck_top,App.Vector(x,y,deck_top)))
    for x in (-18.1,18.1):
        for y in (-12.2,12.2):
            envelope = envelope.fuse(Part.makeCylinder(p.SideBodyColumnDiameter.Value/2,
                23.0,App.Vector(x,y,2.0)))
    central = Part.makeBox(p.CentralOpeningLength.Value,p.CentralOpeningWidth.Value,
        thickness+1.0,App.Vector(-p.CentralOpeningLength.Value/2,
                                -p.CentralOpeningWidth.Value/2,DECK_Z-0.5))
    holes = Part.makeCompound(
        [Part.makeCylinder(p.PCBMountThroughHoleDiameter.Value/2,
            cut_top-DECK_Z+0.2,App.Vector(x,y,DECK_Z-0.1)) for x,y in PCB_MOUNTS]
        + [Part.makeCylinder(p.SideBodyTapHoleDiameter.Value/2,23.2,
            App.Vector(x,y,1.9)) for x in (-18.1,18.1) for y in (-12.2,12.2)])
    fill = allowed.common(envelope).cut(central).cut(holes)
    after = before.fuse(fill).removeSplitter()
    added = after.cut(before)
    assert after.isValid() and len(after.Solids)==1
    assert before.cut(after).Volume<TOL
    assert added.Volume>0.1 and added.cut(allowed).Volume<TOL
    assert after.common(new_cuts).Volume<TOL
    assert after.common(holes).Volume<TOL
    assert after.common(central).Volume<TOL
    assert added.cut(envelope).Volume<TOL
    for field in ("XMin","XMax","YMin","YMax","ZMin","ZMax"):
        assert abs(getattr(after.BoundBox,field)-getattr(before.BoundBox,field))<TOL

    # Probe material just outside both square ends and both width edges. The
    # width probes are in the left extension, outside the central opening.
    for y in rows:
        probes = [Part.makeBox(.01,1.0,.5,App.Vector(x,y-.5,14.0))
                  for x in (xmin-.01,xmax)]
        probes += [Part.makeBox(.5,.01,.5,App.Vector(-14.5,ey,14.0))
                   for ey in (y-NEW_WIDTH/2-.01,y+NEW_WIDTH/2)]
        assert all(probe.cut(after).Volume<TOL for probe in probes)
        clearance = Part.makeBox(length,NEW_WIDTH,cut_top-cut_z,
                                 App.Vector(xmin,y-NEW_WIDTH/2,cut_z))
        assert clearance.common(after).Volume<TOL
        assert abs(first_x-xmin-END_MARGIN)<TOL and abs(xmax-last_x-END_MARGIN)<TOL
    center_overlap = p.CentralOpeningWidth.Value/2-(abs(rows[0])-NEW_WIDTH/2)
    assert abs(center_overlap-.15)<TOL
    joined_air = central.fuse(new_cuts).removeSplitter()
    assert len(joined_air.Solids)==1

    # The four wall joints must remain fully connected after this change.
    joints = [Part.makeBox(.7,cavity_d-2*cavity_r,thickness,
                App.Vector(sign*cavity_w/2-.35,-cavity_d/2+cavity_r,DECK_Z))
                for sign in (-1,1)]
    joints += [Part.makeBox(cavity_w-2*cavity_r,.7,thickness,
                App.Vector(-cavity_w/2+cavity_r,sign*cavity_d/2-.35,DECK_Z))
                for sign in (-1,1)]
    assert all(j.cut(after).Volume<TOL for j in joints)
    if filename==NAMES[0]:
        for name in ("ESP32BoardAssembly","HeaderPinsKeepout","CO2SensorEnvelope",
                     "ButtonPlungerPositive","ButtonPlungerNegative"):
            assert added.common(doc.getObject(name).Shape).Volume<TOL,name
    shell.Shape = after
    p.HeaderSlotWidth = NEW_WIDTH
    p.HeaderSlotLength = length
    p.SlotToCenterOverlap = center_overlap
    if "HeaderSlotEndAxisDistance" not in p.PropertiesList:
        p.addProperty("App::PropertyLength","HeaderSlotEndAxisDistance","Dimensions")
    p.HeaderSlotEndAxisDistance = END_MARGIN
    p.Layout += "两排杜邦排针长条孔宽2.6mm、长22.92mm，方形两端至最近排针轴心各1.3mm，保持与中央孔连通并切穿凸台。"
    doc.recompute()
    for name,(old_shape,old_pose) in others.items():
        obj=doc.getObject(name)
        assert obj.Shape.isSame(old_shape) and obj.Placement.toMatrix().A==old_pose,name
    print("VERIFIED",filename,"LENGTH",length,"WIDTH",NEW_WIDTH,
          "END_AXIS_DISTANCE",END_MARGIN,"X_BOUNDS",(xmin,xmax),
          "CENTER_OVERLAP",center_overlap,"ADDED_VOLUME",added.Volume,
          "OTHER_OBJECTS_UNCHANGED",len(others),flush=True)
    pending.append(doc)

assert pending[0].RearShell.Shape.cut(pending[1].RearShell.Shape).Volume<TOL
assert pending[1].RearShell.Shape.cut(pending[0].RearShell.Shape).Volume<TOL
for doc in pending:
    doc.save()
stl_path = os.path.join(OUT_DIR,"ESP32-S3-LCD-1.47B_紧凑双层外壳_后壳.stl")
Part.export([pending[0].RearShell],stl_path)
mesh = Mesh.Mesh(stl_path)
assert mesh.isSolid()
print("STL_CLOSED",mesh.CountFacets,flush=True)
for doc in pending:
    path=doc.FileName
    App.closeDocument(doc.Name)
    check=App.openDocument(path)
    assert check.RearShell.Shape.isValid() and len(check.RearShell.Shape.Solids)==1
    assert abs(check.DesignParameters.HeaderSlotWidth.Value-NEW_WIDTH)<TOL
    assert abs(check.DesignParameters.HeaderSlotLength.Value-22.92)<TOL
    print("SAVED_REOPENED",path,flush=True)
    App.closeDocument(check.Name)
