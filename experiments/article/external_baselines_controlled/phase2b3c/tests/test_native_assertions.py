def test_assertions_are_exact(assertions):
    a = assertions["assertions"]
    assert a["DirectNoveltyTest"] == {"repeated query": "0.0", "novel query": "1.0"}
    assert a["PartialSyntacticAveragePeculiarityTest"] == {"query 1": "0.25", "query 2": "0.2333333333333333"}
    assert a["LabelSurpriseTest"] == {"value": "0.25"}
    assert a["IndirectNoveltyTest"] == {"loan test": "0.7857142857142857", "adult cases": ["1.0", "0.0", "0.14070321452264645", "0.0"]}
    assert a["PartialDetailedExtensionalRelevanceTest"] == {"loan test": "0.21428571428571427", "adult cases": ["0.0", "1.0", "0.8592967854773536", "1.0"]}


def test_asserted_classes_equal_track_classes(assertions, plan):
    classes = plan["tracks"]["PRE_NATIVE_SMOKE"]["junit_classes"] + plan["tracks"]["POST_NATIVE_SMOKE"]["junit_classes"]
    assert set(assertions["assertions"]) == set(classes)
