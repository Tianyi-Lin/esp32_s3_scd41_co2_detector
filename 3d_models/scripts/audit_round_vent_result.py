import math
import FreeCAD as App
import Part

root='/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)'
backup='/Users/bytedance/Documents/New project/.cad-recovery/before-round-vents-deep-relief-nVlPcPqH'
old=App.openDocument(backup+'/ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd')
new=App.openDocument(root+'/ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd')
a=old.RearShell.Shape.copy()
b=new.RearShell.Shape.copy()
av,bv=a.Volume,b.Volume
print('RELOADED_BODY_VOLUMES',av,bv,flush=True)
added=b.cut(a)
removed=a.cut(b)
expected_added=10*(14*.9-((14-.9)*.9+math.pi*.45**2))*2.2
distance=new.DesignParameters.PCBColumnReliefPlaneOffset.Value
segment=3.55**2*math.acos(distance/3.55)-distance*math.sqrt(3.55**2-distance**2)
expected_removed=2*segment*(old.DesignParameters.PCBColumnReliefBottomZ.Value-15.5)
print('ADDED_REMOVED',added.Volume,removed.Volume,'ANALYTIC',expected_added,expected_removed,flush=True)
assert abs(added.Volume-expected_added)<1e-6
assert abs(removed.Volume-expected_removed)<1e-6
assert abs(bv-av-expected_added+expected_removed)<1e-6
for name in ('RearShell','RemovableBottomCover'):
    s=new.getObject(name).Shape
    assert s.isValid() and len(s.Solids)==1
    print('RELOADED_VALID',name,s.Volume,flush=True)
