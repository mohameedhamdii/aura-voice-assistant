"""
Generates the vector hardware wiring diagram for the Offline Voice Assistant.
Outputs both PDF (vector) and PNG formats in the hardware/ directory.
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def generate_diagram():
    output_dir = Path(__file__).parent.resolve()
    pdf_path = output_dir / "wiring_diagram.pdf"
    png_path = output_dir / "wiring_diagram.png"

    fig, ax = plt.subplots(figsize=(15, 10), dpi=300)
    fig.patch.set_facecolor("#111827")
    ax.set_facecolor("#111827")

    # Title
    ax.text(
        0.5, 0.96,
        "Offline Voice Assistant — Hardware Interconnect & Schematic Diagram",
        fontsize=16, fontweight="bold", color="#F9FAFB",
        ha="center", va="top", transform=ax.transAxes
    )
    ax.text(
        0.5, 0.93,
        "Raspberry Pi 5 + ReSpeaker 4-Mic HAT + MAX98357A I2S Amp + WS2812B LED Ring + ESP32-C6 Matter Bridge",
        fontsize=10, color="#9CA3AF",
        ha="center", va="top", transform=ax.transAxes
    )

    def draw_box(x, y, w, h, title, subtitle, color, text_color="#FFFFFF"):
        box = patches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.015,rounding_size=0.02",
            facecolor=color, edgecolor="#4B5563", linewidth=1.5,
            transform=ax.transAxes, zorder=2
        )
        ax.add_patch(box)
        ax.text(
            x + w/2, y + h - 0.035, title,
            fontsize=11, fontweight="bold", color=text_color,
            ha="center", va="top", transform=ax.transAxes, zorder=3
        )
        if subtitle:
            ax.text(
                x + w/2, y + h - 0.065, subtitle,
                fontsize=8, color="#D1D5DB",
                ha="center", va="top", transform=ax.transAxes, zorder=3
            )

    # 1. Central Raspberry Pi 5
    draw_box(0.35, 0.32, 0.30, 0.52, "Raspberry Pi 5 (8 GB)", "Core Edge Compute & ASR / LLM / TTS", "#1E293B")

    # Pi GPIO pins inside
    gpio_text = (
        "40-Pin Expansion Header (J8)\n"
        "───────────────────────────────\n"
        "Pin 02 / 04:  +5V Power Rail\n"
        "Pin 01 / 17:  +3.3V Power Rail\n"
        "Pin 06 / 09 / 14:  GND (Common)\n"
        "Pin 08:  GPIO 14 (UART0 TXD)\n"
        "Pin 10:  GPIO 15 (UART0 RXD)\n"
        "Pin 11:  GPIO 17 (Mute Button In)\n"
        "Pin 12:  GPIO 18 (PWM0 LED Data)\n"
        "Pin 35:  GPIO 19 (I2S PCM_CLK)\n"
        "Pin 38:  GPIO 20 (I2S PCM_DOUT)\n"
        "Pin 40:  GPIO 21 (I2S PCM_FS)\n"
        "Pin 03 / 05:  I2C SDA / SCL (HAT)"
    )
    ax.text(
        0.50, 0.69, gpio_text,
        fontsize=8.5, family="monospace", color="#E2E8F0",
        ha="center", va="top", transform=ax.transAxes, zorder=3
    )

    # 2. ReSpeaker 4-Mic Array (Top)
    draw_box(0.35, 0.86, 0.30, 0.055, "ReSpeaker 4-Mic Array HAT", "Stacked on GPIO (I2C + Far-field Audio ADC)", "#0F766E")

    # 3. MAX98357A I2S DAC Amp (Bottom-Left)
    draw_box(0.04, 0.42, 0.22, 0.34, "MAX98357A I²S DAC Amp", "Class-D Mono Amplifier 3.2W", "#374151")
    i2s_text = (
        "Pins:\n"
        " VIN   ◄ +5V (Pin 2)\n"
        " GND   ◄ GND (Pin 6)\n"
        " BCLK  ◄ GPIO 19 (Pin 35)\n"
        " LRC   ◄ GPIO 21 (Pin 40)\n"
        " DIN   ◄ GPIO 20 (Pin 38)\n"
        " GAIN  ◄ GND (9 dB gain)\n"
        " SPK+/- ► To 4Ω Speaker"
    )
    ax.text(0.15, 0.66, i2s_text, fontsize=8.5, family="monospace", color="#E5E7EB", ha="center", va="top", transform=ax.transAxes, zorder=3)

    # 4. Speaker Driver (Far Left)
    draw_box(0.04, 0.16, 0.22, 0.18, "Dayton Audio Speaker", "4 Ω / 3 W RMS Full-Range", "#1F2937")
    spk_text = "Terminals:\n SPK+ (Red)\n SPK- (Black)\n Acoustic Back Chamber"
    ax.text(0.15, 0.26, spk_text, fontsize=8.5, family="monospace", color="#93C5FD", ha="center", va="top", transform=ax.transAxes, zorder=3)

    # 5. WS2812B 12-LED Ring (Right Top)
    draw_box(0.74, 0.60, 0.22, 0.24, "WS2812B 12-LED Ring", "50mm OD Status Ring", "#4C1D95")
    led_text = (
        "Connections:\n"
        " 5V  ◄ +5V via 1N4001\n"
        " GND ◄ GND (Pin 14)\n"
        " DI  ◄ GPIO 18 (PWM0)\n"
        " 470µF Filter Cap"
    )
    ax.text(0.85, 0.74, led_text, fontsize=8.5, family="monospace", color="#F472B6", ha="center", va="top", transform=ax.transAxes, zorder=3)

    # 6. ESP32-C6 Matter Bridge (Right Bottom)
    draw_box(0.74, 0.25, 0.22, 0.28, "ESP32-C6 Matter Bridge", "Thread / BLE / Zigbee Mesh", "#1E3A8A")
    esp_text = (
        "Serial Interface:\n"
        " 5V  ◄ +5V (Pin 4)\n"
        " GND ◄ GND (Pin 9)\n"
        " RXD ◄ GPIO 14 (TXD0)\n"
        " TXD ► GPIO 15 (RXD0)\n"
        " Protocol: 115200 baud\n"
        " JSON Line Commands"
    )
    ax.text(0.85, 0.43, esp_text, fontsize=8.5, family="monospace", color="#93C5FD", ha="center", va="top", transform=ax.transAxes, zorder=3)

    # 7. Hardware Mute Button (Bottom Center)
    draw_box(0.38, 0.12, 0.24, 0.14, "Privacy Mute Push Button", "12mm Momentary Tactile Switch", "#831843")
    btn_text = "Pin 1 ──► GPIO 17 (Pin 11)\nPin 2 ──► Ground (Pin 9)\n100nF HW Debounce Cap"
    ax.text(0.50, 0.19, btn_text, fontsize=8.5, family="monospace", color="#FBCFE8", ha="center", va="top", transform=ax.transAxes, zorder=3)

    # Connecting Arrows
    def draw_arrow(x1, y1, x2, y2, color, label=""):
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1),
            xycoords="axes fraction", textcoords="axes fraction",
            arrowprops=dict(arrowstyle="->", color=color, lw=2.0, shrinkA=4, shrinkB=4)
        )
        if label:
            mx, my = (x1 + x2)/2, (y1 + y2)/2
            ax.text(mx, my + 0.015, label, fontsize=8, color=color, fontweight="bold", ha="center", va="bottom", transform=ax.transAxes, zorder=4)

    # ReSpeaker HAT connection
    draw_arrow(0.50, 0.84, 0.50, 0.86, "#2DD4BF", "GPIO Header")

    # Amp connections
    draw_arrow(0.35, 0.55, 0.26, 0.55, "#38BDF8", "I2S Signals")
    draw_arrow(0.15, 0.42, 0.15, 0.34, "#F59E0B", "Audio Output")

    # LED connection
    draw_arrow(0.65, 0.68, 0.74, 0.68, "#E879F9", "PWM Data + 5V")

    # ESP32 connection
    draw_arrow(0.65, 0.40, 0.74, 0.40, "#60A5FA", "UART TX/RX")

    # Mute Button connection
    draw_arrow(0.50, 0.32, 0.50, 0.26, "#F43F5E", "GPIO 17 Sense")

    # Legend at bottom
    legend_text = (
        "Color Code:  ■ Power (+5V/+3.3V)   ■ Ground (GND)   ■ I2S PCM Audio   "
        "■ UART Serial   ■ WS2812B PWM   ■ Control GPIO"
    )
    ax.text(0.5, 0.03, legend_text, fontsize=9, color="#9CA3AF", ha="center", va="center", transform=ax.transAxes)

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    plt.tight_layout()
    plt.savefig(pdf_path, format="pdf", bbox_inches="tight")
    plt.savefig(png_path, format="png", bbox_inches="tight")
    plt.close()
    print(f"Generated {pdf_path} and {png_path}")

if __name__ == "__main__":
    generate_diagram()
