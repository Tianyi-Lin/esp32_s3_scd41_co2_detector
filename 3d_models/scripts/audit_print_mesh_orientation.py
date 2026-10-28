"""Read-only STL orientation audit. Does not save or repair any model."""
from pathlib import Path
import hashlib
import json
import struct
import numpy as np
import FreeCAD as App
import Mesh

ROOT = Path("/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)")


def raw_stl(path):
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) == 84 + count * 50:
        dtype = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")])
        records = np.frombuffer(data, dtype=dtype, count=count, offset=84)
        return records["vertices"].astype(float), records["normal"].astype(float), "binary"
    normals, vertices = [], []
    for line in data.decode("ascii").splitlines():
        fields = line.split()
        if fields[:2] == ["facet", "normal"]:
            normals.append([float(x) for x in fields[2:5]])
        elif fields[:1] == ["vertex"]:
            vertices.append([float(x) for x in fields[1:4]])
    return np.array(vertices).reshape(-1, 3, 3), np.array(normals), "ascii"


def topology(vertices):
    points, indices = np.unique(vertices.reshape(-1, 3), axis=0, return_inverse=True)
    faces = indices.reshape(-1, 3)
    edges = np.stack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]), axis=1).reshape(-1, 2)
    unique, inverse, counts = np.unique(np.sort(edges, axis=1), axis=0, return_inverse=True, return_counts=True)
    direction_sum = np.bincount(inverse, weights=np.where(edges[:, 0] < edges[:, 1], 1, -1), minlength=len(unique))
    wrong = (counts == 2) & (direction_sum != 0)
    return {
        "vertices": len(points),
        "edges": len(unique),
        "boundary_edges": int(np.count_nonzero(counts == 1)),
        "nonmanifold_edges": int(np.count_nonzero(counts > 2)),
        "same_direction_shared_edges": int(np.count_nonzero(wrong)),
        "duplicate_faces": len(faces) - len(np.unique(np.sort(faces, axis=1), axis=0)),
    }


doc = App.openDocument(str(ROOT / "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd"))
objects = {"前盖": "FrontBezel", "后壳": "RearShell", "可拆底盖": "RemovableBottomCover",
           "按键顶杆_打印2件": "ButtonPlungerPositive"}
for path in sorted((ROOT / "打印文件").glob("*.stl")):
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    vertices, normals, filetype = raw_stl(path)
    cross = np.cross(vertices[:, 1] - vertices[:, 0], vertices[:, 2] - vertices[:, 0])
    lengths = np.linalg.norm(cross, axis=1)
    nlength = np.linalg.norm(normals, axis=1)
    nonzero = (lengths > 1e-15) & (nlength > 1e-15)
    cosines = np.einsum("ij,ij->i", cross[nonzero], normals[nonzero]) / (lengths[nonzero] * nlength[nonzero])
    result = {"file": path.name, "format": filetype, "facets": len(vertices),
              "volume_signed_mm3": float(np.einsum("ij,ij->i", vertices[:, 0], np.cross(vertices[:, 1], vertices[:, 2])).sum()/6),
              "area_mm2": float(lengths.sum()/2),
              "bbox_mm": (vertices.max(axis=(0, 1))-vertices.min(axis=(0, 1))).tolist(),
              "degenerate_facets_below_1e-12_mm2": int(np.count_nonzero(lengths < 2e-12)),
              "stored_normals_opposite_to_winding": int(np.count_nonzero(cosines < 0)),
              "stored_normals_more_than_1deg_off": int(np.count_nonzero(cosines < np.cos(np.pi/180))),
              "zero_stored_normals": int(np.count_nonzero(nlength < 1e-15)),
              "min_normal_cosine": float(cosines.min()),
              "raw_topology": topology(vertices)}
    mesh = Mesh.Mesh(str(path))
    result["freecad"] = {"solid": mesh.isSolid(), "nonuniform_oriented_facets": mesh.countNonUniformOrientedFacets(),
                         "nonmanifolds": mesh.hasNonManifolds(), "corrupted": mesh.hasCorruptedFacets(),
                         "out_of_range": mesh.hasFacetsOutOfRange()}
    key = path.stem.split("紧凑双层外壳_", 1)[1]
    shape = doc.getObject(objects[key]).Shape
    result["native_cad"] = {"valid": shape.isValid(), "solids": len(shape.Solids), "volume_mm3": shape.Volume,
                             "orientation": shape.Orientation}
    result["matches_root_copy"] = before == hashlib.sha256((ROOT/path.name).read_bytes()).hexdigest()
    assert before == hashlib.sha256(path.read_bytes()).hexdigest()
    print(json.dumps(result, ensure_ascii=False), flush=True)
App.closeDocument(doc.Name)
