"""Read-only: locate colliding STEP solids and measure room for local reliefs."""
import FreeCAD as App
import Part

PATH='/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd'
doc=App.openDocument(PATH)
board=doc.ESP32BoardAssembly.Shape
shell=doc.RearShell.Shape
print('STEP_SOLID_COUNT',len(board.Solids),flush=True)
def bnds(shape):
    b=shape.BoundBox
    return [round(getattr(b,k),6) for k in ('XMin','YMin','ZMin','XMax','YMax','ZMax')]

for sy in (-1,1):
    center=App.Vector(-18.66,sy*12.62,2.05)
    tower=Part.makeCylinder(3.55,22.95,center)
    bore=Part.makeCylinder(1.15,22.95,center)
    candidates=[]
    for index,solid in enumerate(board.Solids):
        if solid.BoundBox.intersect(tower.BoundBox):
            inter=solid.common(tower)
            gap=solid.distToShape(tower)[0]
            print('NEAR_COLUMN',sy,'SOLID',index,'BOUNDING_BOX',bnds(solid),
                  'INTERSECTION',inter.Volume,'TOWER_GAP',gap,
                  'BORE_TO_SOLID',solid.distToShape(bore)[0],flush=True)
            if inter.Volume>1e-7:
                candidates.append((index,solid))
                print('COLLISION_BOUNDS',bnds(inter),flush=True)
                for i,face in enumerate(solid.Faces):
                    bb=face.BoundBox
                    if bb.ZLength<1e-5:
                        print('HORIZONTAL_FACE',i,'Z',bb.ZMin,'AREA',face.Area,
                              'WIRES',len(face.Wires),'BOUNDING_BOX',bnds(face),flush=True)
    print('COLLIDING_SOLIDS',sy,[i for i,_ in candidates],flush=True)
print('OBJECT_NAMES',[(o.Name,o.Label) for o in doc.Objects],flush=True)
