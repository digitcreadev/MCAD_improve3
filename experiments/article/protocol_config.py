"""Configuration of the experimental evaluation reported in the article.

This module intentionally avoids historical or versioned terminology.  It
defines the protocol that is reported in the paper.
"""

from __future__ import annotations

SEED_DEFAULT = 20260625
BOOTSTRAP_DEFAULT = 2000

CAMPAIGN_A = {
    "name": "FoodMart core evaluation",
    "datasets": ["FoodMart"],
    "objectives": 2,
    "session_lengths": 5,
    "policies": 4,
    "repetitions_per_cell": 75,
    "sessions": 3000,
}

CAMPAIGN_B = {
    "name": "Multi-dataset generalization",
    "datasets": ["FoodMart", "AdventureWorksDW", "SteelWheels"],
    "objectives_per_dataset": 2,
    "policies": 4,
    "effective_repetitions_per_dataset_objective_policy": 50,
    "sessions": 1200,
}

CAMPAIGN_C = {
    "name": "Backend portability validation",
    "datasets": ["AdventureWorksDW", "SteelWheels"],
    "backends": ["SQL Direct", "XMLA/eMondrian"],
    "scenario_families": 4,
    "repetitions_per_scenario_backend_dataset_cell": 30,
    "validations": 480,
}

TOTAL_SESSIONS_OR_VALIDATIONS = 4680
TOTAL_QUERY_DECISIONS = 37440

EXPECTED_COUNTS = {
    "campaign_a_sessions": 3000,
    "campaign_b_sessions": 1200,
    "campaign_c_validations": 480,
    "total_sessions_or_validations": TOTAL_SESSIONS_OR_VALIDATIONS,
    "total_query_decisions": TOTAL_QUERY_DECISIONS,
}
