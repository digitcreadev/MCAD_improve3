# MCAD scalability and CKG growth-control report

## Catalog scalability summary

|scale_factor|n_objectives|n_constraints|n_virtual_nodes|n_nodes|n_edges|p50_eval_ms|p95_eval_ms|p99_eval_ms|snapshot_ms|snapshot_bytes|peak_total_kib|
|---|---|---|---|---|---|---|---|---|---|---|---|
|1|3|8|10|55|66|1.794447|3.263668|3.301457|9.051191|43501|252.771|
|5|11|32|42|223|306|1.694423|3.21374|6.150266|49.759097|207117|618.763|
|10|21|62|82|433|606|1.590491|2.862402|3.288563|88.795865|412597|1166.304|
|20|41|122|162|853|1206|1.782258|3.467445|5.314343|404.249752|822597|2256.121|
|40|81|242|322|1693|2406|1.61928|3.250328|3.614202|358.130254|1642597|4447.076|

## Runtime growth control (keep-last = 8 query-plan nodes)

|mode|step_idx|n_nodes|n_edges|history_len|removed_qp_nodes|eval_ms|
|---|---|---|---|---|---|---|
|no_compaction|1|655|809|0|0|0.610717|
|no_compaction|10|664|823|0|0|0.520561|
|no_compaction|20|674|836|0|0|0.500148|
|no_compaction|30|684|850|0|0|0.699618|
|no_compaction|40|694|863|0|0|0.528388|
|no_compaction|50|704|876|0|0|0.283441|
|no_compaction|60|714|890|0|0|0.366558|
|no_compaction|70|724|903|0|0|0.273388|
|no_compaction|80|734|916|0|0|0.272941|
|no_compaction|90|744|930|0|0|0.364255|
|no_compaction|100|754|943|0|0|0.305983|
|no_compaction|110|764|956|0|0|0.271503|
|no_compaction|120|774|970|0|0|0.370925|
|keep_last|1|655|809|0|0|0.339436|
|keep_last|10|662|821|0|1|0.282196|
|keep_last|20|662|820|0|1|0.508691|
|keep_last|30|662|821|0|1|0.514058|
|keep_last|40|662|821|0|1|0.506563|
|keep_last|50|662|820|0|1|0.508101|
|keep_last|60|662|821|0|1|0.367695|
|keep_last|70|662|821|0|1|0.276532|
|keep_last|80|662|820|0|1|0.295786|
|keep_last|90|662|821|0|1|0.38407|
|keep_last|100|662|821|0|1|0.277757|
|keep_last|110|662|820|0|1|0.275452|
|keep_last|120|662|821|0|1|0.372926|