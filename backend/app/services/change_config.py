"""Shared, versioned parameters for change versus the personal baseline.

ONE place for the windows, floors and band cut-offs used by BOTH
* the risk engine's structural input (``baseline.py`` -> ``structural-v3``), and
* the canonical ChangeSignal path (``canonical_analytics.py`` -> ``canonical-structural-v3``).

Every value here is a **provisional population prior until sufficient personal
data** exists. The evidence, derivations and limitations are in
``docs/adr/0003-evidence-based-change-bands.md``. Changing a value requires
a new ``CONFIG_VERSION`` (and new algorithm versions), never an in-place edit,
so stored rows stay reproducible.

None of this is a RiskAssessment. Deterministic N4 declaration rules, crisis
resources and the LLM are untouched by these parameters.
"""
from __future__ import annotations

import math

CONFIG_VERSION = "change-bands-v1-population-prior"
CALIBRATION_STATUS = "provisional_population_prior"

# --- Windows ---------------------------------------------------------------
# Recent (comparison) window. The reference window ends where it starts:
# reference = [recent_start - REFERENCE_WINDOW_DAYS, recent_start), recent =
# [recent_start, now]. No time point belongs to both.
RECENT_WINDOW_DAYS = 7
# 28 days of daily reports as the in-control ("Phase I") reference, as used by
# Smit & Snippe in the EWMA tutorial of Smit, Schat & Ceulemans (2023).
REFERENCE_WINDOW_DAYS = 28
# Minimum distinct days with a value in the reference, per axis. Engineering
# choice kept from structural-v2 (no study gives a validated minimum); below
# it the axis is insufficient_data, never zero.
MIN_REFERENCE_DAYS = 5
# Personal calibration (personal SD without the prior floor, control limits
# from the person's own series) needs ~100 daily observations for 1-2 reports
# per day (Schat et al., 2023). Until then the prior below governs.
PERSONAL_CALIBRATION_MIN_DAYS = 100

# --- Units of analysis -------------------------------------------------------
# Several check-ins on one day are averaged first (day averages), which reduces
# autocorrelation, skew and the weight of a "talkative" day (Schat et al., 2023).
AGGREGATION = "day_mean"

# --- Floors on the within-person SD (population prior) -----------------------
# 0-10 items: 1 point = the resolution of an integer 0-10 rating; a smaller SD
# would turn a one-step change into several SDs. Sleep: 0.5 h = the AASM
# clinical-significance threshold for subjective total sleep time (30 min,
# Sateia et al., 2017). The person's own SD is used when it is larger.
SD_FLOORS = {"mood": 1.0, "craving_inv": 1.0, "sleep_hours": 0.5, "self_efficacy": 1.0}

# --- Statistical cut-offs on |z| = |recent mean - reference mean| / SD_eff ----
# Derived from the Jacobson & Truax (1991) reliable-change logic applied to a
# difference of two means of daily values (7 recent days vs 28 reference days),
# inflated for lag-1 autocorrelation rho = 0.17 of day averages (Schat et al.,
# 2023, empirical ESM example):
#   SE(diff)/SD = sqrt(1/7 + 1/28) * sqrt((1 + rho) / (1 - rho)) = 0.502
#   95 % two-sided (1.96)  -> |z| >= 0.98  -> TRANSITION_Z = 1.0
#   99 % two-sided (2.576) -> |z| >= 1.29  -> UNSTABLE_Z  = 1.3
PRIOR_AUTOCORRELATION = 0.17
TRANSITION_Z = 1.0
UNSTABLE_Z = 1.3

# --- Absolute (raw-scale) guards ---------------------------------------------
# A band above "stable" also needs a raw change at least this large on the
# declared scale, so a statistically "reliable" but trivial change on a
# near-constant series does not fire.
#   0-10 transition: 1 point (scale resolution).
#   0-10 unstable:   2 points (~2 points / 30 % = clinically important change on
#                    an 11-point NRS, Farrar et al., 2001; borrowed from pain).
#   sleep: 0.5 h for both (AASM subjective TST, 30 min).
ABSOLUTE_GUARDS = {
    "mood": {"transition": 1.0, "unstable": 2.0},
    "craving_inv": {"transition": 1.0, "unstable": 2.0},
    "self_efficacy": {"transition": 1.0, "unstable": 2.0},
    "sleep_hours": {"transition": 0.5, "unstable": 0.5},
}


def z_band(abs_z: float) -> str:
    """Band from the statistical criterion only (composite and per axis)."""
    if abs_z >= UNSTABLE_Z:
        return "unstable"
    if abs_z >= TRANSITION_Z:
        return "transition"
    return "stable"


def axis_band(axis: str, z: float, raw_difference: float) -> str:
    """Per-axis band: statistical criterion AND clinically meaningful raw change."""
    band = z_band(abs(z))
    guards = ABSOLUTE_GUARDS[axis]
    size = abs(raw_difference)
    if band == "unstable" and size < guards["unstable"]:
        band = "transition"
    if band == "transition" and size < guards["transition"]:
        band = "stable"
    return band


def composite_band(abs_z_mean: float, raw_differences: dict[str, float]) -> str:
    """Composite band: mean |z| criterion, and at least one axis must show a
    raw change of at least its transition guard (otherwise a near-constant
    series cannot leave "stable")."""
    band = z_band(abs_z_mean)
    if band != "stable" and not any(
        abs(diff) >= ABSOLUTE_GUARDS[axis]["transition"] for axis, diff in raw_differences.items()
    ):
        return "stable"
    return band


def reliable_change_index(raw_difference: float, sd_eff: float, n_recent: int, n_reference: int) -> float | None:
    """Jacobson & Truax-style index for a difference of two means of daily values,
    inflated for the prior lag-1 autocorrelation. Informative only (shown, not
    used for the band, whose cut-offs are fixed at typical counts)."""
    if n_recent <= 0 or n_reference <= 0 or sd_eff <= 0:
        return None
    inflation = math.sqrt((1 + PRIOR_AUTOCORRELATION) / (1 - PRIOR_AUTOCORRELATION))
    se = sd_eff * math.sqrt(1 / n_recent + 1 / n_reference) * inflation
    return round(raw_difference / se, 3)


def describe() -> dict:
    """Serializable snapshot stored with traces and FeatureDefinitions."""
    return {
        "config_version": CONFIG_VERSION,
        "calibration_status": CALIBRATION_STATUS,
        "recent_window_days": RECENT_WINDOW_DAYS,
        "reference_window_days": REFERENCE_WINDOW_DAYS,
        "reference_precedes_recent": True,
        "min_reference_days": MIN_REFERENCE_DAYS,
        "aggregation": AGGREGATION,
        "sd_floors": dict(SD_FLOORS),
        "transition_z": TRANSITION_Z,
        "unstable_z": UNSTABLE_Z,
        "prior_autocorrelation": PRIOR_AUTOCORRELATION,
        "absolute_guards": {k: dict(v) for k, v in ABSOLUTE_GUARDS.items()},
        "personal_calibration_min_days": PERSONAL_CALIBRATION_MIN_DAYS,
    }
