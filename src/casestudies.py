"""Stored case-study pages for the copylint tracing rule.

TASK-365. Each case study in ``config/clients/productive-offers.yaml`` has a
stored page under ``docs/evidence/case-studies/<key>.json``. The lint reads
these to decide whether a figure in outbound copy actually appears on the
page.

FAIL CLOSED. A study with no stored page refuses every claim that names it.
An empty directory refuses every case-study claim. The lint never silently
passes because the evidence is missing - that was the defect the rework
fixed.
"""
import json
import os

_STUDIES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "evidence", "case-studies",
)

#: Known study keys from the config. The lint uses these to recognise a
#: case-study mention in outbound copy.
KNOWN_STUDIES = {
    "infinum": "Infinum",
    "makerstreet": "Makerstreet",
    "dotcontrol": "DotControl",
    "hike_one": "Hike One",
    "saffron": "Saffron",
    "bicg": "BICG",
    "porsche_digital_croatia": "Porsche Digital Croatia",
    "tandem_x_visuals": "Tandem X Visuals",
    "flatline_agency": "Flatline Agency",
    "donq": "DonQ",
    "medico_digital": "Medico Digital",
}


def load_study(key):
    """Load one stored study. Returns the dict, or None if not stored.

    Returns None for a missing file - the lint treats this as REFUSE, not
    pass. That is the fail-closed invariant.
    """
    path = os.path.join(_STUDIES_DIR, f"{key}.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("status") != "OK" or not data.get("page_text"):
        return None
    return data


def load_all():
    """Every stored study, keyed by study key. Empty dict when none exist.

    The caller (the lint) must treat an empty return as REFUSE ALL, not as
    nothing to check. The docstring says this explicitly because the
    fail-open version of this function is what the rework fixed.
    """
    out = {}
    if not os.path.isdir(_STUDIES_DIR):
        return out
    for key in KNOWN_STUDIES:
        study = load_study(key)
        if study is not None:
            out[key] = study
    return out


def study_names():
    """Display names for every known study, for the lint to match against."""
    return dict(KNOWN_STUDIES)
