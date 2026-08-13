# MCAD scalability and CKG growth-control report

## Catalog scalability summary

|scale_factor|n_objectives|n_constraints|n_virtual_nodes|n_nodes|n_edges|p50_eval_ms|p95_eval_ms|p99_eval_ms|snapshot_ms|snapshot_bytes|peak_total_kib|
|---|---|---|---|---|---|---|---|---|---|---|---|
|1|3|8|10|55|66|1.501773|1.886667|2.031167|15.273152|43501|252.771|
|5|11|32|42|223|306|1.508521|3.440881|4.572655|39.556583|207117|618.82|
|10|21|62|82|433|606|1.456249|1.858206|2.277188|118.048423|412597|1166.304|
|20|41|122|162|853|1206|1.496636|3.041131|3.772807|188.813594|822597|2256.121|
|40|81|242|322|1693|2406|1.535212|1.967695|3.049529|324.961849|1642597|4447.076|

## Runtime growth control (keep-last = 8 query-plan nodes)

|mode|step_idx|n_nodes|n_edges|history_len|removed_qp_nodes|eval_ms|
|---|---|---|---|---|---|---|
|no_compaction|1|655|809|0|0|0.378522|
|no_compaction|10|664|823|0|0|0.279078|
|no_compaction|20|674|836|0|0|0.270579|
|no_compaction|30|684|850|0|0|0.363341|
|no_compaction|40|694|863|0|0|0.274997|
|no_compaction|50|704|876|0|0|0.27131|
|no_compaction|60|714|890|0|0|0.36643|
|no_compaction|70|724|903|0|0|0.279809|
|no_compaction|80|734|916|0|0|0.275493|
|no_compaction|90|744|930|0|0|0.365123|
|no_compaction|100|754|943|0|0|0.308936|
|no_compaction|110|764|956|0|0|0.270357|
|no_compaction|120|774|970|0|0|0.35367|
|keep_last|1|655|809|0|0|0.419361|
|keep_last|10|662|821|0|1|0.280452|
|keep_last|20|662|820|0|1|0.271326|
|keep_last|30|662|821|0|1|0.368281|
|keep_last|40|662|821|0|1|0.49137|
|keep_last|50|662|820|0|1|0.607283|
|keep_last|60|662|821|0|1|0.412843|
|keep_last|70|662|821|0|1|0.290729|
|keep_last|80|662|820|0|1|0.274976|
|keep_last|90|662|821|0|1|0.359489|
|keep_last|100|662|821|0|1|0.279903|
|keep_last|110|662|820|0|1|0.27243|
|keep_last|120|662|821|0|1|0.36785|