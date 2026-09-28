"""Material category constants shared by the whole platform."""
from __future__ import annotations

CATEGORIES: dict[str, dict] = {
    "PCB": {"label": "Printed Circuit Board", "hint": "green/brown boards, chips"}
    ,
    "battery": {"label": "Battery", "hint": "Li-ion / lead acid packs"},
    "motor_magnet": {"label": "Motor / Magnet", "hint": "speaker magnets, motor windings"},
    "cable": {"label": "Cable / Wire", "hint": "copper or aluminium wire"},
    "CRT": {"label": "CRT Monitor", "hint": "thick glass tube TV/monitor"},
    "LCD": {"label": "LCD / LED Panel", "hint": "flat screen panel"},
    "mixed_plastic": {"label": "Mixed Plastic", "hint": "e-waste plastic housing"},
    "other": {"label": "Other E-waste", "hint": "unclassified"},
}

CATEGORY_CODES = list(CATEGORIES.keys())

# Electrode / cell chemistry sub-types, used to refine the stoichiometric estimate.
BATTERY_CHEMISTRIES = ["li_ion_nmc", "li_ion_lfp", "li_ion_lco", "lead_acid", "nimh"]

# User roles
ROLES = ["collector", "recycler", "admin"]
