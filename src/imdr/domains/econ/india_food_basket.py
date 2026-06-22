"""Curated India CPI fresh-food basket — mandi-commodity → CPI sub-group mapping.

The reference artifact for the India fresh-food inflation nowcaster
(see docs/admin/research/india_food_nowcast_spec.md). It strips the volatile,
mandi-observable slice of the CPI food basket — Vegetables + Fruits + Spices —
out of the full Agmarknet commodity universe, drops grains / pulses / oilseeds
(slow movers, by design) and the substantial non-food noise (firewood, flowers,
livestock, industrial/medicinal crops).

Built by evaluating the live ``econ.dim_india_mandi_commodity`` content
(248 distinct commodities loaded 2026-06, data.gov.in OGD resource 35985678).
Names below are the EXACT raw Agmarknet ``Commodity`` strings, so they double as
the API ``filters[Commodity]`` values for the commodity-scoped fetch.

CPI weights are the 2012-base sub-group shares of *total* CPI (the 2024-base
sub-item detail is not yet published by MoSPI). Within-sub-group commodity
weights are assigned at aggregation time (see the spec); this module only
fixes the sub-group membership + the coverage tier.

Tier (by # reporting markets on a normal day):
  A  >= 150 markets  — composite spine (robust national median)
  B  50-150          — supporting (stored; in composite when coverage holds)
  C  < 50            — long tail (stored, NOT in the headline composite)

NB: this module is pure reference data — no DB, no network, no side effects.
"""
from __future__ import annotations

# CPI 2012-base sub-group weights — % of TOTAL CPI (Combined).
CPI_SUBGROUP_WEIGHT_PCT: dict[str, float] = {
    "vegetables": 6.04,
    "fruits": 2.89,
    "spices": 2.50,
}

# Headline trio — the bulk of vegetable-inflation volatility.
TOP = ("Onion", "Potato", "Tomato")

# ---------------------------------------------------------------------------
# FOCUS — kept + fetched. (canonical_raw_name, sub_group, tier)
# canonical_raw_name is the exact Agmarknet Commodity string.
# ---------------------------------------------------------------------------
FOCUS: list[tuple[str, str, str]] = [
    # ----- VEGETABLES (CPI 6.04%) -----
    ("Onion", "vegetables", "A"),
    ("Potato", "vegetables", "A"),
    ("Tomato", "vegetables", "A"),
    ("Brinjal", "vegetables", "A"),
    ("Bhindi(Ladies Finger)", "vegetables", "A"),
    ("Cucumbar(Kheera)", "vegetables", "A"),
    ("Cabbage", "vegetables", "A"),
    ("Bitter gourd", "vegetables", "A"),
    ("Bottle gourd", "vegetables", "A"),
    ("Pumpkin", "vegetables", "A"),
    ("Cauliflower", "vegetables", "A"),
    ("Ridgeguard(Tori)", "vegetables", "A"),
    ("Carrot", "vegetables", "A"),
    ("Beetroot", "vegetables", "A"),
    ("Snakeguard", "vegetables", "A"),
    ("Raddish", "vegetables", "A"),
    ("Drumstick", "vegetables", "A"),
    ("Ashgourd", "vegetables", "A"),
    ("Capsicum", "vegetables", "A"),
    ("Cluster beans", "vegetables", "A"),
    ("Beans", "vegetables", "A"),
    ("Green Avare(W)", "vegetables", "A"),
    ("Onion Green", "vegetables", "A"),
    ("Banana - Green", "vegetables", "A"),       # cooking/raw banana — veg use
    ("Mango(Raw-Ripe)", "vegetables", "A"),      # raw mango — veg/pickle use
    ("Colacasia", "vegetables", "B"),
    ("Elephant Yam(Suran)/Amorphophallus", "vegetables", "B"),
    ("Chow Chow", "vegetables", "B"),
    ("Cowpea(Veg)", "vegetables", "B"),
    ("Sweet Potato", "vegetables", "B"),
    ("Thondekai", "vegetables", "B"),
    ("Tapioca", "vegetables", "B"),
    ("Knool Khol", "vegetables", "B"),
    ("Yam(Ratalu)", "vegetables", "B"),
    ("Pointed gourd(Parval)", "vegetables", "B"),
    ("Little gourd(Kundru)", "vegetables", "B"),
    ("Spinach", "vegetables", "B"),
    ("French Beans(Frasbean)", "vegetables", "B"),
    ("Green Peas", "vegetables", "C"),
    ("Sponge gourd", "vegetables", "C"),
    ("Sweet Pumpkin", "vegetables", "C"),
    ("Peas Wet", "vegetables", "C"),
    ("Tinda", "vegetables", "C"),
    ("Gram Raw(Chholia)", "vegetables", "C"),    # fresh green chickpea — veg
    ("Indian Beans(Seam)", "vegetables", "C"),
    ("Squash(Chappal Kadoo)", "vegetables", "C"),
    ("Mashrooms", "vegetables", "C"),
    ("Long Melon(Kakri)", "vegetables", "C"),
    ("Leafy Vegetable", "vegetables", "C"),
    ("Pegeon Pea(Arhar Fali)", "vegetables", "C"),  # fresh tur pods — veg
    ("Papaya(Raw)", "vegetables", "C"),
    ("Cowpea(Lobia/Karamani)", "vegetables", "C"),
    ("Round gourd", "vegetables", "C"),
    ("Turnip", "vegetables", "C"),
    ("Spiny Gourd / Kartali(Kantola)", "vegetables", "C"),
    ("Methi(Leaves)", "vegetables", "C"),
    ("Amranthas Red", "vegetables", "C"),

    # ----- FRUITS (CPI 2.89%) -----
    ("Banana", "fruits", "A"),
    ("Mango", "fruits", "A"),
    ("Papaya", "fruits", "A"),
    ("Lemon", "fruits", "A"),
    ("Amla(Nelli Kai)", "fruits", "B"),
    ("Guava", "fruits", "B"),
    ("Apple", "fruits", "B"),
    ("Pomegranate", "fruits", "B"),
    ("Water Melon", "fruits", "B"),
    ("Karbuja(Musk Melon)", "fruits", "B"),
    ("Tender Coconut", "fruits", "B"),
    ("Mousambi(Sweet Lime)", "fruits", "B"),
    ("Lime", "fruits", "B"),
    ("Pineapple", "fruits", "B"),
    ("Chikoos(Sapota)", "fruits", "B"),
    ("Jack Fruit(Ripe)", "fruits", "C"),
    ("Plum", "fruits", "C"),
    ("Grapes", "fruits", "C"),
    ("Orange", "fruits", "C"),
    ("Litchi", "fruits", "C"),
    ("Jamun(Narale Hannu)", "fruits", "C"),
    ("Peach", "fruits", "C"),
    ("Apricot(Jardalu/Khumani)", "fruits", "C"),
    ("Pear(Marasebu)", "fruits", "C"),
    ("Cherry", "fruits", "C"),
    ("Custard Apple(Sharifa)", "fruits", "C"),
    ("Kinnow", "fruits", "C"),
    ("Fig(Anjura/Anjeer)", "fruits", "C"),

    # ----- SPICES (CPI 2.50%) -----
    ("Green Chilli", "spices", "A"),             # CPI files green chilli under spices
    ("Ginger(Green)", "spices", "A"),
    ("Garlic", "spices", "A"),
    ("Coriander(Leaves)", "spices", "A"),
    ("Mint(Pudina)", "spices", "B"),
    ("Turmeric", "spices", "C"),
    ("Turmeric(raw)", "spices", "C"),
    ("Corriander seed", "spices", "C"),          # (sic — Agmarknet spelling)
    ("Cummin Seed(Jeera)", "spices", "C"),
    ("Methi Seeds", "spices", "C"),
    ("Dry Chillies", "spices", "C"),
    ("Chili Red", "spices", "C"),
    ("Black pepper", "spices", "C"),
    ("Soanf", "spices", "C"),
    ("Ajwan", "spices", "C"),
    ("Suva(Dill Seed)", "spices", "C"),
    ("Ginger(Dry)", "spices", "C"),
    ("Tamarind Fruit", "spices", "C"),           # condiment/souring agent
]

# Raw-name aliases → canonical FOCUS name (merge Agmarknet duplicate labels).
ALIASES: dict[str, str] = {
    "Ladies Finger": "Bhindi(Ladies Finger)",
    "Yam": "Yam(Ratalu)",
}

# ---------------------------------------------------------------------------
# EXCLUDED food categories — out of scope BY DESIGN (slow movers / not perishable).
# Documented for transparency; not fetched.
# ---------------------------------------------------------------------------
EXCLUDE: dict[str, list[str]] = {
    "grain": [
        "Wheat", "Maize", "Paddy(Common)", "Paddy(Basmati)", "Rice", "Broken Rice",
        "Beaten Rice", "Jowar(Sorghum)", "Bajra(Pearl Millet/Cumbu)", "Barley(Jau)",
        "Ragi(Finger Millet)", "Kodo Millet(Varagu)", "Foxtail Millet(Navane)",
        "Millets", "Kutki", "Maida Atta", "Wheat Atta",
    ],
    "pulse": [
        "Bengal Gram(Gram)(Whole)", "Red gram/Arhar/Tur(whole)",
        "Green Gram(Moong)(Whole)", "Black Gram(Urd Beans)(Whole)",
        "Lentil(Masur)(Whole)", "Masur Dal", "Black Gram Dal(Urd Dal)",
        "Green Gram Dal(Moong Dal)", "Bengal Gram Dal(Chana Dal)",
        "Red gram split/Arhar dal/Tur dal", "Kabuli Chana(Chickpeas-White)",
        "Peas(Dry)", "Field Pea", "Kulthi(Horse Gram)", "Other Pulses",
        "Avare Dal", "Big Gram", "Chennangi Dal", "Lak(Teora)", "Alasande Gram",
        "Mataki", "Guar", "Guar Seed(Cluster Beans Seed)",
    ],
    "oilseed": [
        "Soyabean", "Mustard", "Groundnut", "Groundnut pods(raw)", "Groundnut(Split)",
        "Ground Nut Seed", "Sesamum(Sesame,Gingelly,Til)", "Linseed",
        "Sunflower/Sunflower Seed", "Safflower", "Taramira", "Copra", "Coconut",
        "Coconut Seed", "Coconut Oil", "Mustard Oil", "Cashewnuts", "Almond(Badam)",
        "poppy seeds",
    ],
    "sugar": ["Gur(Jaggery)", "Sugar"],
    "meat_fish": ["Fish"],
}

# ---------------------------------------------------------------------------
# STRIP — NOT FOOD. Hard-drop even on a broad pull. (representative; extend as seen)
# ---------------------------------------------------------------------------
STRIP: frozenset[str] = frozenset({
    # fuel
    "Wood", "Firewood",
    # flowers
    "Marigold(Calcutta)", "Marigold(loose)", "Rose(Local)", "Rose(Loose))",
    "Jasmine", "Tube Rose(Loose)", "Tube Rose(Single)", "Tube Rose(Double)",
    "Carnation", "Lotus", "Lotus Sticks", "Lilly", "Jarbara", "Kankambra",
    "Gladiolus Cut Flower", "Orchid", "Astera", "Tube Flower", "Palash flowers",
    "Raibel", "Kakada", "gulli", "Marget", "Pupadia",
    # livestock
    "She Buffalo", "He Buffalo", "Cow", "Bull", "Ox", "Calf", "Goat", "Sheep",
    "Hen", "Cock", "Pigs",
    # industrial / fibre / medicinal / stimulant / beverage-crop
    "Rubber", "Cotton", "Cotton Seed", "Jute", "Tobacco", "Neem Seed",
    "Isabgul(Psyllium)", "Ashwagandha", "Giloy", "Mahua", "Mahua Seed(Hippe seed)",
    "karanja seeds", "Honge seed", "Lint", "Ambady/Mesta/Patson", "Absinthe",
    "Mahedi", "Cocoa", "Coffee", "Arecanut(Betelnut/Supari)", "Betal Leaves",
})


def focus_raw_names() -> set[str]:
    """Exact Agmarknet Commodity strings to pull (FOCUS canonicals + aliases).

    These feed the API ``filters[Commodity]`` scoped fetch and the
    aggregation join key.
    """
    names = {row[0] for row in FOCUS}
    names.update(ALIASES.keys())
    return names


def canonical(raw_name: str) -> str:
    """Resolve an alias to its canonical FOCUS name (identity if not aliased)."""
    return ALIASES.get(raw_name, raw_name)


def subgroup_of(raw_name: str) -> str | None:
    """CPI sub-group ('vegetables'|'fruits'|'spices') for a FOCUS commodity, else None."""
    name = canonical(raw_name)
    for n, sub, _tier in FOCUS:
        if n == name:
            return sub
    return None


def tier_of(raw_name: str) -> str | None:
    """Coverage tier ('A'|'B'|'C') for a FOCUS commodity, else None."""
    name = canonical(raw_name)
    for n, _sub, tier in FOCUS:
        if n == name:
            return tier
    return None
