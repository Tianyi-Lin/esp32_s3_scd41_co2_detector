import math
import FreeCAD as App
import Part

root='/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)'
main=App.openDocument(root+'/ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd')
backup=App.openDocument('/Users/bytedance/Documents/New project/.cad-recovery/before-pcb-inner-relief-8kfB3VJE/ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd')
original=backup.RearShell.Shape
board=main.ESP32BoardAssembly.Shape
pcb=next(s for s in board.Solids if s.BoundBox.XLength>30 and s.BoundBox.YLength>18 and abs(s.BoundBox.ZLength-.8)<.005)
top=max((f for f in pcb.Faces if f.BoundBox.ZLength<1e-5),key=lambda f:f.CenterOfMass.z)
outline=Part.Face(top.OuterWire)
cutters=[]
for y in (-12.62,12.62):
    # Local X points inward at +/-45 degrees; local Y runs along the cut face.
    angle=45. if y<0 else -45.
    aligned=outline.copy()
    aligned.translate(App.Vector(18.66,-y,0))
    aligned.rotate(App.Vector(),App.Vector(0,0,1),-angle)
    distance=aligned.BoundBox.XMin-.3
    z0=pcb.BoundBox.ZMin-.3
    halfspace=Part.makeBox(20,40,25.1-z0,App.Vector(distance,-20,z0))
    halfspace.rotate(App.Vector(),App.Vector(0,0,1),angle)
    halfspace.translate(App.Vector(-18.66,y,0))
    column=Part.makeCylinder(3.55,22.95,App.Vector(-18.66,y,2.05))
    cutter=halfspace.common(column)
    cutters.append(cutter)
    bore=Part.makeCylinder(1.15,22.95,App.Vector(-18.66,y,2.05))
    nominal=Part.makeCylinder(1.25,22.95,App.Vector(-18.66,y,2.05))
    print('PLANE',y,'ANGLE',angle,'CENTER_DISTANCE',distance,'WALL',bore.distToShape(cutter)[0],'NOMINAL_WALL',nominal.distToShape(cutter)[0],flush=True)
tool=Part.makeCompound(cutters)
after=original.cut(tool).removeSplitter()
print('VALID',after.isValid(),len(after.Solids),'REMOVED',original.Volume-after.Volume,flush=True)
for y in (-12.62,12.62):
    zone=Part.makeCylinder(3.55,22.95,App.Vector(-18.66,y,2.05))
    print('PCB_GAP',y,after.common(zone).distToShape(pcb)[0],flush=True)
print('BOARD_COLLISION',after.common(board).Volume,flush=True)
