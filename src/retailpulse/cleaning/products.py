from __future__ import annotations

import re

import pandas as pd

from retailpulse.cleaning.rules import EXCLUDED

UNCATEGORISED = "Other"

# Ordered: the first matching rule wins, so specific themes precede generic ones.
CATEGORY_KEYWORDS: dict[str, str] = {
    "Seasonal & Party": (
        "CHRISTMAS XMAS EASTER ADVENT SANTA REINDEER HALLOWEEN PARTY BIRTHDAY BUNTING BALLOON "
        "CRACKER CRACKERS"
    ),
    "Bags & Storage": (
        "BAG BAGS SHOPPER TOTE BASKET BASKETS BOX BOXES TIN TINS STORAGE CRATE DRAWER CABINET "
        "SUITCASE LUGGAGE PURSE WALLET"
    ),
    "Kitchen & Dining": (
        "MUG MUGS CUP CUPS TEA TEAPOT COFFEE PLATE PLATES BOWL BOWLS CAKE CAKES CAKESTAND "
        "BAKING JAR JARS KITCHEN CUTLERY NAPKINS TRAY COASTER COASTERS BOTTLE APRON JUG GLASS "
        "GLASSES SPOON SPOONS FORK PANTRY EGG JAM RECIPE OVEN PLACEMATS DISH BREAD MOULD "
        "MOULDS CUTTERS LUNCH SNACK MILK SUGAR CHOPSTICKS TOAST TEACUP SAUCER BEAKER COOKIE "
        "PAN"
    ),
    "Stationery & Gift Wrap": (
        "CARD CARDS WRAP NOTEBOOK NOTEBOOKS PENCIL PENCILS PEN PENS STICKER STICKERS PAPER "
        "RIBBON RIBBONS TAPE TAG TAGS JOURNAL ENVELOPE ENVELOPES RULER ERASER ERASERS "
        "CALENDAR ORGANISER BOOK STAMP CHALK CRAYONS SKETCHBOOK PASSPORT DIARY POSTCARD"
    ),
    "Toys & Kids": (
        "TOY TOYS GAME GAMES DOLL DOLLS DOLLY CHILDREN CHILDRENS CHILDS KIDS PLAYHOUSE "
        "SKITTLES JIGSAW PUZZLE PUZZLES SPACEBOY BABY TEDDY ROCKING SKIPPING MARBLES DOMINOES "
        "PLAYING CIRCUS SOLDIER ROBOT HELICOPTER BINGO LUDO BLOCKS NURSERY FELTCRAFT SEWING "
        "KNITTING PAINT COLOURING CLAY GLIDERS SPINNING"
    ),
    "Fashion & Accessories": (
        "NECKLACE BRACELET EARRINGS RING BROOCH HAIR HAIRCLIP SCARF UMBRELLA GLOVES HAT "
        "JEWELLERY BANGLE BEADS SLIPPERS SOCKS KEYRING KEY SUNGLASSES LARIAT HANDBAG PONCHO "
        "RAINCOAT CHARM"
    ),
    "Garden & Outdoor": (
        "GARDEN GARDENERS PLANT PLANTER WATERING PICNIC BIRD FEEDER FLOWER FLOWERPOT SEEDS "
        "HERB PARASOL HAMMOCK TORCH BICYCLE CAMPING WINDMILL TRELLIS GNOME"
    ),
    "Home Decor": (
        "HEART HEARTS HOLDER HOLDERS CANDLE CANDLES T-LIGHT T-LIGHTS LANTERN LANTERNS FRAME "
        "FRAMES CLOCK MIRROR CUSHION DOORMAT SIGN HOOK HOOKS WREATH DECORATION DECORATIONS "
        "GARLAND LIGHTS LIGHT LAMP VASE ORNAMENT ORNAMENTS WALL DOOR DOORSTOP RUG QUILT THROW "
        "BLANKET TOWEL INCENSE HANGING HANGER CHANDELIER KNOB COVER WICKER STAR BELL BELLS "
        "MAGNETS ALARM WARMER BOTTLES NIGHT BATHROOM SOAP PHOTO CHIME MOBILE BLACKBOARD "
        "MEMOBOARD BOARD CHALKBOARD RACK CHEST MAT CANDLEHOLDER DRAWERKNOB STOOL"
    ),
}

_COMPILED_RULES = tuple(
    (
        category,
        re.compile(r"(?<![A-Z])(?:" + "|".join(map(re.escape, keywords.split())) + r")(?![A-Z])"),
    )
    for category, keywords in CATEGORY_KEYWORDS.items()
)


def categorise(description: object) -> str:
    """Assign a derived product category from keywords in the product description."""
    if pd.isna(description):
        return UNCATEGORISED
    text = str(description).upper()
    for category, pattern in _COMPILED_RULES:
        if pattern.search(text):
            return category
    return UNCATEGORISED


def build_products(transactions: pd.DataFrame) -> pd.DataFrame:
    """Build one row per stock code with its most frequent description and derived category."""
    valid = transactions[transactions["line_type"] != EXCLUDED]
    codes = pd.DataFrame({"stock_code": valid["stock_code"].drop_duplicates()})
    counts = (
        valid.dropna(subset=["description"])
        .groupby(["stock_code", "description"], observed=True)
        .size()
        .reset_index(name="lines")
        .sort_values(["stock_code", "lines", "description"], ascending=[True, False, True])
    )
    names = counts.drop_duplicates("stock_code")[["stock_code", "description"]]
    products = codes.merge(names, on="stock_code", how="left")
    products["description"] = products["description"].astype("string")
    products["category"] = products["description"].map(categorise).astype("string")
    return products.sort_values("stock_code").reset_index(drop=True)
