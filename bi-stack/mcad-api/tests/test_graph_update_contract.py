import importlib.util
import os
import sys
from pathlib import Path

os.environ.setdefault("MCAD_DATA_DIR", "/tmp/mcad-api-test-data")


def load_app_module():
    app_dir = Path(__file__).resolve().parents[1]
    app_path = app_dir / "app.py"
    assert app_path.exists(), f"app.py introuvable: {app_path}"
    sys.path.insert(0, str(app_dir))
    spec = importlib.util.spec_from_file_location("mcad_api_app_contract", app_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_default_objective_strict_mapping_remains_valid():
    app = load_app_module()
    base = {"objective_id": "O_REAL_BEER_WA_MONTH", "group_by": ["Time.Month"], "slicers": {"Store.Store State": "WA", "Product.Product Category": "Beer and Wine"}}
    assert app._infer_objective_constraint_from_qp_features({**base, "measures": ["Store Sales"]})["covered_constraints"] == ["c_sales"]
    assert app._infer_objective_constraint_from_qp_features({**base, "measures": ["Profit"]})["covered_constraints"] == ["c_profit"]
    assert app._infer_objective_constraint_from_qp_features({**base, "measures": ["Unit Sales"]})["covered_constraints"] == []
    assert app._infer_objective_constraint_from_qp_features({**base, "measures": ["Profit"], "group_by": ["Time.Year"]})["covered_constraints"] == []
    assert app._infer_objective_constraint_from_qp_features({"objective_id":"O_REAL_BEER_WA_MONTH", "measures": ["Profit"], "group_by": ["Time.Month"], "slicers": {"Store.Store State": "CA", "Product.Product Category": "Beer and Wine"}})["covered_constraints"] == []


def test_q3_then_q2_contract_state_stays_partial_after_profit_only():
    app = load_app_module()
    sid = "S_Q3_Q2"
    q3 = app._infer_objective_constraint_from_qp_features({"objective_id":"O_REAL_BEER_WA_MONTH", "measures": ["Unit Sales"], "group_by": ["Time.Month"], "slicers": {"Store.Store State": "WA", "Product.Product Category": "Beer and Wine"}})
    app._merge_graph_session_state(sid, {**q3, "objective_id":"O_REAL_BEER_WA_MONTH", "decision": "BLOCK", "step_index": 1})
    q2 = app._infer_objective_constraint_from_qp_features({"objective_id":"O_REAL_BEER_WA_MONTH", "measures": ["Profit"], "group_by": ["Time.Month"], "slicers": {"Store.Store State": "WA", "Product.Product Category": "Beer and Wine"}})
    app._merge_graph_session_state(sid, {**q2, "objective_id":"O_REAL_BEER_WA_MONTH", "decision": "ALLOW", "step_index": 2})
    state = app._public_graph_session_state(sid, "O_REAL_BEER_WA_MONTH")
    assert state["objective_state"] == "partial"
    assert state["session_phi"] == 0.5
    assert state["cumulative_covered_constraints"] == ["c_profit"]
    assert state["pending_constraints"] == ["c_sales"]
    assert state["cumulative_realized_virtual_nodes"] == ["N_c_profit"]


def test_imported_objective_contract_is_not_hard_coded_to_beer_wa():
    app = load_app_module()
    obj = {"id":"O_REAL_DAIRY_CA_MONTH","name":"Monthly Dairy CA","constraints":[{"id":"c_dairy_ca_sales","measure":"Store Sales","grain":"Time.Month","slicers":{"Store.Store State":"CA","Product.Product Category":"Dairy"},"virtual_node":"N_dairy_ca_sales"},{"id":"c_dairy_ca_profit","measure":"Profit","grain":"Time.Month","slicers":{"Store.Store State":"CA","Product.Product Category":"Dairy"},"virtual_node":"N_dairy_ca_profit"}]}
    normalized = app._normalize_imported_objective(obj)
    app._write_imported_objectives_raw([normalized])
    app._register_imported_objectives()
    base = {"objective_id":"O_REAL_DAIRY_CA_MONTH", "group_by":["Time.Month"], "slicers":{"Store.Store State":"CA", "Product.Product Category":"Dairy"}}
    sales = app._infer_objective_constraint_from_qp_features({**base, "measures":["Store Sales"]}, objective_id="O_REAL_DAIRY_CA_MONTH")
    profit = app._infer_objective_constraint_from_qp_features({**base, "measures":["Profit"]}, objective_id="O_REAL_DAIRY_CA_MONTH")
    wrong = app._infer_objective_constraint_from_qp_features({**base, "measures":["Profit"], "slicers":{"Store.Store State":"WA", "Product.Product Category":"Dairy"}}, objective_id="O_REAL_DAIRY_CA_MONTH")
    assert sales["covered_constraints"] == ["c_dairy_ca_sales"]
    assert sales["realized_virtual_nodes"] == ["N_dairy_ca_sales"]
    assert profit["covered_constraints"] == ["c_dairy_ca_profit"]
    assert wrong["covered_constraints"] == []


def test_observed_resources_are_not_promoted_and_block_never_covers():
    app = load_app_module()
    app._merge_graph_session_state("S_OBS", {"objective_id":"O_REAL_BEER_WA_MONTH", "decision":"BLOCK", "covered_constraints":["c_sales"], "realized_virtual_nodes":["N_c_sales"], "observed_resources":["N_c_sales", "Store Sales"]})
    state = app._public_graph_session_state("S_OBS", "O_REAL_BEER_WA_MONTH")
    assert state["cumulative_covered_constraints"] == []
    assert state["cumulative_realized_virtual_nodes"] == []
    assert state["observed_resources"] == ["N_c_sales", "Store Sales"]


def test_multi_kpi_objective_supports_common_mdx_grain_spellings():
    app = load_app_module()
    obj = {
        "id": "O_REAL_DAIRY_CA_MULTI_KPI",
        "name": "Multi KPI Dairy CA",
        "constraints": [
            {"id": "c_dairy_ca_sales_month", "measure": "Store Sales", "grain": "Time.Month", "slicers": {"Store.Store State": "CA", "Product.Product Category": "Dairy"}, "virtual_node": "N_dairy_ca_sales_month"},
            {"id": "c_dairy_ca_profit_month", "measure": "Profit", "grain": "Time.Month", "slicers": {"Store.Store State": "CA", "Product.Product Category": "Dairy"}, "virtual_node": "N_dairy_ca_profit_month"},
            {"id": "c_dairy_ca_profit_product_month", "measure": "Profit", "grain": ["Time.Month", "Product.Product Category"], "slicers": {"Store.Store State": "CA", "Product.Product Category": "Dairy"}, "virtual_node": "N_dairy_ca_profit_product_month"},
        ],
    }
    app._write_imported_objectives_raw([app._normalize_imported_objective(obj)])
    app._register_imported_objectives()

    q1 = "SELECT {[Measures].[Store Sales]} ON COLUMNS, {[Time].[Time].[Month].Members} ON ROWS FROM [Sales] WHERE ([Store].[Store State].[CA], [Product].[Product Category].[Dairy])"
    q2 = "SELECT {[Measures].[Profit]} ON COLUMNS, {[Time].[Month].Members} ON ROWS FROM [Sales] WHERE ([Store].[Store State].[CA], [Product].[Product Category].[Dairy])"
    q9 = "SELECT {[Measures].[Profit]} ON COLUMNS, CrossJoin({[Time].[Time].[Month].Members}, {[Product].[Product Category].Members}) ON ROWS FROM [Sales] WHERE ([Store].[Store State].[CA])"

    q1spec = app.build_query_spec(q1)
    q2spec = app.build_query_spec(q2)
    q9spec = app.build_query_spec(q9)

    assert app._infer_objective_constraint_from_qp_features({"query_spec": q1spec, "mdx": q1, "objective_id": "O_REAL_DAIRY_CA_MULTI_KPI"}, "O_REAL_DAIRY_CA_MULTI_KPI")["covered_constraints"] == ["c_dairy_ca_sales_month"]
    assert app._infer_objective_constraint_from_qp_features({"query_spec": q2spec, "mdx": q2, "objective_id": "O_REAL_DAIRY_CA_MULTI_KPI"}, "O_REAL_DAIRY_CA_MULTI_KPI")["covered_constraints"] == ["c_dairy_ca_profit_month"]
    assert app._infer_objective_constraint_from_qp_features({"query_spec": q9spec, "mdx": q9, "objective_id": "O_REAL_DAIRY_CA_MULTI_KPI"}, "O_REAL_DAIRY_CA_MULTI_KPI")["covered_constraints"] == ["c_dairy_ca_profit_product_month"]


def test_v87_objective_validation_refuses_missing_fields_and_duplicates():
    app = load_app_module()
    bad = {
        "id": "O_BAD_VALIDATION",
        "name": "Bad objective",
        "constraints": [
            {"id": "c1", "measure": "Store Sales", "grain": "Time.Month", "slicers": {}, "virtual_node": "N1"},
            {"id": "c1", "grain": [], "slicers": [], "virtual_node": "N1"},
        ],
    }
    report = app._validate_objectives_payload(bad, check_unique=False)
    assert report["ok"] is False
    joined = "\n".join(report["errors"])
    assert "duplicates c1" in joined
    assert "measure is required" in joined
    assert "grain" in joined
    assert "slicers must be an object" in joined
    assert "duplicates N1" in joined


def test_v87_objective_validation_accepts_multi_kpi_schema():
    app = load_app_module()
    obj = {
        "id": "O_VALIDATE_MULTI_KPI",
        "name": "Validation Multi KPI",
        "dw_id": "foodmart",
        "cube": "Sales",
        "constraints": [
            {"id": "c_sales", "label": "Sales", "measure": "Store Sales", "grain": "Time.Month", "slicers": {"Store.Store State": "CA"}, "virtual_node": "N_sales"},
            {"id": "c_profit", "label": "Profit", "measure": "Profit", "grain": ["Time.Month", "Product.Product Category"], "slicers": {"Store.Store State": "CA"}, "virtual_node": "N_profit"},
        ],
    }
    report = app._validate_objectives_payload(obj, check_unique=False)
    assert report["ok"] is True
    assert report["accepted_count"] == 1
    assert report["objectives"][0]["id"] == "O_VALIDATE_MULTI_KPI"


def test_v871_duplicate_objective_validation_is_warning_not_error():
    app = load_app_module()
    obj = {
        "id": "O_REAL_DAIRY_CA_MULTI_KPI",
        "name": "Multi KPI Dairy CA",
        "dw_id": "foodmart",
        "cube": "Sales",
        "constraints": [
            {"id": "c_sales", "label": "Sales", "measure": "Store Sales", "grain": "Time.Month", "slicers": {"Store.Store State": "CA"}, "virtual_node": "N_sales"}
        ],
    }
    app._write_imported_objectives_raw([app._normalize_imported_objective(obj)])
    report = app._validate_objectives_payload(obj, check_unique=True)
    assert report["ok"] is True
    assert report["status"] == "accepted_with_warnings"
    assert any("will be replaced" in w for w in report["warnings"])


def test_v88_formal_sat_nvac_accepts_known_foodmart_subspace():
    app = load_app_module()
    obj = {
        "id": "O_REAL_DAIRY_CA_MULTI_KPI",
        "name": "Multi KPI Dairy CA",
        "constraints": [
            {"id": "c_dairy_ca_sales_month", "measure": "Store Sales", "grain": "Time.Month", "slicers": {"Store.Store State": "CA", "Product.Product Category": "Dairy"}, "virtual_node": "N_dairy_ca_sales_month"},
        ],
    }
    app._write_imported_objectives_raw([app._normalize_imported_objective(obj)])
    app._register_imported_objectives()
    mdx = "SELECT {[Measures].[Store Sales]} ON COLUMNS, {[Time].[Month].Members} ON ROWS FROM [Sales] WHERE ([Store].[Store State].[CA], [Product].[Product Category].[Dairy])"
    qspec = app.build_query_spec(mdx)
    sat = app._evaluate_sat_formal_clauses(qspec, "O_REAL_DAIRY_CA_MULTI_KPI", mdx)
    assert sat["sat"] is True
    assert sat["checks"]["nvac_ok"] is True
    assert sat["evidence"]["nvac_ok"]["estimated_cells"] > 0


def test_v88_formal_sat_nvac_rejects_unknown_member_subspace():
    app = load_app_module()
    obj = {
        "id": "O_REAL_DAIRY_CA_MULTI_KPI",
        "name": "Multi KPI Dairy CA",
        "constraints": [
            {"id": "c_dairy_ca_sales_month", "measure": "Store Sales", "grain": "Time.Month", "slicers": {"Store.Store State": "CA", "Product.Product Category": "Dairy"}, "virtual_node": "N_dairy_ca_sales_month"},
        ],
    }
    app._write_imported_objectives_raw([app._normalize_imported_objective(obj)])
    app._register_imported_objectives()
    mdx = "SELECT {[Measures].[Store Sales]} ON COLUMNS, {[Time].[Month].Members} ON ROWS FROM [Sales] WHERE ([Store].[Store State].[DZ], [Product].[Product Category].[Dairy])"
    qspec = app.build_query_spec(mdx)
    sat = app._evaluate_sat_formal_clauses(qspec, "O_REAL_DAIRY_CA_MULTI_KPI", mdx)
    assert sat["sat"] is False
    assert sat["checks"]["nvac_ok"] is False or sat["checks"]["slc_ok"] is False
    assert sat["block_reason_code"] in {"BLOCK_EMPTY_SUBSPACE", "BLOCK_SLICER_MISMATCH"}


def test_v88_formal_sat_nvac_accepts_crossjoin_axis_subspace():
    app = load_app_module()
    obj = {
        "id": "O_REAL_DAIRY_CA_MULTI_KPI",
        "name": "Multi KPI Dairy CA",
        "constraints": [
            {"id": "c_dairy_ca_profit_product_month", "measure": "Profit", "grain": ["Time.Month", "Product.Product Category"], "slicers": {"Store.Store State": "CA", "Product.Product Category": "Dairy"}, "virtual_node": "N_dairy_ca_profit_product_month"},
        ],
    }
    app._write_imported_objectives_raw([app._normalize_imported_objective(obj)])
    app._register_imported_objectives()
    mdx = "SELECT {[Measures].[Profit]} ON COLUMNS, CrossJoin({[Time].[Month].Members}, {[Product].[Product Category].Members}) ON ROWS FROM [Sales] WHERE ([Store].[Store State].[CA])"
    qspec = app.build_query_spec(mdx)
    sat = app._evaluate_sat_formal_clauses(qspec, "O_REAL_DAIRY_CA_MULTI_KPI", mdx)
    assert sat["sat"] is True
    assert sat["checks"]["grain_ok"] is True
    assert sat["checks"]["nvac_ok"] is True


def test_v881_hybrid_nvac_probe_blocks_when_probe_count_zero(monkeypatch):
    app = load_app_module()
    app.MCAD_NVAC_MODE = "hybrid"
    app.MCAD_NVAC_PROBE_URL = "http://mcad-proxy:8000/bi/nvac-probe"
    app._NVAC_PROBE_CACHE.clear()

    class FakeResp:
        ok = True
        content = b"{}"
        status_code = 200
        def json(self):
            return {"ok": True, "non_empty": False, "count": 0, "probe_query": "SELECT ..."}

    monkeypatch.setattr(app.requests, "post", lambda *args, **kwargs: FakeResp())
    features = {
        "mdx": "SELECT {[Measures].[Store Sales]} ON COLUMNS, {[Time].[Month].Members} ON ROWS FROM [Sales] WHERE ([Store].[Store State].[CA], [Product].[Product Category].[Seafood])",
        "cube": "Sales",
        "measures": ["Store Sales"],
        "group_by": ["Time.Month"],
        "slicers": {"Store.Store State": "CA", "Product.Product Category": "Seafood"},
    }
    ok, evidence = app._sat_check_nvac_ok(features, "O_ANY")
    assert ok is False
    assert evidence["method"] == "hybrid_probe"
    assert evidence["probe"]["count"] == 0
    assert evidence["rule"] == "probe_count_drives_nvac_ok"


def test_v881_hybrid_nvac_probe_accepts_when_probe_count_positive(monkeypatch):
    app = load_app_module()
    app.MCAD_NVAC_MODE = "hybrid"
    app.MCAD_NVAC_PROBE_URL = "http://mcad-proxy:8000/bi/nvac-probe"
    app._NVAC_PROBE_CACHE.clear()

    class FakeResp:
        ok = True
        content = b"{}"
        status_code = 200
        def json(self):
            return {"ok": True, "non_empty": True, "count": 3, "probe_query": "SELECT ..."}

    monkeypatch.setattr(app.requests, "post", lambda *args, **kwargs: FakeResp())
    features = {
        "mdx": "SELECT {[Measures].[Store Sales]} ON COLUMNS, {[Time].[Month].Members} ON ROWS FROM [Sales] WHERE ([Store].[Store State].[CA], [Product].[Product Category].[Seafood])",
        "cube": "Sales",
        "measures": ["Store Sales"],
        "group_by": ["Time.Month"],
        "slicers": {"Store.Store State": "CA", "Product.Product Category": "Seafood"},
    }
    ok, evidence = app._sat_check_nvac_ok(features, "O_ANY")
    assert ok is True
    assert evidence["method"] == "hybrid_probe"
    assert evidence["probe"]["count"] == 3



def test_v89_decision_detail_archive_round_trip():
    app = load_app_module()
    sid = "S_DETAIL_ARCHIVE"
    item = {
        "session_id": sid,
        "objective_id": "O_REAL_BEER_WA_MONTH",
        "step_index": 1,
        "mdx": "SELECT {[Measures].[Store Sales]} ON COLUMNS FROM [Sales]",
        "decision_summary": {"decision": "ALLOW", "decision_reason_code": "ALLOW_NEW_TOTAL", "phi": 0.5},
        "sat_checks": {"grain_ok": True, "agg_ok": True, "unit_ok": True, "slc_ok": True, "time_ok": True, "nvac_ok": True},
        "nvac_evidence": {"method": "unit_test"},
        "query_spec": {"measures": ["Store Sales"]},
        "graph_update": {"covered_constraints": ["c_sales"]},
    }
    app._record_decision_detail(sid, item)
    out = app._decision_detail_by_step(sid, 1)
    assert out is not None
    assert out["decision_summary"]["decision"] == "ALLOW"
    assert out["sat_checks"]["nvac_ok"] is True
    assert out["graph_update"]["covered_constraints"] == ["c_sales"]


def test_v894_hierarchical_empty_combination_blocks_nvac_without_manual_empty_tuple():
    app = load_app_module()
    obj = {
        "id": "O_REAL_DAIRY_CA_MULTI_KPI",
        "name": "Multi KPI Dairy CA",
        "constraints": [
            {"id": "c_dairy_ca_sales_month", "measure": "Store Sales", "grain": "Time.Month", "slicers": {"Store.Store State": "CA", "Product.Product Category": "Dairy"}, "virtual_node": "N_dairy_ca_sales_month"},
        ],
    }
    app._write_imported_objectives_raw([app._normalize_imported_objective(obj)])
    app._register_imported_objectives()
    mdx = """SELECT {[Measures].[Store Sales]} ON COLUMNS,
{[Time].[Month].Members} ON ROWS
FROM [Sales]
WHERE ([Store].[Store State].[CA], [Store].[Store City].[Portland], [Product].[Product Department].[Alcoholic Beverages], [Product].[Product Category].[Dairy])"""
    qspec = app.build_query_spec(mdx)
    sat = app._evaluate_sat_formal_clauses(qspec, "O_REAL_DAIRY_CA_MULTI_KPI", mdx)
    assert sat["sat"] is False
    assert sat["checks"]["slc_ok"] is True
    assert sat["checks"]["nvac_ok"] is False
    ev = sat["evidence"]["nvac_ok"]
    assert ev["method"] == "hierarchical_combination_empty_index"
    assert ev["rule"] == "known_empty_hierarchical_combination_blocks_directly"
    assert len(ev["hierarchical_conflicts"]) >= 2
    assert sat["block_reason_code"] == "BLOCK_EMPTY_SUBSPACE"


def test_v894_extra_restrictive_slicer_does_not_use_broad_nonempty_index(monkeypatch):
    app = load_app_module()
    app.MCAD_NVAC_MODE = "hybrid"
    app.MCAD_NVAC_PROBE_URL = "http://mcad-proxy:8000/bi/nvac-probe"
    app._NVAC_PROBE_CACHE.clear()

    class FakeResp:
        ok = True
        content = b"{}"
        status_code = 200
        def json(self):
            return {"ok": True, "non_empty": True, "count": 2, "probe_query": "SELECT ..."}

    monkeypatch.setattr(app.requests, "post", lambda *args, **kwargs: FakeResp())
    features = {
        "mdx": "SELECT {[Measures].[Store Sales]} ON COLUMNS FROM [Sales] WHERE ([Store].[Store State].[CA], [Store].[Store City].[Los Angeles], [Product].[Product Category].[Dairy])",
        "cube": "Sales",
        "measures": ["Store Sales"],
        "group_by": ["Time.Month"],
        "slicers": {"Store.Store State": "CA", "Store.Store City": "Los Angeles", "Product.Product Category": "Dairy"},
    }
    ok, evidence = app._sat_check_nvac_ok(features, "O_ANY")
    assert ok is True
    assert evidence["method"] == "hybrid_probe"
    assert evidence["probe"]["count"] == 2


def test_v91_session_report_export_summarizes_formal_trace():
    app = load_app_module()
    sid = "S_V91_REPORT"
    app._write_imported_objectives_raw([app._normalize_imported_objective({
        "id": "O_V91",
        "constraints": [
            {"id": "c_sales", "measure": "Store Sales", "grain": "Time.Month", "slicers": {"Store.Store State":"CA"}, "virtual_node":"N_c_sales"},
            {"id": "c_profit", "measure": "Profit", "grain": "Time.Month", "slicers": {"Store.Store State":"CA"}, "virtual_node":"N_c_profit"},
        ],
    })])
    app._record_decision_detail(sid, {
        "session_id": sid,
        "objective_id": "O_V91",
        "step_index": 1,
        "mdx": "SELECT {[Measures].[Store Sales]} ON COLUMNS FROM [Sales] WHERE ([Store].[Store State].[CA])",
        "decision_summary": {"decision":"ALLOW", "decision_reason_code":"ALLOW_NEW_TOTAL", "formal_sat": True, "phi":0.5, "delta_phi_t":0.5},
        "sat_checks": {"grain_ok": True, "agg_ok": True, "unit_ok": True, "slc_ok": True, "time_ok": True, "nvac_ok": True},
        "nvac_evidence": {"method":"combination_nonempty_index", "estimated_cells":12},
        "query_spec": {"measures":["Store Sales"], "group_by":["Time.Month"], "slicers":{"Store.Store State":"CA"}},
        "graph_update": {"covered_constraints":["c_sales"], "realized_virtual_nodes":["N_c_sales"]},
        "formal_explanation": {"summary_fr":"Q1 contribue à c_sales."},
    })
    app._record_decision_detail(sid, {
        "session_id": sid,
        "objective_id": "O_V91",
        "step_index": 2,
        "mdx": "SELECT {[Measures].[Store Sales]} ON COLUMNS FROM [Sales] WHERE ([Store].[Store State].[DZ])",
        "decision_summary": {"decision":"BLOCK", "decision_reason_code":"BLOCK_SLICER_MISMATCH", "formal_sat": False, "phi":0, "delta_phi_t":0},
        "sat_checks": {"grain_ok": True, "agg_ok": True, "unit_ok": True, "slc_ok": False, "time_ok": True, "nvac_ok": False},
        "nvac_evidence": {"method":"member_dictionary", "estimated_cells":0},
        "query_spec": {"measures":["Store Sales"], "group_by":["Time.Month"], "slicers":{"Store.Store State":"DZ"}},
        "graph_update": {"covered_constraints":[], "realized_virtual_nodes":[]},
        "formal_explanation": {"summary_fr":"Q2 est bloquée par slc_ok."},
    })
    report = app._build_session_report(sid)
    assert report["summary"]["total_queries"] == 2
    assert report["summary"]["allow_count"] == 1
    assert report["summary"]["block_count"] == 1
    assert report["summary"]["covered_constraints"] == ["c_sales"]
    assert "c_profit" in report["summary"]["remaining_constraints"]
    assert report["rows"][1]["failed_sat_clauses"] == ["slc_ok", "nvac_ok"]
    md = app._session_report_markdown(report)
    assert "Formal trace table" in md
    assert "BLOCK_SLICER_MISMATCH" in md
    csv_text = app._session_report_csv(report)
    assert "formal_sat" in csv_text and "member_dictionary" in csv_text



def test_session_metrics_builder_exposes_formal_aggregates():
    app = load_app_module()
    sid = "S_METRICS"
    app._write_decision_details_raw({
        sid: [{
            "session_id": sid,
            "objective_id": "O_REAL_DAIRY_CA_MULTI_KPI",
            "step_index": 1,
            "decision_summary": {
                "decision": "ALLOW",
                "decision_reason_code": "ALLOW_NEW_TOTAL",
                "formal_sat": True,
                "phi": 0.2,
                "delta_phi_t": 0.2,
                "real": 0.2,
                "ceval": 0.2,
            },
            "sat_checks": {"grain_ok": True, "agg_ok": True, "unit_ok": True, "slc_ok": True, "time_ok": True, "nvac_ok": True},
            "nvac_evidence": {"method": "combination_nonempty_index", "estimated_cells": 12},
            "query_spec": {"measures": ["Store Sales"], "group_by": ["Time.Month"], "slicers": {"Store.Store State": "CA", "Product.Product Category": "Dairy"}},
            "graph_update": {"covered_constraints": ["c_dairy_ca_sales_month"], "realized_virtual_nodes": ["N_dairy_ca_sales_month"]},
            "decision": {"details": {"eval_ms": 2}},
        }]
    })
    metrics = app._build_session_metrics(sid)
    assert metrics["version"] == "mcad.experimental_metrics.v1"
    assert metrics["summary"]["total_queries"] == 1
    assert metrics["summary"]["allow_count"] == 1
    assert metrics["summary"]["sat_true_count"] == 1
    assert metrics["distributions"]["reason_code"]["ALLOW_NEW_TOTAL"] == 1
    assert metrics["trace"][0]["nvac_method"] == "combination_nonempty_index"
