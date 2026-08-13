# MCAD scalability and CKG growth-control report

## Catalog scalability summary

|scale_factor|n_objectives|n_constraints|n_virtual_nodes|n_nodes|n_edges|p50_eval_ms|p95_eval_ms|p99_eval_ms|snapshot_ms|snapshot_bytes|peak_total_kib|
|---|---|---|---|---|---|---|---|---|---|---|---|
|1|3|8|10|55|66|2.701838|3.935693|4.487752|8.932515|43501|252.771|
|5|11|32|42|223|306|1.510632|3.30455|3.942645|39.59247|207117|618.763|
|10|21|62|82|433|606|1.462686|1.891393|2.700235|77.966517|412597|1166.304|
|20|41|122|162|853|1206|1.466121|1.839732|2.299032|158.73983|822597|2256.063|
|40|81|242|322|1693|2406|1.549064|2.864236|3.761226|334.331601|1642597|4447.076|

## Runtime growth control (keep-last = 8 query-plan nodes)

|mode|step_idx|n_nodes|n_edges|history_len|removed_qp_nodes|eval_ms|
|---|---|---|---|---|---|---|
|no_compaction|1|655|809|0|0|0.768482|
|no_compaction|10|664|823|0|0|0.554906|
|no_compaction|20|674|836|0|0|0.551026|
|no_compaction|30|684|850|0|0|0.72555|
|no_compaction|40|694|863|0|0|0.58544|
|no_compaction|50|704|876|0|0|0.546145|
|no_compaction|60|714|890|0|0|0.407056|
|no_compaction|70|724|903|0|0|0.269214|
|no_compaction|80|734|916|0|0|0.824265|
|no_compaction|90|744|930|0|0|0.692918|
|no_compaction|100|754|943|0|0|1.619627|
|no_compaction|110|764|956|0|0|0.572024|
|no_compaction|120|774|970|0|0|0.671824|
|keep_last|1|655|809|0|0|0.352192|
|keep_last|10|662|821|0|1|0.282565|
|keep_last|20|662|820|0|1|0.280889|
|keep_last|30|662|821|0|1|0.382203|
|keep_last|40|662|821|0|1|0.279345|
|keep_last|50|662|820|0|1|0.283037|
|keep_last|60|662|821|0|1|0.365827|
|keep_last|70|662|821|0|1|0.270715|
|keep_last|80|662|820|0|1|0.281507|
|keep_last|90|662|821|0|1|0.364648|
|keep_last|100|662|821|0|1|0.27721|
|keep_last|110|662|820|0|1|0.304576|
|keep_last|120|662|821|0|1|0.37414|