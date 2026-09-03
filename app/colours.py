"""
The fixed palette of selectable site colours, grouped for display in the
colour-picker dialog. Each swatch's hex is the actual (or closely
approximated) paint colour hex.
"""

COLOUR_GROUPS = [
    {
        "label": "Earthy & Nature Tones",
        "swatches": [
            {"id": "jitney", "name": "Jitney", "brand": "Farrow & Ball", "hex": "#C4B2A2"},
            {"id": "tuscan-glaze", "name": "Tuscan Glaze", "brand": "Dulux Heritage", "hex": "#C9906F"},
            {"id": "french-gray", "name": "French Gray", "brand": "Farrow & Ball", "hex": "#B5B19A"},
            {"id": "olive-colour", "name": "Olive Colour", "brand": "Little Greene", "hex": "#626446"},
        ],
    },
    {
        "label": "Soothing Neutrals & Warm Greys",
        "swatches": [
            {"id": "slaked-lime", "name": "Slaked Lime", "brand": "Little Greene", "hex": "#F0F1EC"},
            {"id": "skimming-stone", "name": "Skimming Stone", "brand": "Farrow & Ball", "hex": "#DFD6CB"},
            {"id": "pebble-grey", "name": "Pebble Grey", "brand": "Dulux", "hex": "#CFCAC1"},
            {"id": "portland-stone", "name": "Portland Stone", "brand": "Little Greene", "hex": "#C9C5A8"},
        ],
    },
    {
        "label": "Soft Dusk Shades",
        "swatches": [
            {"id": "sulking-room-pink", "name": "Sulking Room Pink", "brand": "Farrow & Ball", "hex": "#A0837F"},
            {"id": "pigeon", "name": "Pigeon", "brand": "Farrow & Ball", "hex": "#A1A093"},
        ],
    },
]

# Flat lookup: id -> swatch dict, and a set of valid hex codes for validation.
COLOURS_BY_ID = {
    swatch["id"]: swatch
    for group in COLOUR_GROUPS
    for swatch in group["swatches"]
}
VALID_HEXES = {swatch["hex"] for swatch in COLOURS_BY_ID.values()}

DEFAULT_COLOUR_ID = "jitney"