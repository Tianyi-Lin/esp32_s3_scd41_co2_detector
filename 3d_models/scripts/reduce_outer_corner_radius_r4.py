"""Reduce only the three enclosure parts' external corner radii from R5 to R4."""
import math
import os
import FreeCAD as App
import Part
import Mesh

ROOT='/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)'
FILES=('ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd',
       'ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd')
PARTS={'RearShell':(2.05,25.,'后壳'),
       'FrontBezel':(25.,28.,'前盖'),
       'RemovableBottomCover':(0.,2.,'可拆底盖')}
W,D=45.,33.5
OLD_R,NEW_R=5.,4.
TOL=1e-6

def rounded_prism(radius,z,height):
    result=Part.makeBox(W-2*radius,D,height,App.Vector(-W/2+radius,-D/2,z))
    result=result.fuse(Part.makeBox(W,D-2*radius,height,App.Vector(-W/2,-D/2+radius,z)))
    for x in (-W/2+radius,W/2-radius):
        for y in (-D/2+radius,D/2-radius):
            result=result.fuse(Part.makeCylinder(radius,height,App.Vector(x,y,z)))
    return result.removeSplitter()

def local_shape(obj):
    return obj.Shape.transformed(obj.Placement.inverse().toMatrix(),copy=True)

def cylinder_records(shape):
    return sorted((round(f.Surface.Radius,6),round(f.Surface.Center.x,6),
                   round(f.Surface.Center.y,6),round(f.BoundBox.ZMin,6),round(f.BoundBox.ZMax,6))
                  for f in shape.Faces if isinstance(f.Surface,Part.Cylinder)
                  and abs(f.Surface.Axis.z)>.999999)

def outer_records(records,radius):
    return [record for record in records if abs(record[0]-radius)<TOL
            and abs(abs(record[1])-(W/2-radius))<TOL
            and abs(abs(record[2])-(D/2-radius))<TOL]

def perimeter_wire(radius,z):
    wafer=rounded_prism(radius,z,.01)
    face=min(wafer.Faces,key=lambda f:f.CenterOfMass.z)
    return face.OuterWire

def radial_outer_distance():
    # Current axes retain their original corner-radius direction (0.8,0.6).
    dx,dy=18.66-(W/2-NEW_R),12.62-(D/2-NEW_R)
    projection=dx*.8+dy*.6
    return -projection+math.sqrt(projection**2+NEW_R**2-dx**2-dy**2)

pending=[]
for filename in FILES:
    doc=App.openDocument(os.path.join(ROOT,filename))
    params=doc.DesignParameters
    assert abs(params.PCBBossDiameter.Value-3.2)<TOL
    assert abs(params.CoverHeadPocketDiameter.Value-5.1)<TOL
    assert abs(params.CoverScrewCenterX.Value-18.66)<TOL
    assert abs(params.CoverScrewCenterY.Value-12.62)<TOL
    unchanged={obj.Name:(obj.Shape,obj.Placement.toMatrix().A)
               for obj in doc.Objects if 'Shape' in obj.PropertiesList and obj.Name not in PARTS}
    for name,(z0,z1,suffix) in PARTS.items():
        obj=doc.getObject(name)
        pose=App.Placement(obj.Placement)
        before=local_shape(obj)
        old_blank=rounded_prism(OLD_R,z0,z1-z0)
        new_blank=rounded_prism(NEW_R,z0,z1-z0)
        additions=new_blank.cut(old_blank)
        after=before.fuse(additions).removeSplitter()
        assert after.isValid() and len(after.Solids)==1,name
        assert before.cut(after).Volume<TOL,(name,'unexpected removal')
        assert after.cut(before).cut(additions).Volume<TOL,(name,'out-of-scope additions')
        assert additions.cut(after).Volume<TOL,(name,'missing corner material')
        expected_volume=(4-math.pi)*(OLD_R**2-NEW_R**2)*(z1-z0)
        assert abs(after.Volume-before.Volume-expected_volume)<.003,(name,after.Volume-before.Volume,expected_volume)
        for axis in ('XMin','XMax','YMin','YMax','ZMin','ZMax'):
            assert abs(getattr(before.BoundBox,axis)-getattr(after.BoundBox,axis))<TOL,(name,axis)
        old_cyls=cylinder_records(before)
        new_cyls=cylinder_records(after)
        old_outer=outer_records(old_cyls,OLD_R)
        new_outer=outer_records(new_cyls,NEW_R)
        assert len(old_outer)==4 and len(new_outer)==4,(name,old_outer,new_outer)
        assert not outer_records(new_cyls,OLD_R)
        assert [c for c in old_cyls if c not in old_outer]==[c for c in new_cyls if c not in new_outer],name
        # All changes lie outside the former external envelope. Thus the
        # entire interior, deck, bosses, holes, windows and ports are retained.
        assert after.common(old_blank).cut(before).Volume<TOL,(name,'interior addition')
        if name!='RearShell':
            z=27.5 if name=='FrontBezel' else .5
            outline=perimeter_wire(NEW_R,z)
            for x in (-18.66,18.66):
                for y in (-12.62,12.62):
                    counterbore=Part.Wire([Part.makeCircle(2.55,App.Vector(x,y,z))])
                    distance=outline.distToShape(counterbore)[0]
                    assert abs(distance-1.29)<TOL,(name,x,y,distance)
                    print('COUNTERBORE_TO_OUTER_EDGE_MM',name,x,y,distance,flush=True)
        obj.Shape=after
        obj.Placement=pose
        print('VALIDATED',filename,name,'OUTER_RADIUS',NEW_R,
              'ADDED_VOLUME',after.Volume-before.Volume,flush=True)
    # Separate the historical equal-wall value into the now-different sides.
    if 'CoverScrewRadialWallThickness' in params.PropertiesList:
        params.removeProperty('CoverScrewRadialWallThickness')
    for key,value in (('OuterCornerRadius',NEW_R),('InnerCornerRadius',3.),
                      ('CoverHeadPocketOuterRim',1.29),
                      ('CoverScrewRadialInnerWallThickness',2.4),
                      ('CoverScrewRadialOuterWallThickness',radial_outer_distance()-1.15)):
        if key not in params.PropertiesList:
            params.addProperty('App::PropertyLength',key,'Dimensions')
        setattr(params,key,value)
    params.Layout += ('外轮廓四角统一由R5改为R4，长宽45×33.5mm不变；'
                      '仅补足外角材料，内腔、孔位、凸台和沉孔不变；'
                      '四角Ø5.1沉孔至外缘最小1.29mm，替代此前1mm留边；'
                      '侧壁角柱径向内壁仍2.4mm、外壁约2.795mm，不再内外等厚。')
    doc.recompute()
    for name,(shape,pose) in unchanged.items():
        obj=doc.getObject(name)
        assert obj.Shape.isSame(shape) and obj.Placement.toMatrix().A==pose,name
    print('OTHER_OBJECTS_UNCHANGED',len(unchanged),flush=True)
    pending.append(doc)

for name in PARTS:
    a=local_shape(pending[0].getObject(name))
    b=local_shape(pending[1].getObject(name))
    assert a.cut(b).Volume<TOL and b.cut(a).Volume<TOL,name
for doc in pending:
    doc.save()
for name,(_,_,suffix) in PARTS.items():
    path=os.path.join(ROOT,'ESP32-S3-LCD-1.47B_紧凑双层外壳_'+suffix+'.stl')
    Part.export([pending[0].getObject(name)],path)
    mesh=Mesh.Mesh(path)
    assert mesh.isSolid(),suffix
    print('STL_CLOSED',suffix,mesh.CountFacets,flush=True)
for doc in pending:
    path=doc.FileName
    App.closeDocument(doc.Name)
    check=App.openDocument(path)
    for name in PARTS:
        shape=local_shape(check.getObject(name))
        assert shape.isValid() and len(shape.Solids)==1
        assert len(outer_records(cylinder_records(shape),NEW_R))==4
    print('SAVED_REOPENED',path,flush=True)
    App.closeDocument(check.Name)
