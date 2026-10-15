-- Ensure the canonical v3 analytics feature definitions exist in every environment.
-- Idempotent: safe when runtime seeding or a manual production repair already
-- created the v2 rows. Preserves older v1 definitions for historical provenance.
begin;

do $$
declare
    membership_is_expected boolean;
begin
    select count(*) = 1
       and bool_and(m.admin_option)
       and not bool_or(m.inherit_option)
       and not bool_or(m.set_option)
       and bool_and(grantor.rolname = 'supabase_admin')
      into membership_is_expected
      from pg_auth_members m
      join pg_roles granted_role on granted_role.oid = m.roleid
      join pg_roles member_role on member_role.oid = m.member
      join pg_roles grantor on grantor.oid = m.grantor
     where granted_role.rolname = 'psychdeep_backend'
       and member_role.rolname = 'postgres';

    if not coalesce(membership_is_expected, false) then
        raise exception 'Unexpected postgres -> psychdeep_backend membership; migration stopped safely';
    end if;
end
$$;

grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

insert into psychdeep_v12.feature_definitions
    (feature_key, version, formula, unit, window_spec, missingness_policy, valid_range, status)
values
    ('mood', 'v2', 'mean of day means(mood) over recent window; craving inverted for z-score',
     '0-10', '{"baseline_days":28,"recent_days":7,"min_n":5,"min_n_unit":"days","change_config":{"config_version":"change-bands-v1-population-prior","calibration_status":"provisional_population_prior","recent_window_days":7,"reference_window_days":28,"reference_precedes_recent":true,"min_reference_days":5,"aggregation":"day_mean","sd_floors":{"mood":1.0,"craving_inv":1.0,"sleep_hours":0.5,"self_efficacy":1.0},"transition_z":1.0,"unstable_z":1.3,"prior_autocorrelation":0.17,"absolute_guards":{"mood":{"transition":1.0,"unstable":2.0},"craving_inv":{"transition":1.0,"unstable":2.0},"self_efficacy":{"transition":1.0,"unstable":2.0},"sleep_hours":{"transition":0.5,"unstable":0.5}},"personal_calibration_min_days":100}}'::jsonb,
     'missing_is_not_zero; axis omitted from composite when absent', '{"min":0,"max":10}'::jsonb, 'active'),
    ('craving', 'v2', 'mean of day means(craving) over recent window; craving inverted for z-score',
     '0-10', '{"baseline_days":28,"recent_days":7,"min_n":5,"min_n_unit":"days","change_config":{"config_version":"change-bands-v1-population-prior","calibration_status":"provisional_population_prior","recent_window_days":7,"reference_window_days":28,"reference_precedes_recent":true,"min_reference_days":5,"aggregation":"day_mean","sd_floors":{"mood":1.0,"craving_inv":1.0,"sleep_hours":0.5,"self_efficacy":1.0},"transition_z":1.0,"unstable_z":1.3,"prior_autocorrelation":0.17,"absolute_guards":{"mood":{"transition":1.0,"unstable":2.0},"craving_inv":{"transition":1.0,"unstable":2.0},"self_efficacy":{"transition":1.0,"unstable":2.0},"sleep_hours":{"transition":0.5,"unstable":0.5}},"personal_calibration_min_days":100}}'::jsonb,
     'missing_is_not_zero; axis omitted from composite when absent', '{"min":0,"max":10}'::jsonb, 'active'),
    ('sleep_hours', 'v2', 'mean of day means(sleep_hours) over recent window; craving inverted for z-score',
     'hours', '{"baseline_days":28,"recent_days":7,"min_n":5,"min_n_unit":"days","change_config":{"config_version":"change-bands-v1-population-prior","calibration_status":"provisional_population_prior","recent_window_days":7,"reference_window_days":28,"reference_precedes_recent":true,"min_reference_days":5,"aggregation":"day_mean","sd_floors":{"mood":1.0,"craving_inv":1.0,"sleep_hours":0.5,"self_efficacy":1.0},"transition_z":1.0,"unstable_z":1.3,"prior_autocorrelation":0.17,"absolute_guards":{"mood":{"transition":1.0,"unstable":2.0},"craving_inv":{"transition":1.0,"unstable":2.0},"self_efficacy":{"transition":1.0,"unstable":2.0},"sleep_hours":{"transition":0.5,"unstable":0.5}},"personal_calibration_min_days":100}}'::jsonb,
     'missing_is_not_zero; axis omitted from composite when absent', '{"min":0,"max":24}'::jsonb, 'active'),
    ('self_efficacy', 'v2', 'mean of day means(self_efficacy) over recent window; craving inverted for z-score',
     '0-10', '{"baseline_days":28,"recent_days":7,"min_n":5,"min_n_unit":"days","change_config":{"config_version":"change-bands-v1-population-prior","calibration_status":"provisional_population_prior","recent_window_days":7,"reference_window_days":28,"reference_precedes_recent":true,"min_reference_days":5,"aggregation":"day_mean","sd_floors":{"mood":1.0,"craving_inv":1.0,"sleep_hours":0.5,"self_efficacy":1.0},"transition_z":1.0,"unstable_z":1.3,"prior_autocorrelation":0.17,"absolute_guards":{"mood":{"transition":1.0,"unstable":2.0},"craving_inv":{"transition":1.0,"unstable":2.0},"self_efficacy":{"transition":1.0,"unstable":2.0},"sleep_hours":{"transition":0.5,"unstable":0.5}},"personal_calibration_min_days":100}}'::jsonb,
     'missing_is_not_zero; axis omitted from composite when absent', '{"min":0,"max":10}'::jsonb, 'active')
on conflict (feature_key, version) do update set
    formula = excluded.formula,
    unit = excluded.unit,
    window_spec = excluded.window_spec,
    missingness_policy = excluded.missingness_policy,
    valid_range = excluded.valid_range,
    status = excluded.status;

reset role;
revoke psychdeep_backend from postgres granted by postgres;

commit;
