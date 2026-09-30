# 3D Printable Smart Speaker Enclosure

This directory contains the 3D model and specifications for the smart-speaker cylindrical enclosure.

---

## 1. Specifications & Geometry

| Parameter | Value |
|---|---|
| **Form Factor** | Modern Cylindrical Smart Speaker |
| **Outer Diameter** | 92 mm |
| **Total Height** | 135 mm |
| **Wall Thickness** | 3.0 mm (high acoustic damping) |
| **Bottom Chamber** | Downward-firing 45 mm speaker driver chamber with radial acoustic ports |
| **Mid Section** | Raspberry Pi 5 horizontal mounting plate with 4x M2.5 brass heat-set insert standoffs (58 mm × 49 mm) |
| **Rear I/O Cutout** | USB-C power port (14 mm × 8 mm) and ventilation intake |
| **Top Ring Collar** | Recessed mounting seat for WS2812B 12-LED ring (50 mm outer diameter, 37 mm inner diameter) |
| **Top Cap / Diffuser** | Frosted acrylic disc or natural PLA diffuser ring (0.8 mm thickness) for diffused LED glow |
| **Microphone Clearance**| 4x peripheral ports aligned with ReSpeaker 4-Mic Array MEMS mics |

---

## 2. Print Settings & Slicer Recommendations

| Slicer Setting | Recommended Value | Note |
|---|---|---|
| **Material** | PLA, PETG, or Matte PLA | Matte PLA or PETG provides superior aesthetics and vibration damping |
| **Layer Height** | 0.20 mm (or 0.16 mm Adaptive) | Balances print speed and smooth curvature |
| **Perimeters / Walls** | 4 walls (1.6 mm) | Crucial for acoustic isolation and rigidity |
| **Top / Bottom Layers**| 5 layers | Eliminates light bleeding from LEDs and seals acoustic chamber |
| **Infill Density** | 25% | Gyroid or Honeycomb pattern prevents acoustic resonance |
| **Supports** | Tree / Organic supports | Only required under the rear USB-C port cutout |
| **Print Orientation** | Upright (bottom chamber flat on build plate) | No brim needed on PEI sheet |

---

## 3. Files in this Directory

- `speaker_housing.stl`: Ready-to-slice 3D mesh for 3D printers.
- `speaker_housing.scad`: Parametric OpenSCAD design file for CAD modifications.
- `generate_stl.py`: Mathematical geometry generator script used to compile the STL binary.
