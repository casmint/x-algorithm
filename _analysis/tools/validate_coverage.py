#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AN = ROOT / '_analysis'
SNAP = AN / 'snapshots' / '2026-08-15_c65aa17'

def read_rows(p: Path):
    with p.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def object_bytes(fp: Path, is_symlink: bool) -> bytes:
    if is_symlink and fp.is_symlink():
        return os.readlink(fp).encode()
    # GitHub ZIP extraction may materialize a symlink as a regular file containing the link target.
    return fp.read_bytes()

checks=[]
def check(name: str, cond: bool, detail: str=''):
    checks.append((name, bool(cond), detail))
    if not cond:
        raise AssertionError(f'{name}: {detail}')

manifest = read_rows(SNAP / 'file_manifest.csv')
dom = read_rows(AN / 'domains' / 'file_domain_map.csv')
passes = read_rows(AN / 'passes' / 'file_specialist_map.csv')
ledger = read_rows(AN / 'coverage_ledger.csv')
dcat = read_rows(AN / 'domains' / 'domain_catalog.csv')
manual = read_rows(AN / 'domains' / 'manual_attention.csv')
components = read_rows(AN / 'domains' / 'component_map.csv')

mset={r['path'] for r in manifest}; dset={r['path'] for r in dom}; pset={r['path'] for r in passes}; lset={r['path'] for r in ledger}
check('baseline_manifest_count', len(manifest)==2016, str(len(manifest)))
check('baseline_manifest_unique', len(mset)==2016, str(len(mset)))
check('domain_map_exact_path_set', dset==mset, f'domain={len(dset)} manifest={len(mset)}')
check('specialist_map_exact_path_set', pset==mset, f'pass={len(pset)} manifest={len(mset)}')
check('coverage_ledger_exact_path_set', lset==mset, f'ledger={len(lset)} manifest={len(mset)}')
check('manual_classification_queue_empty', len(manual)==0, str(len(manual)))

valid_domains={r['domain_id'] for r in dcat}
check('domain_catalog_count', len(valid_domains)==20, str(len(valid_domains)))
check('all_files_have_domain', all(r['all_domains'] for r in dom))
check('all_domain_ids_valid', all(set(r['all_domains'].split(';')) <= valid_domains for r in dom))
check('all_assignment_confidence_high', all(r['classification_confidence']=='HIGH' for r in dom))
check('all_files_have_review_treatment', all(r['review_treatment'] for r in dom))
check('primary_domain_partition_is_2016', len(dom)==2016)

valid_passes={f'S{i:02d}' for i in range(19)}
check('all_files_have_specialist', all(r['specialist_passes'] for r in passes))
check('all_specialist_ids_valid', all(set(r['specialist_passes'].split(';')) <= valid_passes for r in passes))
check('component_catalog_covers_all_top_components', {r['component'] for r in components} == {r['top_component'] for r in manifest})

check('all_review_states_still_unreviewed', all(r['review_status']=='UNREVIEWED' for r in ledger))
check('no_false_pass_completion', all(
    r['pass_component_audit']=='NO' and r['pass_behavior_trace']=='NO' and
    r['pass_discovery']=='NO' and r['pass_adversarial_verify']=='NO' for r in ledger
))
check('generated_get_boundary_treatment', all(r['review_treatment']=='BOUNDARY_TRACE_GENERATED' for r in dom if r['is_generated']=='YES'))
check('symlink_get_reference_treatment', all(r['review_treatment']=='SYMLINK_REFERENCE' for r in dom if r['is_symlink']=='YES'))
check('analysis_not_in_baseline', all(not r['path'].startswith('_analysis/') for r in manifest))
check('exactly_one_baseline_symlink', sum(r.get('is_symlink')=='True' for r in manifest)==1)

missing=[]; mismatches=[]
for r in manifest:
    fp=ROOT/r['path']
    # lexists matters for a symlink even if its target becomes unavailable in another checkout.
    if not os.path.lexists(fp):
        missing.append(r['path']); continue
    got=hash_bytes(object_bytes(fp, r.get('is_symlink')=='True'))
    if got != r['sha256']:
        mismatches.append((r['path'], r['sha256'], got))
check('all_baseline_objects_present', not missing, repr(missing[:3]))
check('all_baseline_sha256_match_snapshot', not mismatches, repr(mismatches[:3]))

snap=json.loads((SNAP/'snapshot.json').read_text())
check('snapshot_tree_match_recorded', snap.get('tree_match_verified') is True, repr(snap.get('tree_match_verified')))
check('snapshot_upstream_tree_equals_reconstructed', snap.get('upstream_git_tree_sha1')==snap.get('local_reconstructed_git_tree_sha1'),
      f"{snap.get('upstream_git_tree_sha1')} vs {snap.get('local_reconstructed_git_tree_sha1')}")
check('snapshot_file_count_consistent', snap.get('file_count')==len(manifest))
check('snapshot_symlink_count_consistent', snap.get('symlink_count')==sum(r.get('is_symlink')=='True' for r in manifest))
check('snapshot_bytes_consistent', snap.get('total_uncompressed_bytes')==sum(int(r['bytes']) for r in manifest))
check('snapshot_text_count_consistent', snap.get('utf8_text_file_count')==sum(r['utf8_text']=='True' for r in manifest))
check('snapshot_line_count_consistent', snap.get('approx_total_text_lines')==sum(int(r['lines'] or 0) for r in manifest))

report=AN/'review'/'COVERAGE_VALIDATION.md'
with report.open('w',encoding='utf-8') as f:
    f.write('# Coverage Framework Validation\n\n')
    f.write('Validation is against frozen baseline `2026-08-15_c65aa17`.\n\n')
    for n,ok,d in checks:
        f.write(f"- **{'PASS' if ok else 'FAIL'}** `{n}`" + (f" — {d}" if d else '') + '\n')
    f.write(f'\nResult: **ALL {len(checks)} CHECKS PASSED**. This validates snapshot/coverage bookkeeping only; it does not claim behavioral review has occurred.\n')
print(f'ALL {len(checks)} COVERAGE VALIDATION CHECKS PASSED')
