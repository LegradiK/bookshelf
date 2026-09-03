"""
The fixed palette of selectable site colours, grouped for display in the
colour-picker dialog. Each swatch's hex is the actual (or closely
approximated) paint colour hex.
"""

COLOUR_GROUPS = [
    {
        "label": "Coffee & Earth Tones",
        "swatches": [
            {"id": "coffee", "name": "Coffee", "brand": "House blend", "hex": "#6F4E37"},
            {"id": "fox-red", "name": "Fox Red", "brand": "Farrow & Ball", "hex": "#A24B36"},
            {"id": "india-yellow", "name": "India Yellow", "brand": "Farrow & Ball", "hex": "#CB9E59"},
            {"id": "bancha", "name": "Bancha", "brand": "Farrow & Ball", "hex": "#686A47"},
        ],
    },
    {
        "label": "Bold Neutrals",
        "swatches": [
            {"id": "slaked-lime", "name": "Slaked Lime", "brand": "Little Greene", "hex": "#F0F1EC"},
            {"id": "portland-stone", "name": "Portland Stone", "brand": "Little Greene", "hex": "#C9C5A8"},
            {"id": "railings", "name": "Railings", "brand": "Farrow & Ball", "hex": "#45484B"},
        ],
    },
    {
        "label": "Statement Accents",
        "swatches": [
            {"id": "stiffkey-blue", "name": "Stiffkey Blue", "brand": "Farrow & Ball", "hex": "#4D5B6A"},
            {"id": "sulking-room-pink", "name": "Sulking Room Pink", "brand": "Farrow & Ball", "hex": "#A0837F"},
            {"id": "brinjal", "name": "Brinjal", "brand": "Farrow & Ball", "hex": "#5A4348"},
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

# The site's default colour before anyone has opened the picker and chosen
# one of the named paint swatches above. Not one of the selectable swatches
# itself — just the starting coffee-brown accent.
DEFAULT_HEX = "#6F4E37"