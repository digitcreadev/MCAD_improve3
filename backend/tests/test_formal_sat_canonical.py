from mcad.formal_sat import evaluate_sat_formal_clauses


def test_canonical_formal_sat_accepts_foodmart_monthly_beer_wa_sales():
    query_spec = {
        "mdx": "SELECT {[Measures].[Store Sales]} ON COLUMNS, [Time].[Month].Members ON ROWS FROM [Sales] WHERE ([Product].[Product Category].[Beer and Wine], [Store].[Store State].[WA])",
        "cube": "Sales",
        "measures": ["Store Sales"],
        "group_by": ["Time.Month"],
        "slicers": {
            "Product.Product Category": "Beer and Wine",
            "Store.Store State": "WA",
        },
    }
    out = evaluate_sat_formal_clauses(query_spec, "O_REAL_BEER_WA_MONTH", query_spec["mdx"])
    assert out["sat"] is True
    assert out["checks"]["grain_ok"] is True
    assert out["checks"]["nvac_ok"] is True
    assert out["evidence"]["nvac_ok"]["method"] == "combination_nonempty_index"


def test_canonical_formal_sat_rejects_wrong_grain():
    query_spec = {
        "mdx": "SELECT {[Measures].[Store Sales]} ON COLUMNS, [Time].[Year].Members ON ROWS FROM [Sales] WHERE ([Product].[Product Category].[Beer and Wine], [Store].[Store State].[WA])",
        "cube": "Sales",
        "measures": ["Store Sales"],
        "group_by": ["Time.Year"],
        "slicers": {
            "Product.Product Category": "Beer and Wine",
            "Store.Store State": "WA",
        },
    }
    out = evaluate_sat_formal_clauses(query_spec, "O_REAL_BEER_WA_MONTH", query_spec["mdx"])
    assert out["sat"] is False
    assert out["checks"]["grain_ok"] is False
    assert out["block_reason_code"] == "BLOCK_GRAIN_MISMATCH"


def test_canonical_formal_sat_rejects_hierarchical_empty_subspace():
    query_spec = {
        "mdx": "SELECT {[Measures].[Store Sales]} ON COLUMNS, [Time].[Month].Members ON ROWS FROM [Sales] WHERE ([Store].[Store State].[CA], [Store].[Store City].[Portland], [Product].[Product Department].[Alcoholic Beverages], [Product].[Product Category].[Dairy])",
        "cube": "Sales",
        "measures": ["Store Sales"],
        "group_by": ["Time.Month"],
        "slicers": {
            "Store.Store State": "CA",
            "Store.Store City": "Portland",
            "Product.Product Department": "Alcoholic Beverages",
            "Product.Product Category": "Dairy",
        },
    }
    out = evaluate_sat_formal_clauses(query_spec, "O_REAL_BEER_WA_MONTH", query_spec["mdx"])
    assert out["sat"] is False
    assert out["checks"]["nvac_ok"] is False
    assert out["block_reason_code"] == "BLOCK_EMPTY_SUBSPACE"
    assert out["evidence"]["nvac_ok"]["method"] == "hierarchical_combination_empty_index"


def test_canonical_formal_sat_signature_exposes_optional_nvac_probe():
    import inspect

    sig = inspect.signature(evaluate_sat_formal_clauses)
    assert "nvac_probe" in sig.parameters


def test_canonical_formal_sat_uses_probe_callback_only_when_static_evidence_uncertain():
    query_spec = {
        "mdx": "SELECT {[Measures].[Store Sales]} ON COLUMNS, [Time].[Month].Members ON ROWS FROM [Sales] WHERE ([Product].[Product Category].[Carousel], [Store].[Store State].[CA])",
        "cube": "Sales",
        "measures": ["Store Sales"],
        "group_by": ["Time.Month"],
        "slicers": {
            "Product.Product Category": "Carousel",
            "Store.Store State": "CA",
        },
    }
    calls = []

    def fake_probe(features, mdx):
        calls.append((features, mdx))
        return {"probe_attempted": True, "non_empty": True, "count": 3, "probe_query": "bounded probe"}

    out = evaluate_sat_formal_clauses(query_spec, "O_REAL_BEER_WA_MONTH", query_spec["mdx"], nvac_probe=fake_probe)
    assert calls
    assert out["checks"]["nvac_ok"] is True
    assert out["evidence"]["nvac_ok"]["method"] == "hybrid_probe"
    assert out["evidence"]["nvac_ok"]["probe"]["probe_query"] == "bounded probe"
