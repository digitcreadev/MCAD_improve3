# MCAD scalability and CKG growth-control report

## Catalog scalability summary

|scale_factor|n_objectives|n_constraints|n_virtual_nodes|n_nodes|n_edges|p50_eval_ms|p95_eval_ms|p99_eval_ms|snapshot_ms|snapshot_bytes|peak_total_kib|
|---|---|---|---|---|---|---|---|---|---|---|---|
|1|3|8|10|55|66|1.508555|2.162718|2.509213|10.594221|43501|252.771|
|5|11|32|42|223|306|1.71426|3.380992|4.029478|40.904149|207117|618.82|
|10|21|62|82|433|606|1.76735|3.519697|5.635449|79.100456|412597|1166.304|
|20|41|122|162|853|1206|1.471164|2.044209|3.052011|158.160649|822597|2256.121|
|40|81|242|322|1693|2406|1.580361|4.176775|8.105856|349.505275|1642597|4447.076|

## Runtime growth control (keep-last = 8 query-plan nodes)

|mode|step_idx|n_nodes|n_edges|history_len|removed_qp_nodes|eval_ms|
|---|---|---|---|---|---|---|
|no_compaction|1|655|809|0|0|2.651851|
|no_compaction|10|664|823|0|0|0.496095|
|no_compaction|20|674|836|0|0|0.491962|
|no_compaction|30|684|850|0|0|0.655362|
|no_compaction|40|694|863|0|0|0.508323|
|no_compaction|50|704|876|0|0|0.42482|
|no_compaction|60|714|890|0|0|0.671506|
|no_compaction|70|724|903|0|0|0.517276|
|no_compaction|80|734|916|0|0|0.434553|
|no_compaction|90|744|930|0|0|0.65747|
|no_compaction|100|754|943|0|0|0.540991|
|no_compaction|110|764|956|0|0|0.483413|
|no_compaction|120|774|970|0|0|0.661582|
|keep_last|1|655|809|0|0|3.080484|
|keep_last|10|662|821|0|1|0.590726|
|keep_last|20|662|820|0|1|0.523257|
|keep_last|30|662|821|0|1|0.992711|
|keep_last|40|662|821|0|1|0.774041|
|keep_last|50|662|820|0|1|0.277638|
|keep_last|60|662|821|0|1|0.393144|
|keep_last|70|662|821|0|1|0.283407|
|keep_last|80|662|820|0|1|0.271181|
|keep_last|90|662|821|0|1|0.406066|
|keep_last|100|662|821|0|1|0.287167|
|keep_last|110|662|820|0|1|0.272783|
|keep_last|120|662|821|0|1|0.362367|