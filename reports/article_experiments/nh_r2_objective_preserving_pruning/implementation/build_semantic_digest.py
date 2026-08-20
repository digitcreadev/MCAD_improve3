#!/usr/bin/env python3
import csv, hashlib, json, sys
from pathlib import Path

out = Path(sys.argv[1])
# Canonical semantic projection: deliberately excludes machine-dependent timing fields.
fields = [
    'session_id','split','topology','pattern','candidate_index','query_id','policy','sat',
    'semantic_contract_valid','class','safe_to_prune','operational_action','proof_status','reason',
    'phi_before','delta_phi','phi_after','novel_evidence_count','frontier_gain_count','evidence_atoms'
]
h = hashlib.sha256()
with (out/'decision_records.csv').open(newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        payload = {k:r[k] for k in fields}
        h.update((json.dumps(payload, sort_keys=True, separators=(',',':'))+'\n').encode())
projection_sha = h.hexdigest()
components = {}
for name in ['session_summary.csv','stratum_summary.csv','replay_manifest_safe_pruned.csv','replay_manifest_inadmissible.csv','r3_backend_binding_template.csv','gate_results.json']:
    components[name] = hashlib.sha256((out/name).read_bytes()).hexdigest()
doc = {
    'schema_id':'MCAD-NH-R2-SEMANTIC-DIGEST-1',
    'decision_semantic_projection_sha256':projection_sha,
    'components_sha256':components,
    'excluded_as_environment_dependent':['gate_latency_ns','gate_cpu_ns','environment.json','logs/*'],
}
path=out/'semantic_digest.json'
path.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
digest=hashlib.sha256(path.read_bytes()).hexdigest()
(out/'SEMANTIC_DIGEST_SHA256.txt').write_text(f'{digest}  semantic_digest.json\n')
print('semantic_digest_sha256='+digest)
print('decision_semantic_projection_sha256='+projection_sha)
