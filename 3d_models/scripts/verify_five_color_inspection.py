import hashlib
import math
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

root = Path('/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)')
source = root / 'ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd'
exploded = root / 'ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd'
dest = root / 'ESP32-S3-LCD-1.47B_紧凑装配_五色半透明检查.FCStd'
assert hashlib.sha256(source.read_bytes()).hexdigest() == '2c2ab6cee95e60e1f7490db368f759d69fd252ae27b5068e51273ca637b4cc84'
assert hashlib.sha256(exploded.read_bytes()).hexdigest() == '7b49744afa4adeb321f445b906f7eea15f448dfd4ca9e5921e09a262e0f8423e'
with zipfile.ZipFile(source) as a, zipfile.ZipFile(dest) as b:
    payloads = [n for n in a.namelist() if n.endswith('.brp')]
    for name in payloads:
        if a.read(name) != b.read(name):
            lines_a = a.read(name).decode().splitlines()
            lines_b = b.read(name).decode().splitlines()
            differences = [(i, x, y) for i, (x, y) in enumerate(zip(lines_a, lines_b)) if x != y]
            assert len(lines_a) == len(lines_b), name
            for index, x, y in differences:
                # Display/meshing resets OpenCascade's cached Checked flag.
                if (x, y) == ('0111000', '0101000'):
                    continue
                left, right = x.split(), y.split()
                assert len(left) == len(right), (name, index)
                for u, v in zip(left, right):
                    if u != v:
                        assert math.isclose(float(u), float(v), rel_tol=1e-12, abs_tol=1e-12), (name, index, u, v)
    old = ET.fromstring(a.read('Document.xml'))
    new = ET.fromstring(b.read('Document.xml'))
    for obj in old.findall('./ObjectData/Object'):
        name = obj.attrib['name']
        placement = obj.find('./Properties/Property[@name="Placement"]')
        if placement is not None:
            other = new.find('./ObjectData/Object[@name="%s"]/Properties/Property[@name="Placement"]' % name)
            assert ET.tostring(placement) == ET.tostring(other), name
    gui = ET.fromstring(b.read('GuiDocument.xml'))
    colors = set()
    visible = []
    for view in gui.findall('./ViewProviderData/ViewProvider'):
        name = view.attrib['name']
        visibility = view.find('./Properties/Property[@name="Visibility"]/Bool')
        appearance = view.find('./Properties/Property[@name="ShapeAppearance"]/MaterialList')
        if visibility is not None and visibility.attrib['value'] == 'true' and appearance is not None:
            visible.append(name)
            transparency = view.find('./Properties/Property[@name="Transparency"]/Integer')
            assert transparency.attrib['value'] == '60', name
            material = b.read(appearance.attrib['file'])
            colors.add(material)
            print('VISIBLE_60_PERCENT', name)
    assert len(visible) == 10, visible
    assert len(colors) == 5, len(colors)
    envelope = gui.find('./ViewProviderData/ViewProvider[@name="CO2SensorEnvelope"]/Properties/Property[@name="Visibility"]/Bool')
    assert envelope.attrib['value'] == 'false'
    assert not new.findall('.//Object[@type="App::Link"]')
    print('ORIGINAL_FILES_UNCHANGED; ALL_VISIBLE_TRANSPARENCY_60_PERCENT')
    print('ALL_BREP_GEOMETRY_AND_TOPOLOGY_IDENTICAL_WITHIN_1E-12')
    print('ALL_PLACEMENTS_IDENTICAL; FIVE_VISIBLE_COLOR_GROUPS; NO_LINK_OBJECTS')
