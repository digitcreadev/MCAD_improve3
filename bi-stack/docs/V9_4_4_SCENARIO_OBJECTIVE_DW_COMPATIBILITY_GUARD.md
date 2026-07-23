# V9.4.4 — Scenario / Objective / DW Compatibility Guard

This patch hardens the demonstration workflow by enforcing compatibility between:

- the active MCAD objective;
- the selected physical data warehouse / execution adapter;
- the scenario's declared objective and logical dataset.

## Rules

A scenario is compatible with the active session only when:

1. `scenario.objective_id` matches the active `objective_id`, when both are known;
2. the selected `dw_id` is registered and `enabled=true`;
3. the scenario logical dataset matches the selected DW dataset;
4. FoodMart scenarios are accepted for both `foodmart` (XMLA/eMondrian) and `foodmart_sql_direct` (Direct BI), because both declare `dataset=FoodMart`;
5. disabled future DWs such as AdventureWorksDW or SteelWheels cannot be selected/executed silently.

## Backend changes

The proxy now attaches a compatibility report to scenarios:

```json
{
  "compatible": true,
  "compatibility": {
    "scenario_objective_id": "O_REAL_BEER_WA_MONTH",
    "active_objective_id": "O_REAL_BEER_WA_MONTH",
    "scenario_dataset": "foodmart",
    "selected_dataset": "foodmart",
    "errors": []
  }
}
```

`/bi/scenarios` hides incompatible scenarios by default when a session is active. Use:

```text
/bi/scenarios?include_incompatible=true
```

to inspect all scenarios and their compatibility errors.

`/bi/execute` also enforces the guard server-side. If a forced request attempts to execute an incompatible scenario, it returns a MCAD-style BLOCK without physical execution:

```text
BLOCK_SCENARIO_OBJECTIVE_DW_INCOMPATIBLE
```

## UI changes

The Scenario Runner now:

- displays only scenarios compatible with the active session;
- disables “Load into session” when the selected scenario is incompatible;
- shows compatibility details in the scenario preview;
- refuses execution of incompatible loaded scenarios;
- keeps FoodMart Q1-Q6 compatible with both FoodMart via XMLA/eMondrian and FoodMart via Direct BI.

## Expected behavior

| Active session | Scenario | Result |
|---|---|---|
| O_REAL_BEER_WA_MONTH + FoodMart XMLA | foodmart_q1_q6 | allowed |
| O_REAL_BEER_WA_MONTH + FoodMart Direct BI | foodmart_q1_q6 | allowed |
| O_REAL_DAIRY_CA_MULTI_KPI + foodmart_q1_q6 | incompatible |
| AdventureWorks_XMLA disabled + foodmart_q1_q6 | blocked / not selectable |

