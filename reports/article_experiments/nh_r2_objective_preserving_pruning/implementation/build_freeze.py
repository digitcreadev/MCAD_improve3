#!/usr/bin/env python3
import hashlib, json, sys
from pathlib import Path
root=Path(sys.argv[1]); out=Path(sys.argv[2]); gate=json.loads((out/'gate_results.json').read_text())
semantic_digest_sha=(out/'SEMANTIC_DIGEST_SHA256.txt').read_text().split()[0]
freeze={
 'freeze_id':'MCAD-NH-R2-OBJECTIVE-PRESERVING-PRUNING-CAMPAIGN-FREEZE-1',
 'parent_r1_sha256':'b12034c9658a23ad2cb588237bb462148478f6e32d42e9494019611367eecdfb',
 'parent_r1_freeze_sha256':'68538940e73d6ee8b9927f142d80abce3a8e097b6595c32ea14fbb88fb43937a',
 'config_sha256':hashlib.sha256((root/'config/r2_campaign.json').read_bytes()).hexdigest(),
 'semantic_digest_sha256':semantic_digest_sha,
 'gate':gate['gate'],'sessions':gate['sessions'],'candidate_policy_decisions':gate['candidate_policy_decisions'],
 'objective_preservation_failures':gate['objective_preservation_failures'],
 'false_prunes_immediate_or_deferred':gate['false_prunes_immediate_or_deferred'],
 'strict_immediate_completion_loss_sessions':gate['strict_immediate_completion_loss_sessions'],
 'safe_pruned_replay_pairs':gate['safe_pruned_replay_pairs'],
 'resource_claims':'NOT_PROMOTED_AT_R2',
 'next_station':'MCAD-NH-R3 End-to-End Resource Avoidance & Time-to-Objective Benchmark'
}
path=out/'MCAD_NH_R2_FREEZE.json'; path.write_text(json.dumps(freeze,indent=2,sort_keys=True)+'\n')
h=hashlib.sha256(path.read_bytes()).hexdigest(); (out/'MCAD_NH_R2_FREEZE_SHA256.txt').write_text(f'{h}  MCAD_NH_R2_FREEZE.json\n')
print('freeze_sha256='+h)
