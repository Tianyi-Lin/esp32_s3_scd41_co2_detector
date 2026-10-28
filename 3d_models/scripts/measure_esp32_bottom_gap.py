"""Read-only inspection of PCB underside to bottom-cover inner floor."""
import FreeCAD as App
import Part

ROOT = '/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/'
for filename in ('ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd',
                 'ESP32-S3-LCD-1.47B_紧凑装配_五色半透明检查.FCStd'):
    doc = App.openDocument(ROOT + filename)
    board = doc.ESP32BoardAssembly
    bottom = doc.RemovableBottomCover
    print('DOCUMENT', filename, flush=True)
    print('BOARD_PLACEMENT', board.Placement, flush=True)
    print('BOTTOM_PLACEMENT', bottom.Placement, flush=True)
    print('LARGE_BOARD_ASSEMBLY_SOLIDS', flush=True)
    for index, solid in enumerate(board.Shape.Solids):
        bb = solid.BoundBox
        if bb.XLength > 20 and bb.YLength > 10:
            print('SOLID', index, 'BOUNDS', bb, 'SIZE',
                  bb.XLength, bb.YLength, bb.ZLength, 'VOLUME', solid.Volume,
                  flush=True)
            faces = []
            for fi, face in enumerate(solid.Faces):
                fb = face.BoundBox
                if isinstance(face.Surface, Part.Plane) and fb.ZLength < 1e-6 and face.Area > 100:
                    faces.append((fi, fb.ZMin, face.Area, face.normalAt(0, 0)))
            print('LARGE_HORIZONTAL_FACES', faces, flush=True)
    print('BOTTOM_COVER_HORIZONTAL_FACES', flush=True)
    for index, face in enumerate(bottom.Shape.Faces):
        bb = face.BoundBox
        if isinstance(face.Surface, Part.Plane) and bb.ZLength < 1e-6 and face.Area > 100:
            print('BOTTOM_FACE', index + 1, 'Z', bb.ZMin, 'AREA', face.Area,
                  'NORMAL', face.normalAt(0, 0), flush=True)
    print('PARAMETERS', [(n, str(getattr(doc.DesignParameters, n)))
                         for n in ('BoardLayerStart', 'PCBMountContactHeight')], flush=True)
    App.closeDocument(doc.Name)
