# MCAD scalability and CKG growth-control report

## Catalog scalability summary

|scale_factor|n_objectives|n_constraints|n_virtual_nodes|n_nodes|n_edges|p50_eval_ms|p95_eval_ms|p99_eval_ms|snapshot_ms|snapshot_bytes|peak_total_kib|
|---|---|---|---|---|---|---|---|---|---|---|---|
|1|3|8|10|55|66|2.911372|4.318592|6.641977|17.583291|43501|252.771|
|5|11|32|42|223|306|1.566679|2.541466|3.016873|39.811955|207117|618.82|
|10|21|62|82|433|606|1.498528|2.728499|3.118112|86.2125|412597|1166.304|
|20|41|122|162|853|1206|1.774246|3.310394|5.649274|288.200093|822597|2256.121|
|40|81|242|322|1693|2406|1.859573|3.594842|6.447994|351.960872|1642597|4447.076|

## Runtime growth control (keep-last = 8 query-plan nodes)

|mode|step_idx|n_nodes|n_edges|history_len|removed_qp_nodes|eval_ms|
|---|---|---|---|---|---|---|
|no_compaction|1|655|809|0|0|0.400243|
|no_compaction|10|664|823|0|0|0.284663|
|no_compaction|20|674|836|0|0|0.274496|
|no_compaction|30|684|850|0|0|0.367526|
|no_compaction|40|694|863|0|0|0.27699|
|no_compaction|50|704|876|0|0|0.273315|
|no_compaction|60|714|890|0|0|0.363047|
|no_compaction|70|724|903|0|0|0.278562|
|no_compaction|80|734|916|0|0|0.278391|
|no_compaction|90|744|930|0|0|0.423357|
|no_compaction|100|754|943|0|0|0.627039|
|no_compaction|110|764|956|0|0|0.561762|
|no_compaction|120|774|970|0|0|0.824767|
|keep_last|1|655|809|0|0|0.680799|
|keep_last|10|662|821|0|1|0.805886|
|keep_last|20|662|820|0|1|0.448079|
|keep_last|30|662|821|0|1|0.759501|
|keep_last|40|662|821|0|1|0.787391|
|keep_last|50|662|820|0|1|0.476727|
|keep_last|60|662|821|0|1|0.648191|
|keep_last|70|662|821|0|1|0.61111|
|keep_last|80|662|820|0|1|0.458742|
|keep_last|90|662|821|0|1|0.366127|
|keep_last|100|662|821|0|1|0.284083|
|keep_last|110|662|820|0|1|0.27487|
|keep_last|120|662|821|0|1|0.371832|