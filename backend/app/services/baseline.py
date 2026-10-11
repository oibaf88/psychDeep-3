"""
Local, transparent equivalent of the "Alfa ML" structural_score /
confidence_band engine referenced throughout the spec docs.

The docs (doc 1, section on the "Motor analítico") explicitly sanction
simple, explainable statistics -- rolling Z-score / IQR -- for the
prototype phase, and only mark EWMA/CUSUM/Bayesian changepoint methods as
later research work. This module implements exactly that prototype-phase
method, entirely locally (no network calls, no third-party service).

Deliberate deviation from the docs: doc 2 sketches piping this
calculation through a third-party service ("AlphaInfo.io" / a pip
package called `alphainfo`) using an API key. That integration was
NOT implemented -- see README "Assumptions and gaps" for why (unverified
third party, would send sensitive mental-health signal data off-device,
contradicts the docs' own privacy-by-design principles). This module
reproduces the same statistical idea (z-score-based structural
similarity to a personal baseline) fully locally instead.
"""
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import AlfaSignal, Baseline, CheckIn
from app.services import change_config
from app.services.daily_statistics import local_day

# structural-v3 (2026-10-10, ADR 0003): windows, floors and bands come from the
# shared, versioned ``change_config``. The reference window now strictly
# precedes the recent window (no shared time points) and both use day means.
BASELINE_WINDOW_DAYS = change_config.REFERENCE_WINDOW_DAYS
RECENT_WINDOW_DAYS = change_config.RECENT_WINDOW_DAYS
MIN_CHECKINS_FOR_BASELINE = change_config.MIN_REFERENCE_DAYS

# How long an active baseline describes the present.
#
# It used to be forever: `get_active_baseline(...) or compute_or_refresh_...`
# created one on first use and never looked again, so a person's "normal" was
# fixed by their first three weeks in treatment and stayed there. Someone who
# genuinely improved kept being measured against how they were at their worst,
# and someone who deteriorated slowly drifted out of their own baseline
# without any single reading looking unusual.
#
# Recomputed on a 21-day window, so the baseline follows the person at the
# same pace it was built from. Long enough that a bad fortnight does not
# redefine normal; short enough that a season of change eventually does.
BASELINE_MAX_AGE_DAYS = 21

# craving is "inverted" (lower is better) so we flip sign before z-scoring
VARIABLES = ("mood", "craving_inv", "sleep_hours", "self_efficacy")

# Population-prior floors on the within-person SD (see change_config / ADR 0003).
STD_FLOORS = change_config.SD_FLOORS
CALCULATION_VERSION = "structural-v3"
# Versions whose deterioration band means "adverse, non-compensated" and can
# count towards persistence. v1 (symmetric) rows are never reused.
DETERIORATION_VERSIONS = ("structural-v2", "structural-v3")
# Cut-offs on mean |z| (kept as names for traces and older readers).
TRANSITION_MIN_COMPOSITE_Z = change_config.TRANSITION_Z
UNSTABLE_MIN_COMPOSITE_Z = change_config.UNSTABLE_Z


@dataclass
class StructuralScoreResult:
    score: float | None
    confidence_band: str  # stable | transition | unstable | insufficient_data
    z_scores: dict[str, float]
    baseline_n: int
    recent_n: int
    baseline_stats: dict[str, dict[str, float]]
    recent_means: dict[str, float]
    composite_z: float | None
    # Lower score means greater adverse deviation; it is not a probability
    # of suicide, relapse, or illness. Sleep is bilateral (change, not benefit).
    deterioration_score: float | None = None
    deterioration_band: str = "insufficient_data"
    adverse_composite_z: float | None = None
    favourable_composite_z: float | None = None
    adverse_z_scores: dict[str, float] = field(default_factory=dict)
    effective_stds: dict[str, float] = field(default_factory=dict)
    recent_counts: dict[str, int] = field(default_factory=dict)
    baseline_is_stale: bool = False
    calculation_version: str = CALCULATION_VERSION
    raw_differences: dict[str, float] = field(default_factory=dict)
    reference_window: dict[str, str] | None = None
    recent_window: dict[str, str] | None = None
    config_version: str = change_config.CONFIG_VERSION


@dataclass
class TrendResult:
    label: str
    slope: float | None
    sample_count: int
    increasing_threshold: float = 0.15
    decreasing_threshold: float = -0.15


def _finite_number(value) -> float | None:
    """Unknown, malformed, and non-finite values are not observations of zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _checkin_vector(c: CheckIn) -> dict[str, float]:
    vector = {}
    for key in VARIABLES:
        raw = _finite_number(getattr(c, "craving" if key == "craving_inv" else key, None))
        upper = 24.0 if key == "sleep_hours" else 10.0
        if raw is not None and 0.0 <= raw <= upper:
            vector[key] = 10.0 - raw if key == "craving_inv" else raw
    return vector


def _baseline_sample_count(stats: dict) -> int:
    counts = [_finite_number(_axis_stats(stats, key).get("n")) for key in VARIABLES]
    return int(min(counts)) if all(n is not None and n >= 0 for n in counts) else 0


def _axis_stats(stats: dict, key: str) -> dict:
    value = stats.get(key)
    return value if isinstance(value, dict) else {}


def _baseline_is_stale(baseline: Baseline, now: datetime | None = None) -> bool:
    # window_end dates the underlying observations, even if an old baseline
    # was copied/imported into a newly created database row.
    reference = getattr(baseline, "window_end", None) or getattr(baseline, "created_at", None)
    if not isinstance(reference, datetime):
        return True
    if reference.tzinfo is not None:
        reference = reference.astimezone(timezone.utc).replace(tzinfo=None)
    current = now or datetime.utcnow()
    if current.tzinfo is not None:
        current = current.astimezone(timezone.utc).replace(tzinfo=None)
    return current - reference >= timedelta(days=BASELINE_MAX_AGE_DAYS)


def _deviation_band(composite_z: float) -> str:
    """Statistical band only (no raw guard). Kept for older callers."""
    return change_config.z_band(composite_z)


def windows_for(now: datetime) -> tuple[datetime, datetime, datetime]:
    """``(reference_start, reference_end, recent_start)``; reference_end == recent_start.

    The reference is ``[reference_start, reference_end)`` and the recent window
    ``[recent_start, now]``: no time point belongs to both.
    """
    recent_start = now - timedelta(days=RECENT_WINDOW_DAYS)
    return recent_start - timedelta(days=BASELINE_WINDOW_DAYS), recent_start, recent_start


def _day_means(checkins: list[CheckIn]) -> dict[str, list[float]]:
    """Per-axis list of day means (several check-ins on one day count once)."""
    by_day: dict[str, dict[str, list[float]]] = {}
    for index, checkin in enumerate(checkins):
        created = getattr(checkin, "created_at", None)
        # A row without a timestamp cannot be placed on a day; it counts as
        # its own unit rather than being dropped or merged with another.
        day = local_day(created) if isinstance(created, datetime) else f"~undated-{index:06d}"
        for key, value in _checkin_vector(checkin).items():
            by_day.setdefault(day, {}).setdefault(key, []).append(value)
    out: dict[str, list[float]] = {key: [] for key in VARIABLES}
    for day in sorted(by_day):
        for key, values in by_day[day].items():
            out[key].append(statistics.fmean(values))
    return out


def _similarity(composite_z: float) -> float:
    # Smooth and strictly positive for every finite deviation. Previously
    # max(0, 1 - z/3) collapsed all z >= 3 to zero, including improvements.
    return 1.0 / (1.0 + composite_z)


def _mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = statistics.fmean(values)
    std = statistics.pstdev(values) if len(values) > 1 else 0.0
    return mean, std


def compute_or_refresh_baseline(db: Session, user_id, now: datetime | None = None) -> Baseline | None:
    """Persist a reference that ENDS where the recent window starts.

    Reference = day means of check-ins in ``[recent_start - 28 d, recent_start)``.
    Returns None (and keeps nothing new) when an axis has fewer than
    ``MIN_CHECKINS_FOR_BASELINE`` days: missing data is not zero.
    """
    now = now or datetime.utcnow()
    window_start, window_end, _ = windows_for(now)
    checkins = (
        db.query(CheckIn)
        .filter(CheckIn.user_id == user_id, CheckIn.created_at >= window_start, CheckIn.created_at < window_end)
        .all()
    )
    day_values = _day_means(checkins)
    stats: dict[str, dict[str, float]] = {}
    for var in VARIABLES:
        values = day_values.get(var, [])
        if len(values) < MIN_CHECKINS_FOR_BASELINE:
            return None
        mean, std = _mean_std(values)
        stats[var] = {"mean": mean, "std": std, "n": len(values)}

    db.query(Baseline).filter(Baseline.user_id == user_id, Baseline.is_active == True).update(  # noqa: E712
        {"is_active": False}
    )
    baseline = Baseline(
        user_id=user_id,
        window_start=window_start,
        window_end=window_end,
        stats=stats,
        is_active=True,
    )
    db.add(baseline)
    db.commit()
    db.refresh(baseline)
    return baseline


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def get_active_baseline(db: Session, user_id) -> Baseline | None:
    return (
        db.query(Baseline)
        .filter(Baseline.user_id == user_id, Baseline.is_active == True)  # noqa: E712
        .order_by(Baseline.created_at.desc())
        .first()
    )


def _current_baseline(db: Session, user_id, now: datetime | None = None) -> Baseline | None:
    """A reference that does not overlap the current recent window.

    Recomputed whenever the active row would overlap the recent window or no
    longer ends at (within a day of) its start. When a fresh reference cannot be
    built (too few days), an older active row is only reused if it ends before
    the recent window starts; an overlapping one is never used.
    """
    now = now or datetime.utcnow()
    _, _, recent_start = windows_for(now)
    active = get_active_baseline(db, user_id)
    active_end = getattr(active, "window_end", None) if active is not None else None
    if isinstance(active_end, datetime):
        active_end = _naive_utc(active_end)
        if active_end <= recent_start and recent_start - active_end < timedelta(days=1):
            return active
    fresh = compute_or_refresh_baseline(db, user_id, now)
    if fresh is not None:
        return fresh
    if isinstance(active_end, datetime) and active_end <= recent_start:
        return active
    return None


def compute_structural_score(db: Session, user_id, now: datetime | None = None) -> StructuralScoreResult:
    now = now or datetime.utcnow()
    baseline = _current_baseline(db, user_id, now)
    if baseline is None:
        return StructuralScoreResult(
            score=None,
            confidence_band="insufficient_data",
            z_scores={},
            baseline_n=0,
            recent_n=0,
            baseline_stats={},
            recent_means={},
            composite_z=None,
        )

    baseline_stats = baseline.stats if isinstance(baseline.stats, dict) else {}
    baseline_is_stale = _baseline_is_stale(baseline, now)
    _, _, recent_start = windows_for(now)
    ref_start = getattr(baseline, "window_start", None)
    ref_end = getattr(baseline, "window_end", None)
    reference_window = {
        "start": _naive_utc(ref_start).isoformat() if isinstance(ref_start, datetime) else None,
        "end": _naive_utc(ref_end).isoformat() if isinstance(ref_end, datetime) else None,
    }
    recent_window = {"start": recent_start.isoformat(), "end": now.isoformat()}
    recent = (
        db.query(CheckIn)
        .filter(CheckIn.user_id == user_id, CheckIn.created_at >= recent_start, CheckIn.created_at <= now)
        .all()
    )
    if not recent:
        return StructuralScoreResult(
            score=None,
            confidence_band="insufficient_data",
            z_scores={},
            baseline_n=_baseline_sample_count(baseline_stats),
            recent_n=0,
            baseline_stats=baseline_stats,
            recent_means={},
            composite_z=None,
            baseline_is_stale=baseline_is_stale,
        )

    recent_day_values = _day_means(recent)
    z_scores: dict[str, float] = {}
    raw_differences: dict[str, float] = {}
    recent_means: dict[str, float] = {}
    recent_counts: dict[str, int] = {}
    effective_stds: dict[str, float] = {}
    adverse_z_scores: dict[str, float] = {}
    abs_z_values: list[float] = []
    adverse_values: list[float] = []
    favourable_values: list[float] = []
    for var in VARIABLES:
        var_stats = _axis_stats(baseline_stats, var)
        mean = _finite_number(var_stats.get("mean"))
        std = _finite_number(var_stats.get("std"))
        n = _finite_number(var_stats.get("n"))
        values = recent_day_values.get(var, [])
        recent_counts[var] = len(values)
        if not values:
            continue
        recent_mean = statistics.fmean(values)
        recent_means[var] = round(recent_mean, 3)
        upper = 24.0 if var == "sleep_hours" else 10.0
        if mean is None or not 0 <= mean <= upper or std is None or std < 0 or n is None or n < MIN_CHECKINS_FOR_BASELINE:
            continue
        effective_std = max(std, STD_FLOORS[var])
        effective_stds[var] = effective_std
        z = (recent_mean - mean) / effective_std
        z_scores[var] = round(z, 3)
        raw_differences[var] = round(recent_mean - mean, 3)
        abs_z_values.append(abs(z))
        # Sleep duration has no universally favourable direction. Both less
        # and more than the personal baseline merit review, without claiming
        # either change establishes a clinical deterioration on its own.
        adverse = abs(z) if var == "sleep_hours" else max(-z, 0.0)
        favourable = 0.0 if var == "sleep_hours" else max(z, 0.0)
        adverse_z_scores[var] = round(adverse, 3)
        adverse_values.append(adverse)
        favourable_values.append(favourable)

    # The four-axis composite is not comparable if a missing axis is silently
    # replaced by zero, or if the denominator changes from four to three.
    if len(z_scores) != len(VARIABLES):
        return StructuralScoreResult(
            score=None, confidence_band="insufficient_data", z_scores=z_scores,
            baseline_n=_baseline_sample_count(baseline_stats), recent_n=len(recent),
            baseline_stats=baseline_stats, recent_means=recent_means, composite_z=None,
            adverse_z_scores=adverse_z_scores, effective_stds=effective_stds,
            recent_counts=recent_counts, baseline_is_stale=baseline_is_stale,
            raw_differences=raw_differences, reference_window=reference_window, recent_window=recent_window,
        )

    composite_z = statistics.fmean(abs_z_values)
    adverse_z = statistics.fmean(adverse_values)
    favourable_z = statistics.fmean(favourable_values)
    score = _similarity(composite_z)
    deterioration_score = _similarity(adverse_z)
    band = change_config.composite_band(composite_z, raw_differences)
    # Only adverse raw changes may lift the deterioration band (sleep bilateral).
    adverse_raw = {
        var: (abs(diff) if var == "sleep_hours" else max(-diff, 0.0)) for var, diff in raw_differences.items()
    }
    deterioration_band = change_config.composite_band(adverse_z, adverse_raw)

    signal = AlfaSignal(
        user_id=user_id,
        signal_type="structural_score",
        value={
            "score": score, "z_scores": z_scores, "composite_z": round(composite_z, 3),
            "deterioration_score": deterioration_score, "deterioration_band": deterioration_band,
            "adverse_composite_z": round(adverse_z, 3), "favourable_composite_z": round(favourable_z, 3),
            "adverse_z_scores": adverse_z_scores, "effective_stds": effective_stds,
            "recent_counts": recent_counts, "baseline_is_stale": baseline_is_stale,
            "calculation_version": CALCULATION_VERSION,
            "config_version": change_config.CONFIG_VERSION,
            "calibration_status": change_config.CALIBRATION_STATUS,
            "raw_differences": raw_differences,
            "aggregation": change_config.AGGREGATION,
            "reference_window": reference_window, "recent_window": recent_window,
            "baseline_id": str(baseline.id) if getattr(baseline, "id", None) is not None else None,
        },
        confidence_band=band,
    )
    db.add(signal)
    db.commit()

    return StructuralScoreResult(
        score=score,
        confidence_band=band,
        z_scores=z_scores,
        baseline_n=_baseline_sample_count(baseline_stats),
        recent_n=len(recent),
        baseline_stats=baseline_stats,
        recent_means=recent_means,
        composite_z=round(composite_z, 3),
        deterioration_score=deterioration_score,
        deterioration_band=deterioration_band,
        adverse_composite_z=round(adverse_z, 3),
        favourable_composite_z=round(favourable_z, 3),
        adverse_z_scores=adverse_z_scores,
        effective_stds=effective_stds,
        recent_counts=recent_counts,
        baseline_is_stale=baseline_is_stale,
        raw_differences=raw_differences,
        reference_window=reference_window,
        recent_window=recent_window,
    )


# Trend labels per variable. A falling slope is only "worsening" where lower is
# worse (sleep, as before); for craving a falling slope is "disminuyendo" and a
# rising one "aumentando", so a rise in craving always reads as a rise.
TREND_LABELS = {
    "default": ("aumentando", "empeorando"),
    "sleep_hours": ("aumentando", "empeorando"),
    "craving": ("aumentando", "disminuyendo"),
}


def calculate_trend_detail(values: list, variable: str = "default") -> TrendResult:
    """Small linear-regression-slope trend classifier (doc 18 `calcular_tendencia`).

    Returns the label *and* the exact regression inputs used to derive it:
    insufficient data below 3 points, thresholded slope ->
    aumentando/empeorando/estable.
    """
    # Missing values are skipped, never read as zero.
    values = [v for v in (_finite_number(x) for x in values) if v is not None]
    if len(values) < 3:
        return TrendResult(label="insuficiente", slope=None, sample_count=len(values))
    rising_label, falling_label = TREND_LABELS.get(variable, TREND_LABELS["default"])

    n = len(values)
    xs = list(range(n))
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(values)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values))
    denominator = sum((x - x_mean) ** 2 for x in xs) or 1.0
    slope = numerator / denominator

    # thresholds are intentionally conservative / symmetric
    if slope > 0.15:
        return TrendResult(label=rising_label, slope=round(slope, 4), sample_count=n)
    if slope < -0.15:
        return TrendResult(label=falling_label, slope=round(slope, 4), sample_count=n)
    return TrendResult(label="estable", slope=round(slope, 4), sample_count=n)
