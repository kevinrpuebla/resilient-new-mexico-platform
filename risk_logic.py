# risk_logic.py
def simulate_adjusted_risk(eal_score: float,
                           social_vulnerability: float,
                           community_resilience: float,
                           sv_delta_pct: float,
                           cr_delta_pct: float):
    """
    eal_score: e.g., normalized 0–100
    social_vulnerability, community_resilience: baseline indices (0–1 or 0–100 scaled)
    sv_delta_pct, cr_delta_pct: slider changes in percent (e.g., +0.2 = +20%)

    This is NOT FEMA’s exact formula, just a demonstration inspired by:
      Risk = EAL × f(SV / CR).
    """

    # Apply slider changes
    sv_effect = 1.0 + sv_delta_pct  # more vulnerability → higher risk
    cr_effect = 1.0 - cr_delta_pct  # more resilience → lower risk

    # Tune alpha/beta implicitly by limiting effect range
    multiplier = sv_effect * cr_effect

    adjusted_risk = eal_score * multiplier
    return adjusted_risk
