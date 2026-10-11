# ADR-0003 — Evidence-based change bands and a reference window that precedes the comparison

Status: Accepted by the product owner on 2026-10-10 as a **provisional population prior**. Formal clinical sign-off is still pending (AGENTS.md G3 item "Complete formal clinical sign-off for vNext safety thresholds/protocol behaviour" stays `[ ]`). This does not mark PsychDeep vNext complete, pilot-ready or clinically validated.

## Context

The 2026-10-10 audit found three problems in how PsychDeep compares a person with their own recent past:

1. **Overlapping windows in the risk engine.** `structural-v2` (`backend/app/services/baseline.py`) built the personal baseline from the last 21 days *including* the 7-day window it was then compared with, and reused an active baseline for up to 21 days. A recent deterioration was partly absorbed into its own reference, which pulled every comparison towards "stable". The product owner stated the rule: *by definition, the deviation over time and the baseline cannot be computed over overlapping time points.* The canonical path (`canonical-structural-v2`, PR #172) already excluded the recent window. The linguistic personal baseline (`profile.py`, 120 days) also included the reading it was compared against.
2. **Band cut-offs without evidence.** `structural-v2` kept descriptive cut-offs (mean |z| 1.2 / 1.95) inherited from an earlier score transform. They were labelled engineering heuristics.
3. **Craving trend wording inverted.** `calculate_trend_detail` called every falling slope "empeorando". For craving, a *falling* craving was therefore labelled "worsening" in the trend that feeds the risk rules and their trace. (The rule itself used "aumentando" correctly; the wording was wrong.)

The product owner asked (2026-10-10) for parameters taken from good-quality clinical and scientific sources on the temporal variability of daily self-reports (EMA / daily diaries), as a scientifically acceptable starting point until PsychDeep has enough data of its own, and authorised changing the engine.

## Evidence (only sources that were opened and read)

| # | Source | Design / sample | What it supports | Exact value used |
|---|---|---|---|---|
| 1 | Jacobson NS, Truax P. Clinical significance: a statistical approach to defining meaningful change in psychotherapy research. *J Consult Clin Psychol* 1991;59(1):12-19. doi:10.1037/0022-006X.59.1.12. PMID 2002127 | Methodological | Reliable change index (RC): a change is "reliable" when it exceeds what measurement error explains; twofold criterion (statistically reliable **and** clinically meaningful) | Two-sided 95 % criterion, 1.96 × SE of the difference; we also use 2.576 (99 %) for the upper band |
| 2 | Schat E, Tuerlinckx F, Smit AC, De Ketelaere B, Ceulemans E. Detecting mean changes in experience sampling data in real time: a comparison of univariate and multivariate statistical process control methods. *Psychol Methods* 2023;28(6):1335-1357. doi:10.1037/met0000447. PMID 34914467 (author manuscript, KU Leuven Lirias) | Simulation + empirical ESM case (patient relapsing into depression) | Monitor **day averages**, not single prompts (less autocorrelation, skew, missingness); EWMA/CUSUM beat Shewhart; Phase I (reference) length | Lag-1 autocorrelation of day averages in Phase I "reduced to .17"; "at least 100 days is recommended for 1 and 2 beeps per day" in Phase I; λ = .1 with L = 2.7 for ARL0 = 370 (not used yet, see Rule for personal calibration) |
| 3 | Smit AC, Schat E, Ceulemans E. The exponentially weighted moving average procedure for detecting changes in intensive longitudinal data in psychological research in real-time: a tutorial showcasing potential applications. *Assessment* 2023;30(5):1354-1368. doi:10.1177/10731911221086985. PMID 35603660, PMC10248291 | Tutorial on three empirical intensive-longitudinal datasets (including a "craving" item in a person with remitted substance abuse) | Phase I must be representative of no-change behaviour; a 28-day Phase I used in an applied example | "a Phase I period of 28 days"; λ "between .05 and .10 work well when using day averages" |
| 4 | Norman GR, Sloan JA, Wyrwich KW. Interpretation of changes in health-related quality of life: the remarkable universality of half a standard deviation. *Med Care* 2003;41(5):582-592. PMID 12719681 | Systematic review, 38 studies, 62 effect sizes | Minimal important difference is about 0.5 SD; human discrimination limit ≈ 1 part in 7 | MID mean = 0.495 SD (SD 0.155). Used as a cross-check (our 1-point floor and 1-point guard are below 1/7 of 0-10 ≈ 1.43, i.e. more sensitive) |
| 5 | Farrar JT, Young JP Jr, LaMoreaux L, Werth JL, Poole MR. Clinical importance of changes in chronic pain intensity measured on an 11-point numerical pain rating scale. *Pain* 2001;94(2):149-158. PMID 11690728 | 10 placebo-controlled RCTs, n = 2724, daily-diary 0-10 NRS vs PGIC | Clinically important change on a daily 0-10 NRS | "a reduction of approximately two points or … approximately 30 %" → 2-point guard for the unstable band on 0-10 items (borrowed from pain, see limitations) |
| 6 | Sateia MJ et al. Clinical Practice Guideline for the Pharmacologic Treatment of Chronic Insomnia in Adults: AASM. *J Clin Sleep Med* 2017. doi:10.5664/jcsm.6470 (Table 3, read in the AASM PDF) | Guideline, task-force consensus prior to analysis | Clinical significance threshold for total sleep time | Subjective (sleep diary) TST: **30 min**; PSG/actigraphy 20 min → 0.5 h floor and guard for sleep |
| 7 | Serre F, Fatseas M, Swendsen J, Auriacombe M. Ecological momentary assessment in the investigation of craving and substance use in daily life: a systematic review. *Drug Alcohol Depend* 2015;148:1-20. doi:10.1016/j.drugalcdep.2014.12.024. PMID 25637078 | Systematic review, 91 EMA studies (73 % tobacco) | Craving → use link in daily life, strongest when close in time | 92 % of studies reported a positive craving-use relationship. Supports a short (7-day) recent window and keeping craving as an axis; no number enters the formula |
| 8 | Moore TM, Seavey A, Ritter K, McNulty JK, Gordon KC, Stuart GL. Ecological momentary assessment of the effects of craving and affect on risk for relapse during substance abuse treatment. *Psychol Addict Behav* 2014;28(2):619-624. PMID 24128286 | RCT-embedded EMA, n = 100 SUD outpatients, 3 prompts/day for 4 months | An *increase* in craving precedes relapse | Increase in craving on a prompt → 14 times more likely to report relapse on the next prompt. Supports reading a rise in craving as a rise (trend fix) |
| 9 | Epstein DH, Willner-Reid J, Vahabzadeh M, Mezghanni M, Lin JL, Preston KL. Real-time electronic diary reports of cue exposure and mood in the hours before cocaine and heroin craving and use. *Arch Gen Psychiatry* 2009;66(1):88-94. PMID 19124692 | Cohort, 114 methadone-treated outpatients, 14 918 person-days | Feasibility of daily EMA in polydrug SUD; precursors are detectable hours before craving/use | Context only; no number used |
| 10 | Boyett B et al. Assessment of craving in opioid use disorder: psychometric evaluation and predictive validity of the opioid craving VAS. *Drug Alcohol Depend* 2021;229:109057. PMID 34794061 (abstract read; full text not accessible) | Phase 3 trial data, n = 487 | A single-item craving scale is reliable and predicts subsequent use | Weekly test-retest ICC > 0.70. No MCID taken from it (the threshold reported in the full text could not be verified) |

Also read and used as context only: Jahng, Wood & Trull 2008 (*Psychol Methods* 13:354-375, PMID 19071999; MSSD as an instability index); Bei et al. 2016 (*Sleep Med Rev* 28:108-124, PMID 26588182; sleep intra-individual variability higher with depression, insomnia, stress; no pooled SD); van Rijsbergen et al. 2012 (*PLoS One* 7:e46796, PMID 23056456; a one-item mood VAS predicted depressive relapse over 5.5 years, 6.3 % of variance).

**GHB/GBL.** No EMA or daily-diary study of within-person variability in GHB/GBL use disorder was found. Values are borrowed from other SUD and psychiatric samples (see limitations).

## Decision

One shared, versioned module, `backend/app/services/change_config.py` (`CONFIG_VERSION = "change-bands-v1-population-prior"`), is used by both the risk engine's structural input (`structural-v3`, `risk-engine-v1.6`) and the canonical ChangeSignal path (`canonical-structural-v3`, `FeatureDefinition` version `v2`).

| Parameter | Value | Basis |
|---|---|---|
| Recent (comparison) window | 7 days, `[now − 7 d, now]` | Unchanged; craving→use is proximal (7, 8) |
| Reference window | 28 days, `[recent_start − 28 d, recent_start)`; **ends where the recent window starts, no shared time point** | Product-owner rule; 28-day Phase I (3) |
| Unit of analysis | Mean per local (Europe/Madrid) day; several check-ins on one day count once | (2), (3) |
| Minimum reference | 5 days with a value per axis; else `insufficient_data` (never zero) | Engineering, unchanged from v2 (no evidence for a specific minimum) |
| SD used for z | max(personal SD of day means, prior floor) | Prior floor guards against near-constant series |
| Prior SD floors | 1 point for mood, craving (inverted axis) and self-efficacy; 0.5 h for sleep | 1 point = resolution of an integer 0-10 item (below the 1/7 discrimination limit, 4); 0.5 h = AASM subjective TST (6) |
| Statistical criterion | z = (recent mean − reference mean) / SD_eff. Transition at \|z\| ≥ 1.0; unstable at \|z\| ≥ 1.3 (per axis and on the mean of the four \|z\|) | RC logic (1) for a difference of two means of daily values with 7 vs 28 days and lag-1 autocorrelation 0.17 (2): SE/SD = √(1/7 + 1/28) × √(1.17/0.83) = 0.502. 1.96 × 0.502 = 0.98 → 1.0; 2.576 × 0.502 = 1.29 → 1.3 |
| Clinically meaningful raw change (guard) | Per axis: transition needs ≥ 1 point (0-10) / ≥ 0.5 h (sleep); unstable needs ≥ 2 points (0-10) / ≥ 0.5 h. Composite: leaves "stable" only if at least one axis moved ≥ its transition guard | Twofold criterion (1); 2 points / 30 % on daily 0-10 NRS (5); 30 min TST (6) |
| Reliable change index | Stored per axis in `ChangeSignal.uncertainty.reliable_change_index` with the actual day counts | (1), (2). Informative; the band uses the fixed cut-offs above |
| Craving trend wording | Raw craving slope > 0.15/registro → "aumentando"; < −0.15 → "disminuyendo" (was "empeorando"). Sleep keeps "empeorando" for a falling slope | (7), (8). The N3 rule condition (`craving_rising` = "aumentando") is unchanged |
| Linguistic personal baseline | Signals from the last 7 days are excluded from the 120-day reference | Same non-overlap rule |

Kept unchanged on purpose: deterministic N4 declaration rules, crisis resources, `adverse_composite_z > 2.4`, persistence days (3 / 5), `PERSONAL_DEVIATION_SIGMA`, all rule thresholds outside the structural band, and the LLM role (none in this calculation). ChangeSignal remains separate from RiskAssessment. Old rows keep their versions (`structural-v2`, `canonical-structural-v2`); the chart from #179 shows a marker at the version change and each segment keeps its own bands. `structural-v2` deterioration bands still count towards persistence; v1 rows never do.

## Rule for switching to personal calibration

All values above are a **provisional population prior until sufficient personal data**. Personal calibration means: the person's own SD of day means replaces the prior floor, and control limits (EWMA, λ ≈ 0.1, L ≈ 2.7 for ARL0 ≈ 370, per (2)) are estimated from the person's own reference. It may only be introduced, in a new versioned config, when **all** of the following hold:

1. at least `PERSONAL_CALIBRATION_MIN_DAYS = 100` days with a check-in in a reference period with no clinically recorded crisis episode (2: ≥ 100 Phase I days for 1-2 reports per day);
2. a retrospective check on PsychDeep's own de-identified data shows the false-alarm rate and the detection of documented deteriorations, reviewed by the clinical lead;
3. formal clinical sign-off (G3).

Until then every stored calculation records `calibration_status = "provisional_population_prior"` and the config snapshot.

## Sensitivity check (old `structural-v2` / `risk-engine-v1.5` vs new)

Harness: `/workspace/audit/sensitivity/harness.py` (audit artefact). Each scenario is evaluated day by day for 7 days with persisted history, then the canonical path runs once. Deterministic seeds; the same data for both engines.

| Scenario | Alert level, final (old → new) | Max level in 7 days | Engine band | Deterioration band | Canonical composite | Craving trend label |
|---|---|---|---|---|---|---|
| Demo seed patient (28 days) | 0 → 0 | 0 → 0 | stable → stable | stable → stable | stable → stable | empeorando → **disminuyendo** (craving was falling) |
| Laura: last week worse | 3 → 3 | 3 → 3 | unstable → unstable | unstable → unstable | unstable → unstable | estable → estable |
| Marta: 14 days, stable | 0 → 0 | 0 → 0 | stable → stable | stable → stable | stable → stable | aumentando → aumentando |
| Pablo: no check-ins for 20 days | 1 → 1 | 1 → 1 | insufficient → insufficient | insufficient → insufficient | insufficient → insufficient | estable → estable |
| Stable with noise, 42 days | 0 → 0 | 0 → 0 | stable → stable | stable → stable | stable → stable | estable → estable |
| Constant series, 1-point shift on three axes | 0 → 0 | 0 → 0 | stable → stable | stable → stable | stable → stable (per axis: mood, craving, self-efficacy stable → transition) | estable → estable |
| Acute craving spike, last 3 days | 0 → **2** | 0 → **2** | stable → transition | stable → transition | stable → transition | aumentando → aumentando |
| Gradual mood decline over 6 weeks | 0 → 0 | 0 → 0 | stable → stable | stable → stable | stable → stable (mood transition in both) | estable → estable |
| Sleep drop 7 h → 4.75 h last week | 0 → **2** | 0 → **2** | stable → transition | stable → transition | transition → transition | estable → estable |
| Clear improvement | 0 → 0 | 0 → 0 | unstable → unstable | stable → stable | unstable → unstable | estable → estable |
| 3 check-ins per day, deterioration | 3 → 3 | 3 → 3 | unstable → unstable | unstable → unstable | unstable → unstable | empeorando → **disminuyendo** |
| Sparse data (every 3rd day), deterioration | 2 → **3** | 2 → **3** | transition → unstable | transition → unstable | unstable → unstable | aumentando → aumentando |
| Craving rising 3 → 9 over 7 days | 0 → 0 | 0 → 0 | stable → stable | stable → stable | stable → stable (craving unstable in both) | aumentando → aumentando |
| Moderate deterioration (~1.5 points) | 2 → **3** | 2 → **3** | transition → unstable | transition → unstable | transition → unstable | estable → estable |

No scenario's alert level went down, on the final day or on any of the 7 evaluated days. Four scenarios escalate (more sensitivity). The full existing backend suite passes unchanged apart from the tests that asserted v2-specific values. Key rows are encoded as regression tests in `backend/tests/test_change_bands_v3.py`.

## Limitations

- **No validated MCID** exists for single-item daily mood, craving or self-efficacy ratings on 0-10 in SUD. The 2-point guard comes from pain NRS (5). The 1-point guard and floor are a scale-resolution choice, not a clinical threshold.
- **No pooled within-person SD** for daily 0-10 mood/craving/self-efficacy in SUD samples was found in the sources read. The floors are therefore resolution-based. Sleep (6) is a between-group clinical-significance threshold used as a within-person minimum.
- The autocorrelation prior (0.17) comes from one empirical ESM case in (2). Higher autocorrelation would make the cut-offs too liberal (more alerts, not fewer).
- The 28-day reference is far shorter than the ≥ 100 days that (2) recommends for well-estimated control limits. This is why the prior floors stay and personal calibration is deferred.
- No GHB/GBL-specific daily variability data were found.
- The minimum of 5 reference days has no evidence base.
- Increased sensitivity raises N2/N3 alerts in some scenarios. Alert burden in real use is not yet measured.
- The sensitivity check uses synthetic scenarios and existing fixtures, not real patient data.

## Rollback

Revert the PR. Rows written with `structural-v3` / `canonical-structural-v3` stay in the database with their version labels (additive; no migration). Readers already treat unknown versions as historical.
