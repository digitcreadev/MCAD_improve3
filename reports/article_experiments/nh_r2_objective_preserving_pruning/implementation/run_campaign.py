#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, hashlib, json, platform, random, subprocess, sys, time
from collections import Counter, defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from reference_model import Query, classify, computable_constraints, execute_if_kept, phi, operational_prune_decision, IMMEDIATE, DEFERRED

POLICIES=("PERMISSIVE","SAFE_PRUNING","STRICT_IMMEDIATE")

def stable_seed(master:int, *parts:str)->int:
    b=(str(master)+'|'+'|'.join(parts)).encode()
    return int.from_bytes(hashlib.sha256(b).digest()[:8], 'big')

def make_spec(topology:str, sid:str):
    p=sid.replace('-','_')
    if topology=='SINGLE':
        return {f'{p}_C1':(frozenset({f'{p}_a'}),), f'{p}_C2':(frozenset({f'{p}_b'}),), f'{p}_C3':(frozenset({f'{p}_c'}),)}
    if topology=='MULTI2':
        return {f'{p}_C1':(frozenset({f'{p}_a1',f'{p}_a2'}),), f'{p}_C2':(frozenset({f'{p}_b1',f'{p}_b2'}),), f'{p}_C3':(frozenset({f'{p}_c1',f'{p}_c2'}),)}
    if topology=='ALTERNATIVE':
        return {f'{p}_C1':(frozenset({f'{p}_a1',f'{p}_a2'}),frozenset({f'{p}_a3'})), f'{p}_C2':(frozenset({f'{p}_b1',f'{p}_b2'}),frozenset({f'{p}_b3'})), f'{p}_C3':(frozenset({f'{p}_c1',f'{p}_c2'}),frozenset({f'{p}_c3'}))}
    if topology=='OVERLAP':
        return {f'{p}_C1':(frozenset({f'{p}_shared',f'{p}_a'}),), f'{p}_C2':(frozenset({f'{p}_shared',f'{p}_b'}),), f'{p}_C3':(frozenset({f'{p}_shared2',f'{p}_c'}),)}
    raise ValueError(topology)

def objective_atoms(spec):
    s=set()
    for fam in spec.values():
        for sup in fam: s.update(sup)
    return sorted(s)

def candidate_templates(spec,sid,pattern,n,rng):
    atoms=objective_atoms(spec); distract=[f'{sid}_d{i}' for i in range(1,9)]; c=[]
    for a in atoms: c.append((True,frozenset({a}),f'ATOM_{a}'))
    vals=list(atoms)
    for i in range(0,min(len(vals)-1,6),2): c.append((True,frozenset(vals[i:i+2]),f'PAIR_{i}'))
    for a in atoms[:min(5,len(atoms))]: c.append((True,frozenset({a}),f'REPEAT_{a}'))
    for d in distract[:(8 if pattern=='DISTRACTOR_HEAVY' else 4)]: c.append((True,frozenset({d}),f'DIST_{d}'))
    for i in range(5 if pattern=='MIXED_SAT' else 2): c.append((False,frozenset({f'{sid}_inad_{i}'}),f'INAD_{i}'))
    while len(c)<n:
        roll=rng.random()
        if roll<.35:
            a=rng.choice(atoms); c.append((True,frozenset({a}),f'RPT_{len(c)}_{a}'))
        elif roll<.75:
            d=rng.choice(distract); c.append((True,frozenset({d}),f'DST_{len(c)}_{d}'))
        else:
            a=rng.choice(atoms); d=rng.choice(distract); c.append((True,frozenset({a,d}),f'MIX_{len(c)}'))
    c=c[:n]
    if pattern=='ORDERED': pass
    elif pattern=='OUT_OF_ORDER': c=list(reversed(c[:len(atoms)]))+c[len(atoms):]
    elif pattern in ('OVERLAP','DISTRACTOR_HEAVY','MIXED_SAT'): rng.shuffle(c)
    else: raise ValueError(pattern)
    return c

def split_for_rep(rep,reps):
    x=rep/reps
    return 'dev' if x<.5 else ('val' if x<.75 else 'test')

def git_info(root):
    def g(*a):
        try: return subprocess.check_output(['git','-C',str(root),*a],text=True,stderr=subprocess.DEVNULL).strip()
        except Exception: return 'UNAVAILABLE'
    return {'branch':g('branch','--show-current'),'head':g('rev-parse','HEAD'),'status':g('status','--short','--branch')}

def write_csv(path,rows,fieldnames=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    if fieldnames is None: fieldnames=list(rows[0].keys()) if rows else []
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fieldnames); w.writeheader(); w.writerows(rows)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config',required=True); ap.add_argument('--out',required=True); ap.add_argument('--repo-root',default='.')
    args=ap.parse_args(); cfg=json.loads(Path(args.config).read_text()); out=Path(args.out); out.mkdir(parents=True,exist_ok=True); repo=Path(args.repo_root).resolve()
    master=int(cfg['master_seed']); n=int(cfg['candidates_per_session']); reps=int(cfg['replicates_per_stratum']); invalid_rate=float(cfg['semantic_contract_invalid_rate'])
    env={'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),'git':git_info(repo),'config':cfg,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    (out/'environment.json').write_text(json.dumps(env,indent=2,sort_keys=True))
    decisions=[]; sessions=[]; replay=[]; inad=[]; strata=defaultdict(Counter); total=0
    for topology in cfg['support_topologies']:
      for pattern in cfg['sequence_patterns']:
       for rep in range(reps):
        sid=f'NH2-{topology}-{pattern}-R{rep+1:03d}'; split=split_for_rep(rep,reps); rng=random.Random(stable_seed(master,topology,pattern,str(rep))); spec=make_spec(topology,sid)
        templ=candidate_templates(spec,sid,pattern,n,rng); flags=[random.Random(stable_seed(master,'contract',sid,str(i))).random()>=invalid_rate for i in range(1,n+1)]
        queries=[Query(f'{sid}-Q{i:02d}-{lab}',sat,real) for i,(sat,real,lab) in enumerate(templ,1)]
        states={p:frozenset() for p in POLICIES}; execs={p:0 for p in POLICIES}; fullcand={p:None for p in POLICIES}; fullexec={p:None for p in POLICIES}; safe_false=0; session_start=len(decisions)
        for idx,(q,contract_valid) in enumerate(zip(queries,flags),1):
            for policy in POLICIES:
                e=states[policy]; t0=time.perf_counter_ns(); c0=time.process_time_ns(); r=classify(spec,e,q)
                if policy=='PERMISSIVE': action='REJECT_INADMISSIBLE' if not q.sat else 'EXECUTE'; proof='SAT_SEPARATE' if not q.sat else 'PERMISSIVE_BASELINE'
                elif policy=='SAFE_PRUNING':
                    d=operational_prune_decision(spec,e,q,contract_valid); r=d; action=d['operational_action']; proof=d['proof_status']
                else:
                    if not q.sat: action='REJECT_INADMISSIBLE'; proof='SAT_SEPARATE'
                    elif not contract_valid: action='EXECUTE_FAIL_OPEN'; proof='UNPROVEN_SEMANTIC_CONTRACT'
                    elif float(r['delta_phi'])>0: action='EXECUTE'; proof='STRICT_IMMEDIATE_POSITIVE_DELTA'
                    else: action='PRUNE'; proof='STRICT_IMMEDIATE_ZERO_DELTA'
                c1=time.process_time_ns(); t1=time.perf_counter_ns(); keep=action in ('EXECUTE','EXECUTE_FAIL_OPEN'); e2=execute_if_kept(e,q,keep)
                if keep: execs[policy]+=1
                if phi(spec,e2)>=1.0 and fullcand[policy] is None: fullcand[policy]=idx; fullexec[policy]=execs[policy]
                row={'session_id':sid,'split':split,'topology':topology,'pattern':pattern,'candidate_index':idx,'query_id':q.query_id,'policy':policy,'sat':str(q.sat).lower(),'semantic_contract_valid':str(contract_valid).lower(),'class':r['class'],'safe_to_prune':str(bool(r.get('safe_to_prune',False))).lower(),'operational_action':action,'proof_status':proof,'reason':r['reason'],'phi_before':f'{phi(spec,e):.12f}','delta_phi':f'{float(r["delta_phi"]):.12f}','phi_after':f'{phi(spec,e2):.12f}','novel_evidence_count':len(r['novel']),'frontier_gain_count':len(r['frontier_gain']),'gate_latency_ns':t1-t0,'gate_cpu_ns':c1-c0,'evidence_atoms':'|'.join(sorted(q.real))}
                decisions.append(row)
                if policy=='SAFE_PRUNING':
                    if action=='PRUNE' and r['class'] in (IMMEDIATE,DEFERRED): safe_false+=1
                    if action=='PRUNE': replay.append({'session_id':sid,'split':split,'candidate_index':idx,'query_id':q.query_id,'class':r['class'],'reason':r['reason'],'evidence_atoms':'|'.join(sorted(q.real)),'treatment_action':'PRUNE','counterfactual_action':'EXECUTE_PERMISSIVE_REPLAY','backend_binding_status':'NEEDS_WAREHOUSE_BINDING_R3'})
                    elif action=='REJECT_INADMISSIBLE': inad.append({'session_id':sid,'split':split,'candidate_index':idx,'query_id':q.query_id,'class':r['class'],'reason':r['reason'],'evidence_atoms':'|'.join(sorted(q.real)),'treatment_action':'REJECT_INADMISSIBLE','counterfactual_action':'EXECUTE_ONLY_IF_R3_MEASURES_INADMISSIBLE_COST','backend_binding_status':'NEEDS_WAREHOUSE_BINDING_R3'})
                states[policy]=e2
        final={p:phi(spec,states[p]) for p in POLICIES}; preservation=abs(final['SAFE_PRUNING']-final['PERMISSIVE'])<1e-12 and computable_constraints(spec,states['SAFE_PRUNING'])==computable_constraints(spec,states['PERMISSIVE']); strict_loss=final['STRICT_IMMEDIATE']+1e-12<final['PERMISSIVE']; total+=1
        block=decisions[session_start:]
        safe_block=[r for r in block if r['policy']=='SAFE_PRUNING']
        safe_pruned=sum(r['operational_action']=='PRUNE' for r in safe_block); safe_rej=sum(r['operational_action']=='REJECT_INADMISSIBLE' for r in safe_block); safe_fo=sum(r['operational_action']=='EXECUTE_FAIL_OPEN' for r in safe_block)
        strata[(split,topology,pattern)]['sessions']+=1; strata[(split,topology,pattern)]['safe_pruned']+=safe_pruned; strata[(split,topology,pattern)]['strict_loss']+=int(strict_loss)
        sessions.append({'session_id':sid,'split':split,'topology':topology,'pattern':pattern,'candidates':n,'permissive_executed':execs['PERMISSIVE'],'safe_executed':execs['SAFE_PRUNING'],'strict_executed':execs['STRICT_IMMEDIATE'],'safe_pruned':safe_pruned,'safe_rejected_inadmissible':safe_rej,'safe_fail_open_exec':safe_fo,'safe_false_prunes':safe_false,'phi_final_permissive':f'{final["PERMISSIVE"]:.12f}','phi_final_safe':f'{final["SAFE_PRUNING"]:.12f}','phi_final_strict':f'{final["STRICT_IMMEDIATE"]:.12f}','objective_preserved':str(preservation).lower(),'strict_completion_loss':str(strict_loss).lower(),'first_full_phi_candidate_permissive':fullcand['PERMISSIVE'] or '','first_full_phi_candidate_safe':fullcand['SAFE_PRUNING'] or '','first_full_phi_backend_exec_permissive':fullexec['PERMISSIVE'] or '','first_full_phi_backend_exec_safe':fullexec['SAFE_PRUNING'] or ''})
    write_csv(out/'decision_records.csv',decisions); write_csv(out/'session_summary.csv',sessions); write_csv(out/'replay_manifest_safe_pruned.csv',replay); write_csv(out/'replay_manifest_inadmissible.csv',inad)
    write_csv(out/'stratum_summary.csv',[{'split':k[0],'topology':k[1],'pattern':k[2],**dict(v)} for k,v in sorted(strata.items())])
    safe_rows=[r for r in decisions if r['policy']=='SAFE_PRUNING']; class_counts=Counter(r['class'] for r in safe_rows); action_counts=Counter(r['operational_action'] for r in safe_rows); preserved=sum(r['objective_preserved']=='true' for r in sessions); false=sum(int(r['safe_false_prunes']) for r in sessions); strict_losses=sum(r['strict_completion_loss']=='true' for r in sessions)
    gate={'gate':'PASS' if preserved==total and false==0 else 'FAIL','sessions':total,'candidates_per_session':n,'candidate_policy_decisions':len(decisions),'safe_policy_candidates':len(safe_rows),'objective_preservation_sessions':preserved,'objective_preservation_failures':total-preserved,'false_prunes_immediate_or_deferred':false,'strict_immediate_completion_loss_sessions':strict_losses,'safe_class_counts':dict(class_counts),'safe_action_counts':dict(action_counts),'safe_pruned_replay_pairs':len(replay),'inadmissible_counterfactual_rows':len(inad),'resource_claims':'NOT_PROMOTED_AT_R2','next_station':'MCAD-NH-R3 End-to-End Resource Avoidance & Time-to-Objective Benchmark'}
    (out/'gate_results.json').write_text(json.dumps(gate, indent=2, sort_keys=True) + '\n')
    qids=sorted({r['query_id'] for r in replay+inad}); write_csv(out/'r3_backend_binding_template.csv',[{'query_id':q,'warehouse_id':'','backend_adapter':'','query_template_path':'','parameter_binding':'','notes':''} for q in qids])
    print(json.dumps(gate,indent=2,sort_keys=True)); return 0 if gate['gate']=='PASS' else 2
if __name__=='__main__': raise SystemExit(main())
