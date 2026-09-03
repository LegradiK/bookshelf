"""
Small hex-colour helpers so the whole site's palette (primary, primary-dark,
tint, tint-secondary) can be derived from a single chosen paint colour,
instead of hand-picking a palette per swatch.
"""


def _clamp(value: float) -> int:
    return max(0, min(255, round(value)))


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(_clamp(c) for c in rgb))


def darken(hex_color: str, amount: float = 0.4) -> str:
    """Move the colour toward black by `amount` (0-1)."""
    r, g, b = hex_to_rgb(hex_color)
    return rgb_to_hex((r * (1 - amount), g * (1 - amount), b * (1 - amount)))


def lighten(hex_color: str, amount: float = 0.6) -> str:
    """Move the colour toward white by `amount` (0-1)."""
    r, g, b = hex_to_rgb(hex_color)
    return rgb_to_hex((
        r + (255 - r) * amount,
        g + (255 - g) * amount,
        b + (255 - b) * amount,
    ))


def site_palette(base_hex: str) -> dict[str, str]:
    """Derive the full set of CSS custom property values from one base hex."""
    return {
        "primary": base_hex,
        "primary_dark": darken(base_hex, 0.42),
        "secondary": darken(base_hex, 0.15),
        "secondary_dark": darken(base_hex, 0.45),
        "tint": lighten(base_hex, 0.78),
        "tint_secondary": lighten(base_hex, 0.88),
    }