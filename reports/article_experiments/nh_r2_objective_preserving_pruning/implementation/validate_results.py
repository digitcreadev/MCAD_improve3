#!/usr/bin/env python3
import csv, json, sys
from pathlib import Path

def main(out):
    out=Path(out); gate=json.loads((out/'gate_results.json').read_text()); sessions=list(csv.DictReader((out/'session_summary.csv').open())); decisions=list(csv.DictReader((out/'decision_records.csv').open())); errs=[]
    if gate['gate']!='PASS': errs.append('gate_results != PASS')
    if any(r['objective_preserved']!='true' for r in sessions): errs.append('objective preservation failure')
    if any(int(r['safe_false_prunes'])!=0 for r in sessions): errs.append('false prune detected')
    for r in decisions:
        if r['policy']=='SAFE_PRUNING' and r['operational_action']=='PRUNE' and r['class'] in ('IMMEDIATE_CONTRIBUTOR','DEFERRED_SUPPORT_CONTRIBUTOR'): errs.append('unsafe class pruned'); break
        if r['policy']=='SAFE_PRUNING' and r['semantic_contract_valid']=='false' and r['sat']=='true' and r['operational_action']=='PRUNE': errs.append('invalid semantic contract pruned instead of fail-open'); break
    if errs:
        print('VALIDATION=FAIL'); [print(' -',e) for e in errs]; return 2
    print('VALIDATION=PASS'); print(f"sessions={len(sessions)} decisions={len(decisions)} replay_pairs={gate['safe_pruned_replay_pairs']}"); return 0
if __name__=='__main__': raise SystemExit(main(sys.argv[1]))
