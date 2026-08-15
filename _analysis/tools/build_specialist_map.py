#!/usr/bin/env python3
from __future__ import annotations
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AN = ROOT / "_analysis"
SRC = AN / "domains" / "file_domain_map.csv"
OUT = AN / "passes" / "file_specialist_map.csv"

COMPONENT = {
    "[root]": ["S00"], "docs": ["S00"],
    "candidate-pipeline": ["S01"], "home-mixer": ["S01"],
    "thunder": ["S03"], "simclusters": ["S04"], "phoenix": ["S05", "S06"],
    "phoenix-rankall": ["S07"], "phoenix-rankall-strato": ["S07"], "vm-ranker": ["S08"],
    "grox": ["S09"], "media-model-proxy": ["S10"], "clip": ["S10"],
    "adult-content": ["S10"], "pnsfwmedia": ["S10"],
    "agatha": ["S11"], "bdsm": ["S11"], "user-cred-v2": ["S11"],
    "botmaker": ["S12"], "botmaker-rules": ["S13"], "scarecrow": ["S13"],
    "safety-label-user-agg": ["S13"], "visibility-filtering": ["S14"],
    "visibility-filtering-client": ["S14"], "abuse-enforcement-service": ["S15"],
    "under-the-hood": ["S16"],
}

def add(xs, x):
    if x not in xs: xs.append(x)

rows=[]
for r in csv.DictReader(SRC.open(newline="", encoding="utf-8")):
    passes=list(COMPONENT[r["top_component"]])
    p=r["path"].lower(); ds=set(r["all_domains"].split(";"))
    # Home Mixer gets explicit behavior specialists in addition to orchestration.
    if r["top_component"] == "home-mixer":
        if "D07" in ds or "D08" in ds or p.startswith("home-mixer/selectors/") or p.startswith("home-mixer/ads/"):
            add(passes,"S02")
        if "D02" in ds: add(passes,"S03")
        if "D03" in ds or "D05" in ds: add(passes,"S05")
        if "D06" in ds: add(passes,"S08")
        if "D12" in ds: add(passes,"S14")
    # Cross-repo control/ops specialists receive only explicitly tagged material.
    if "D17" in ds or r["is_config"] == "YES": add(passes,"S17")
    if "D18" in ds or "D19" in ds or r["is_build"] == "YES": add(passes,"S18")
    if not passes: raise RuntimeError(r["path"])
    rows.append({"path":r["path"], "top_component":r["top_component"],
                 "specialist_passes":";".join(passes), "primary_specialist":passes[0],
                 "review_treatment":r["review_treatment"], "all_domains":r["all_domains"]})

if len(rows)!=2016 or len({r['path'] for r in rows})!=2016:
    raise RuntimeError("specialist mapping denominator mismatch")
with OUT.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
counts=Counter()
for r in rows:
    for p in r['specialist_passes'].split(';'): counts[p]+=1
with (AN/'passes'/'specialist_summary.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f); w.writerow(['pass_id','assigned_files_including_overlap'])
    for p in sorted(counts): w.writerow([p,counts[p]])
print(f"Assigned {len(rows)} files; unassigned=0; specialist passes={len(counts)}")
