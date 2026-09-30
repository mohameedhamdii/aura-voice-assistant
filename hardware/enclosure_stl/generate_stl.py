"""
Generates the 3D-printable binary STL file for the smart speaker enclosure.
Outputs hardware/enclosure_stl/speaker_housing.stl directly.
"""

import math
import struct
from pathlib import Path

def write_binary_stl(filename, facets):
    """
    Write facets to binary STL format.
    Each facet is ((nx, ny, nz), (v1x, v1y, v1z), (v2x, v2y, v2z), (v3x, v3y, v3z))
    """
    header = b"Smart Speaker Enclosure - Offline Voice Assistant 3D Model" + b" " * 22
    header = header[:80]
    
    with open(filename, "wb") as f:
        f.write(header)
        f.write(struct.pack("<I", len(facets)))
        for normal, v1, v2, v3 in facets:
            f.write(struct.pack("<3f", *normal))
            f.write(struct.pack("<3f", *v1))
            f.write(struct.pack("<3f", *v2))
            f.write(struct.pack("<3f", *v3))
            f.write(struct.pack("<H", 0))

def compute_normal(v1, v2, v3):
    u = (v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2])
    v = (v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2])
    nx = u[1] * v[2] - u[2] * v[1]
    ny = u[2] * v[0] - u[0] * v[2]
    nz = u[0] * v[1] - u[1] * v[0]
    length = math.sqrt(nx*nx + ny*ny + nz*nz)
    if length > 1e-9:
        return (nx/length, ny/length, nz/length)
    return (0.0, 0.0, 1.0)

def add_quad(facets, v1, v2, v3, v4):
    """Adds a quad as two counter-clockwise triangles: (v1, v2, v3) and (v1, v3, v4)"""
    n1 = compute_normal(v1, v2, v3)
    facets.append((n1, v1, v2, v3))
    n2 = compute_normal(v1, v3, v4)
    facets.append((n2, v1, v3, v4))

def generate_speaker_housing_stl():
    output_path = Path(__file__).parent / "speaker_housing.stl"
    
    # Model parameters in mm
    outer_r = 46.0      # 92mm OD
    inner_r = 43.0      # 86mm ID (3mm wall)
    speaker_hole_r = 23.0 # 46mm speaker aperture
    height = 135.0
    floor_h = 4.0
    segments = 64
    
    facets = []
    
    # Precompute ring vertices
    angles = [2 * math.pi * i / segments for i in range(segments)]
    
    # 1. Outer Cylinder Wall
    for i in range(segments):
        i_next = (i + 1) % segments
        a1, a2 = angles[i], angles[i_next]
        
        # Bottom outer
        bo1 = (outer_r * math.cos(a1), outer_r * math.sin(a1), 0.0)
        bo2 = (outer_r * math.cos(a2), outer_r * math.sin(a2), 0.0)
        # Top outer
        to1 = (outer_r * math.cos(a1), outer_r * math.sin(a1), height)
        to2 = (outer_r * math.cos(a2), outer_r * math.sin(a2), height)
        
        # Outer quad
        add_quad(facets, bo1, bo2, to2, to1)
        
    # 2. Inner Cylinder Wall (from floor_h to height)
    for i in range(segments):
        i_next = (i + 1) % segments
        a1, a2 = angles[i], angles[i_next]
        
        # Inner floor
        bi1 = (inner_r * math.cos(a1), inner_r * math.sin(a1), floor_h)
        bi2 = (inner_r * math.cos(a2), inner_r * math.sin(a2), floor_h)
        # Inner top
        ti1 = (inner_r * math.cos(a1), inner_r * math.sin(a1), height)
        ti2 = (inner_r * math.cos(a2), inner_r * math.sin(a2), height)
        
        # Inner quad (faces inward)
        add_quad(facets, bi2, bi1, ti1, ti2)
        
    # 3. Top Rim connecting outer and inner walls
    for i in range(segments):
        i_next = (i + 1) % segments
        a1, a2 = angles[i], angles[i_next]
        
        to1 = (outer_r * math.cos(a1), outer_r * math.sin(a1), height)
        to2 = (outer_r * math.cos(a2), outer_r * math.sin(a2), height)
        ti1 = (inner_r * math.cos(a1), inner_r * math.sin(a1), height)
        ti2 = (inner_r * math.cos(a2), inner_r * math.sin(a2), height)
        
        add_quad(facets, to1, to2, ti2, ti1)

    # 4. Bottom Base Surface (with speaker center hole)
    for i in range(segments):
        i_next = (i + 1) % segments
        a1, a2 = angles[i], angles[i_next]
        
        bo1 = (outer_r * math.cos(a1), outer_r * math.sin(a1), 0.0)
        bo2 = (outer_r * math.cos(a2), outer_r * math.sin(a2), 0.0)
        sh1 = (speaker_hole_r * math.cos(a1), speaker_hole_r * math.sin(a1), 0.0)
        sh2 = (speaker_hole_r * math.cos(a2), speaker_hole_r * math.sin(a2), 0.0)
        
        # Bottom face facing -Z
        add_quad(facets, bo2, bo1, sh1, sh2)

    # 5. Inner Floor Surface (between speaker hole and inner wall)
    for i in range(segments):
        i_next = (i + 1) % segments
        a1, a2 = angles[i], angles[i_next]
        
        bi1 = (inner_r * math.cos(a1), inner_r * math.sin(a1), floor_h)
        bi2 = (inner_r * math.cos(a2), inner_r * math.sin(a2), floor_h)
        sh1 = (speaker_hole_r * math.cos(a1), speaker_hole_r * math.sin(a1), floor_h)
        sh2 = (speaker_hole_r * math.cos(a2), speaker_hole_r * math.sin(a2), floor_h)
        
        # Floor facing +Z
        add_quad(facets, bi1, bi2, sh2, sh1)

    # 6. Speaker Hole Vertical Wall (between z=0 and z=floor_h)
    for i in range(segments):
        i_next = (i + 1) % segments
        a1, a2 = angles[i], angles[i_next]
        
        shb1 = (speaker_hole_r * math.cos(a1), speaker_hole_r * math.sin(a1), 0.0)
        shb2 = (speaker_hole_r * math.cos(a2), speaker_hole_r * math.sin(a2), 0.0)
        sht1 = (speaker_hole_r * math.cos(a1), speaker_hole_r * math.sin(a1), floor_h)
        sht2 = (speaker_hole_r * math.cos(a2), speaker_hole_r * math.sin(a2), floor_h)
        
        add_quad(facets, shb1, shb2, sht2, sht1)

    # 7. Add 4 Standoff Posts for Raspberry Pi 5 (58mm x 49mm)
    standoff_r = 3.0
    standoff_h = 6.0
    pi_x = 29.0
    pi_y = 24.5
    post_segs = 16
    
    for px in [-pi_x, pi_x]:
        for py in [-pi_y, pi_y]:
            post_base_z = floor_h
            post_top_z = floor_h + standoff_h
            
            p_angles = [2 * math.pi * j / post_segs for j in range(post_segs)]
            for j in range(post_segs):
                j_next = (j + 1) % post_segs
                pa1, pa2 = p_angles[j], p_angles[j_next]
                
                pb1 = (px + standoff_r * math.cos(pa1), py + standoff_r * math.sin(pa1), post_base_z)
                pb2 = (px + standoff_r * math.cos(pa2), py + standoff_r * math.sin(pa2), post_base_z)
                pt1 = (px + standoff_r * math.cos(pa1), py + standoff_r * math.sin(pa1), post_top_z)
                pt2 = (px + standoff_r * math.cos(pa2), py + standoff_r * math.sin(pa2), post_top_z)
                
                # Standoff wall
                add_quad(facets, pb1, pb2, pt2, pt1)
                
                # Standoff top cap
                center_top = (px, py, post_top_z)
                n = (0.0, 0.0, 1.0)
                facets.append((n, center_top, pt1, pt2))

    write_binary_stl(output_path, facets)
    print(f"Generated {output_path} with {len(facets)} triangular facets.")

if __name__ == "__main__":
    generate_speaker_housing_stl()
