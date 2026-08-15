#!/usr/bin/env python3
from __future__ import annotations
import csv
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
AN=ROOT/'_analysis'
roles={
'[root]':'Repository-level docs/license and architecture explanation.',
'docs':'Published explanatory example(s) of algorithm changes.',
'home-mixer':'Builds the For You feed: pipeline stages, scoring weights, and calls to other request-path systems.',
'candidate-pipeline':'Generic framework for source/hydrator/filter/scorer/selector/side-effect pipeline stages.',
'thunder':'In-memory recent-post source for accounts the viewer follows.',
'phoenix':'Phoenix retrieval and ranking model code, training, inference, serving, and reference tooling.',
'simclusters':'Cluster-based out-of-network candidate discovery.',
'phoenix-rankall':'Maintains the post index queried by Phoenix retrieval.',
'phoenix-rankall-strato':'Event/admission layer deciding index placement, including visibility consultation.',
'vm-ranker':'DPP-based reranking/diversity service called after scoring.',
'grox':'Post text/media understanding and classification/embedding flows.',
'media-model-proxy':'Serving layer for image/video understanding models.',
'clip':'Training/model code for image-text embeddings consumed by media classifiers.',
'adult-content':'Adult-media classifier training/calibration utilities.',
'pnsfwmedia':'Adult-media classifier combining media embeddings with account-level signals.',
'agatha':'Offline account labeling/features from blocks/reports/spam/adult-related signals.',
'bdsm':'Behavior-sequence modeling for inauthentic/abusive account behavior.',
'user-cred-v2':'Graph/PageRank-derived per-account credibility mass/score.',
'botmaker':'Rule language/compiler/runtime used by Scarecrow.',
'botmaker-rules':'Published Scarecrow/Botmaker rules; repository notes some rules are omitted.',
'scarecrow':'Event-driven labeling system embedding Botmaker.',
'safety-label-user-agg':'Aggregates post safety labels to user-level labels.',
'visibility-filtering':'Central policy evaluation deciding show/drop/interstitial-like visibility outcomes.',
'visibility-filtering-client':'Client/types used by callers of Visibility Filtering.',
'abuse-enforcement-service':'Model-score-driven account/post labeling, challenges, suspensions/enforcement.',
'under-the-hood':'Collects/serves per-account label transparency reports.'
}
def read(p):
    with p.open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
census={r['component']:r for r in read(AN/'snapshots/2026-08-15_c65aa17/component_census.csv')}
rows=read(AN/'domains/file_domain_map.csv')
by=defaultdict(list)
for r in rows: by[r['top_component']].append(r)
out=[]
for comp,c in census.items():
    if comp not in roles: raise RuntimeError(f'missing documented role: {comp}')
    doms=[]
    for r in by[comp]:
        for d in r['all_domains'].split(';'):
            if d not in doms: doms.append(d)
    out.append({'component':comp,'documented_role':roles[comp],'files':c['files'],'lines':c['lines'],'bytes':c['bytes'],
                'symlinks':c.get('symlinks','0'),'audit_domains':';'.join(doms),'cross_domain':'YES' if len(doms)>1 else 'NO',
                'verification_status':'DOCUMENTED_ROLE_NOT_YET_IMPLEMENTATION_VERIFIED'})
fields=list(out[0])
with (AN/'domains/component_map.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
with (AN/'domains/cross_domain_components.csv').open('w',newline='',encoding='utf-8') as f:
    fs=['component','audit_domains','files','lines','documented_role'];w=csv.DictWriter(f,fieldnames=fs);w.writeheader()
    for r in out:
        if r['cross_domain']=='YES':w.writerow({k:r[k] for k in fs})
print(f'components={len(out)}; cross_domain={sum(r["cross_domain"]=="YES" for r in out)}')
