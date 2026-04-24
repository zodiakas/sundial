#!/usr/bin/env python3
"""Cylindrical 'valley dial' SVG generator.

This version replaces the traditional declination (and optionally EOT) approximation
with NOAA's 'General Solar Position Calculations' declination model.

Sources:
- NOAA GML solar equations (declination + equation of time)
  https://gml.noaa.gov/grad/solcalc/solareqns.PDF

Notes
-----
- day_of_year is treated as 1..365 (non‑leap year). For convenience, this script
  will accept 0..365 too and internally convert via (n = day+1).
- The output is an SVG sized to A4 landscape (297×210 mm).
"""

import math

A4_W_MM, A4_H_MM = 297.0, 210.0

# Default location: Vilnius 
# Coordinates source: ~54.71, 25.29
VILNIUS_LAT_DEG = 54.71
VILNIUS_LON_DEG = 25.29
# Standard time requirement:
# Lithuania standard time is EET (UTC+02:00). For zone time the reference meridian is 30°E.
# This dial is configured to SHOW STANDARD TIME (EET) year-round (no DST applied).
VILNIUS_STANDARD_MERIDIAN_DEG = 30.0
# If you *do* compare with summer time (EEST, UTC+03:00), add +1 hour to the reading manually.


def solar_params_noaa(day_of_year, hour=12.0):
    """Return (declination_rad, equation_of_time_min) using NOAA approximation.

    Parameters
    ----------
    day_of_year : int
        Day number in [1, 365]. If 0..365 is passed, it's interpreted as 0-based
        and converted to 1-based by adding 1.
    hour : float
        Local clock hour used in NOAA fractional-year gamma term.
        (We keep default 12.0, matching the 'daily' usage.)
    """
    # Allow 0-based input
    if day_of_year <= 0:
        n = int(day_of_year) + 1
    else:
        n = int(day_of_year)

    # NOAA: fractional year gamma (radians)
    gamma = 2.0 * math.pi / 365.0 * (n - 1 + (hour - 12.0) / 24.0)

    # NOAA: equation of time (minutes)
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2.0 * gamma)
        - 0.040849 * math.sin(2.0 * gamma)
    )

    # NOAA: solar declination (radians)
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2.0 * gamma)
        + 0.000907 * math.sin(2.0 * gamma)
        - 0.002697 * math.cos(3.0 * gamma)
        + 0.00148 * math.sin(3.0 * gamma)
    )

    return decl, eqtime


def svg_header(width_mm, height_mm):
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm}mm" height="{height_mm}mm" viewBox="0 0 {width_mm} {height_mm}">',
        '<style>',
        '  .small { font: 3.5px sans-serif; fill: #111; }',
        '  .label { font: 4.2px sans-serif; fill: #111; }',
        '  .thin { stroke: #111; stroke-width: 0.25; fill: none; }',
        '  .hair { stroke: #111; stroke-width: 0.18; fill: none; }',
        '</style>',
    ]


def svg_footer():
    return ['</svg>']


def generate_true_valley_dial(
    lat_deg,
    lon_deg,
    meridian_deg,
    diameter_mm,
    height_mm,
    filename="valley_dial_vilnius_noaa.svg",
):
    """Generate a cylindrical valley dial SVG.

    Parameters match the original script's intent.
    - lat_deg: geographic latitude
    - lon_deg: geographic longitude (degrees east positive)
    - meridian_deg: standard meridian of the time zone (e.g., 15° for UTC+1)
    - diameter_mm: cylinder diameter (controls wrap width)
    - height_mm: dial scale height (cylinder height)
    """

    LAT = math.radians(lat_deg)
    circumference = math.pi * float(diameter_mm)

    offset_x = (A4_W_MM - circumference) / 2.0
    offset_y = (A4_H_MM - float(height_mm)) / 2.0

    # Choose summer solstice-ish day for scaling gnomon length
    # (Using day 172, as in the original.)
    decl_sum, _ = solar_params_noaa(172, hour=12.0)
    alt_sum = math.asin(
        math.sin(LAT) * math.sin(decl_sum)
        + math.cos(LAT) * math.cos(decl_sum)
    )

    # gnomon length so that summer-noon drop is ~80% of height
    gnomon_length = (float(height_mm) * 0.8) / math.tan(alt_sum)

    svg = []
    svg += svg_header(A4_W_MM, A4_H_MM)

    # Border for the dial area
    svg.append(
        f'<rect x="{offset_x:.2f}" y="{offset_y:.2f}" width="{circumference:.2f}" height="{float(height_mm):.2f}" class="thin"/>'
    )

    # Month labels and day tick marks (1, 11, 21)
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    month_lengths = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    curr_day0 = 0  # 0-based day index

    for name, mlen in zip(month_names, month_lengths):
        x = offset_x + (curr_day0 / 365.0) * circumference
        svg.append(f'<text x="{x:.2f}" y="{(offset_y - 2.0):.2f}" class="label">{name}</text>')

        for dom in (1, 11, 21):
            day0 = curr_day0 + (dom - 1)
            dx = offset_x + (day0 / 365.0) * circumference
            svg.append(f'<line x1="{dx:.2f}" y1="{offset_y:.2f}" x2="{dx:.2f}" y2="{(offset_y + float(height_mm)):.2f}" class="hair"/>')
            svg.append(f'<text x="{(dx + 0.6):.2f}" y="{(offset_y + 4.2):.2f}" class="small">{dom}</text>')

        curr_day0 += mlen

    # Hour lines (clock time) with correction to apparent solar time:
    # long_corr = 4*(lon - meridian) minutes
    long_corr = 4.0 * (float(lon_deg) - float(meridian_deg))

    for hour in range(5, 21):
        points = []

        for day0 in range(0, 366):
            # Convert 0-based to NOAA day-of-year (1..365) by adding 1.
            # Clamp day0==365 to 365 to avoid n=366 in a non-leap model.
            n = min(day0 + 1, 365)
            decl, eot = solar_params_noaa(n, hour=12.0)

            solar_time = hour + (eot + long_corr) / 60.0
            h_angle = math.radians((solar_time - 12.0) * 15.0)

            sin_alt = (
                math.sin(LAT) * math.sin(decl)
                + math.cos(LAT) * math.cos(decl) * math.cos(h_angle)
            )

            # Only plot when Sun is above horizon (simple cutoff)
            if sin_alt > 0.02:
                alt = math.asin(sin_alt)
                vertical_drop = gnomon_length * math.tan(alt)

                if vertical_drop < float(height_mm):
                    x = offset_x + (day0 / 365.0) * circumference
                    y = offset_y + vertical_drop
                    points.append((x, y))
                else:
                    # If we exceeded height, break the polyline segment
                    if len(points) > 1:
                        pts = " ".join(f"{px:.2f},{py:.2f}" for px, py in points)
                        svg.append(f'<polyline points="{pts}" class="thin"/>')
                    points = []
            else:
                if len(points) > 1:
                    pts = " ".join(f"{px:.2f},{py:.2f}" for px, py in points)
                    svg.append(f'<polyline points="{pts}" class="thin"/>')
                points = []

        # Flush last segment
        if len(points) > 1:
            pts = " ".join(f"{px:.2f},{py:.2f}" for px, py in points)
            svg.append(f'<polyline points="{pts}" class="thin"/>')

        # Hour label near mid-year, if the point exists
        mid_day0 = 182
        nmid = mid_day0 + 1
        decl_mid, eot_mid = solar_params_noaa(nmid, hour=12.0)
        solar_time_mid = hour + (eot_mid + long_corr) / 60.0
        h_angle_mid = math.radians((solar_time_mid - 12.0) * 15.0)
        sin_alt_mid = (
            math.sin(LAT) * math.sin(decl_mid)
            + math.cos(LAT) * math.cos(decl_mid) * math.cos(h_angle_mid)
        )
        if sin_alt_mid > 0.02:
            alt_mid = math.asin(sin_alt_mid)
            drop_mid = gnomon_length * math.tan(alt_mid)
            if drop_mid < float(height_mm):
                lx = offset_x + (mid_day0 / 365.0) * circumference
                ly = offset_y + drop_mid
                svg.append(f'<text x="{(lx + 1.2):.2f}" y="{(ly - 0.8):.2f}" class="small">{hour}</text>')

    # Info text
    svg.append(
        f'<text x="{offset_x:.2f}" y="{(offset_y + float(height_mm) + 6.0):.2f}" class="label">'
        f'Horizontal gnomon length: {gnomon_length:.2f} mm (NOAA declination) — Time scale: EET (UTC+2)' 
        f'</text>'
    )
    svg.append(
        f'<text x="{offset_x:.2f}" y="{(offset_y + float(height_mm) + 12.0):.2f}" class="small">'
        f'Mount gnomon at the TOP border line' 
        f'</text>'
    )

    svg += svg_footer()

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))


if __name__ == "__main__":
    # Example run (same params as the original script)
    generate_true_valley_dial(
        lat_deg=VILNIUS_LAT_DEG,
        lon_deg=VILNIUS_LON_DEG,
        meridian_deg=VILNIUS_STANDARD_MERIDIAN_DEG,
        diameter_mm=90,
        height_mm=100,
        filename="valley_dial_vilnius_noaa.svg",
    )
