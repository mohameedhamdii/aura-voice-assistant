// ============================================================================
// speaker_housing.scad — Parametric 3D Printable Smart Speaker Enclosure
// ============================================================================
// Designed for:
//   - Raspberry Pi 5 (8 GB) + Active Cooler
//   - ReSpeaker 4-Mic Array HAT
//   - Dayton Audio DMA45-4 / 45mm 3W Speaker Driver (downward firing)
//   - WS2812B 12-LED Neopixel Ring (50mm OD)
//   - MAX98357A I2S DAC Amp & ESP32-C6
// ============================================================================

$fn = 120; // Smooth radial curves

// Global Dimensions
outer_diameter   = 92.0;
inner_diameter   = 86.0; // 3mm wall thickness
total_height     = 135.0;

// Acoustic Base & Speaker Chamber
speaker_hole_dia = 46.0; // 45mm driver seat
acoustic_h       = 32.0;
port_count       = 8;
port_width       = 5.0;
port_height      = 12.0;

// Pi 5 Standoffs (58mm x 49mm rectangle)
pi_hole_x        = 58.0;
pi_hole_y        = 49.0;
pi_standoff_h    = 6.0;
pi_standoff_dia  = 6.0;
pi_screw_hole    = 2.8;  // M2.5 brass heat-set insert

// Top LED Ring Collar
led_ring_od      = 52.0;
led_ring_id      = 36.0;
led_collar_depth = 4.0;

module speaker_housing() {
    difference() {
        // Main Outer Cylinder with chamfered bottom rim
        union() {
            cylinder(d=outer_diameter, h=total_height);
        }

        // Inner Main Cavity
        translate([0, 0, 4.0])
            cylinder(d=inner_diameter, h=total_height);

        // Bottom Speaker Sound Port (Downward firing)
        translate([0, 0, -1])
            cylinder(d=speaker_hole_dia, h=6.0);

        // Speaker driver screw mount holes (4x M3 @ 52mm PCD)
        for (a = [45, 135, 225, 315]) {
            rotate([0, 0, a])
                translate([26.0, 0, -1])
                    cylinder(d=3.2, h=8.0);
        }

        // Radial Acoustic Bass Ports around lower rim
        for (i = [0 : port_count - 1]) {
            rotate([0, 0, i * (360 / port_count)])
                translate([outer_diameter / 2 - 4, -port_width / 2, 8])
                    cube([8, port_width, port_height]);
        }

        // Rear USB-C & Power Access Port
        translate([outer_diameter / 2 - 6, -8, 45])
            cube([12, 16, 10]);

        // Top Recessed Seat for WS2812B 12-LED Ring
        translate([0, 0, total_height - led_collar_depth])
            difference() {
                cylinder(d=led_ring_od + 1.0, h=led_collar_depth + 1);
                cylinder(d=led_ring_id - 1.0, h=led_collar_depth + 2);
            }

        // Top Microphone Acoustic Vents (4x MEMS mic holes)
        for (a = [0, 90, 180, 270]) {
            rotate([0, 0, a])
                translate([32.0, 0, total_height - 10])
                    cylinder(d=2.5, h=15);
        }
    }

    // Internal Pi 5 Standoff Posts with M2.5 screw bosses
    translate([0, 0, acoustic_h]) {
        for (dx = [-pi_hole_x / 2, pi_hole_x / 2]) {
            for (dy = [-pi_hole_y / 2, pi_hole_y / 2]) {
                translate([dx, dy, 0])
                    difference() {
                        cylinder(d=pi_standoff_dia, h=pi_standoff_h);
                        translate([0, 0, 1])
                            cylinder(d=pi_screw_hole, h=pi_standoff_h + 1);
                    }
            }
        }
    }
}

// Render housing
speaker_housing();
