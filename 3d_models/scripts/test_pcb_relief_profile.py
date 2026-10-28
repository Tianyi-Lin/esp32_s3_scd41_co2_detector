import FreeCAD as App
import Part

doc=App.openDocument('/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd')
pcb=doc.ESP32BoardAssembly.Shape.Solids[1]
face=max((f for f in pcb.Faces if f.BoundBox.ZLength<1e-5),key=lambda f:f.CenterOfMass.z)
outer=Part.Face(face.OuterWire)
print('OFFSET_HELP',outer.makeOffset2D.__doc__,flush=True)
print('PCB_OUTLINE',outer.Area,len(outer.Edges),str(outer.BoundBox),flush=True)
offset=outer.makeOffset2D(.3,0,False,False,False)
print('OFFSET',offset.ShapeType,offset.isValid(),len(offset.Faces),offset.Area,str(offset.BoundBox),flush=True)
print('OFFSET_EDGE_DISTANCE',outer.OuterWire.distToShape(offset.OuterWire)[0],flush=True)
assert offset.Area>outer.Area and outer.cut(offset).Area<1e-6
offset.translate(App.Vector(0,0,pcb.BoundBox.ZMin-.3-offset.BoundBox.ZMin))
sweep=offset.extrude(App.Vector(0,0,25.1-offset.BoundBox.ZMin))
zones=Part.makeCompound([Part.makeCylinder(3.55,22.95,App.Vector(-18.66,y,2.05)) for y in (-12.62,12.62)])
tool=sweep.common(zones)
after=doc.RearShell.Shape.cut(tool).removeSplitter()
print('SHAPE_VALID',after.isValid(),len(after.Solids),'REMOVED',doc.RearShell.Shape.Volume-after.Volume,flush=True)
for y in (-12.62,12.62):
    column=Part.makeCylinder(3.55,22.95,App.Vector(-18.66,y,2.05))
    remaining=after.common(column)
    bore=Part.makeCylinder(1.15,22.95,App.Vector(-18.66,y,2.05))
    print('SIDE',y,'PCB_GAP',remaining.distToShape(pcb)[0],
          'BORE_TO_RELIEF',bore.distToShape(tool)[0],flush=True)
print('ALL_BOARD_COLLISION',after.common(doc.ESP32BoardAssembly.Shape).Volume,flush=True)
