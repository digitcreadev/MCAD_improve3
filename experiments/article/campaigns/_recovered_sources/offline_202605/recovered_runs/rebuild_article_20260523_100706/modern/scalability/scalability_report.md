# MCAD scalability and CKG growth-control report

## Catalog scalability summary

|scale_factor|n_objectives|n_constraints|n_virtual_nodes|n_nodes|n_edges|p50_eval_ms|p95_eval_ms|p99_eval_ms|snapshot_ms|snapshot_bytes|peak_total_kib|
|---|---|---|---|---|---|---|---|---|---|---|---|
|1|3|8|10|55|66|1.470688|1.83217|2.04095|12.027232|43501|252.771|
|5|11|32|42|223|306|1.526923|3.172555|3.335119|49.27171|207117|618.82|
|10|21|62|82|433|606|1.509505|2.952329|3.436829|90.06413|412597|1166.304|
|20|41|122|162|853|1206|1.793934|3.423436|4.867961|383.250351|822597|2256.121|
|40|81|242|322|1693|2406|1.855764|3.518854|4.162221|363.490718|1642597|4447.076|

## Runtime growth control (keep-last = 8 query-plan nodes)

|mode|step_idx|n_nodes|n_edges|history_len|removed_qp_nodes|eval_ms|
|---|---|---|---|---|---|---|
|no_compaction|1|655|809|0|0|0.38969|
|no_compaction|10|664|823|0|0|0.273681|
|no_compaction|20|674|836|0|0|0.27263|
|no_compaction|30|684|850|0|0|0.362841|
|no_compaction|40|694|863|0|0|0.276007|
|no_compaction|50|704|876|0|0|0.301406|
|no_compaction|60|714|890|0|0|0.357274|
|no_compaction|70|724|903|0|0|0.302562|
|no_compaction|80|734|916|0|0|0.277751|
|no_compaction|90|744|930|0|0|0.403381|
|no_compaction|100|754|943|0|0|0.369199|
|no_compaction|110|764|956|0|0|0.269412|
|no_compaction|120|774|970|0|0|0.357918|
|keep_last|1|655|809|0|0|0.605373|
|keep_last|10|662|821|0|1|0.587681|
|keep_last|20|662|820|0|1|0.318041|
|keep_last|30|662|821|0|1|0.438559|
|keep_last|40|662|821|0|1|0.282235|
|keep_last|50|662|820|0|1|0.280558|
|keep_last|60|662|821|0|1|0.366766|
|keep_last|70|662|821|0|1|0.28054|
|keep_last|80|662|820|0|1|0.280104|
|keep_last|90|662|821|0|1|0.36075|
|keep_last|100|662|821|0|1|0.279509|
|keep_last|110|662|820|0|1|0.354707|
|keep_last|120|662|821|0|1|0.363233|