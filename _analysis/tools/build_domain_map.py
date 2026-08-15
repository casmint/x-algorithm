#!/usr/bin/env python3
"""Build the baseline audit-domain assignment for xai-org/x-algorithm.

Run from the repository root after placing _analysis/ there.
The script intentionally reads the frozen baseline manifest rather than walking the
current tree for baseline classification, so the 2026-08-15 evidence denominator
cannot drift. Future update tooling should diff a new manifest against this baseline.
"""
from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AN = ROOT / "_analysis"
SNAP = AN / "snapshots" / "2026-08-15_c65aa17"
MANIFEST = SNAP / "file_manifest.csv"
OUT = AN / "domains"

DOMAINS = {
    "D00": ("Repository metadata & explanatory docs", "Project-level documentation, licensing, published explanations, and audit context rather than an executable algorithm stage."),
    "D01": ("Request pipeline & orchestration", "Home Mixer request assembly, generic candidate-pipeline stages, hydration, service integration, and feed-request execution."),
    "D02": ("In-network retrieval", "Recent content retrieval from accounts the viewer follows, principally Thunder."),
    "D03": ("Out-of-network retrieval", "Phoenix retrieval, SimClusters candidate discovery, and related OON candidate generation."),
    "D04": ("Retrieval index & admission", "Maintenance and eligibility of the candidate index queried by Phoenix retrieval, including RankAll and its Strato/event layer."),
    "D05": ("Ranking & score construction", "Phoenix action prediction as used for ranking plus Home Mixer score combination, weights, boosts, penalties, and rank-affecting calculations."),
    "D06": ("Selection, reranking & diversity", "Top-K selection, slate shaping, author/semantic diversity, and VMRanker/DPP reranking."),
    "D07": ("Feed eligibility & non-VF filtering", "Request-path filters such as age, seen-state, social graph, duplicate/conversation, access, and other eligibility outside the central Visibility Filtering policy engine."),
    "D08": ("Blending, ads & non-post insertion", "Feed blending and insertion/reordering of ads, recommendations, prompts, frames, and other non-ranked-post material."),
    "D09": ("Content & media understanding", "Post/media classifiers and embeddings: Grox, media-model-proxy, CLIP, adult-content, pNSFW media, and their data/serving code."),
    "D10": ("Account behavior, credibility & reputation signals", "Account-level behavioral models and graph-derived signals: Agatha, BDSM, UserCred V2, and related feature production."),
    "D11": ("Label production, rules & aggregation", "Botmaker engine/rules, Scarecrow event labeling, and post-to-user safety-label aggregation."),
    "D12": ("Visibility policy & safety filtering", "ALLOW/INTERSTITIAL/DROP policy evaluation, safety-label hydration, policy rules, and the Visibility Filtering client surface."),
    "D13": ("Abuse enforcement & account actions", "Model-score-driven labeling, challenges, suspension/enforcement decisions, allowlists, and enforcement lifecycle."),
    "D14": ("Transparency & user-facing reporting", "Under the Hood label transparency collection, aggregation, storage, and serving."),
    "D15": ("Model training, evaluation & artifact production", "Training/evaluation pipelines and model artifact generation across ranking, retrieval, media, and account models."),
    "D16": ("Data models, storage & service integration", "Schemas, IDLs, serialization, stores/caches, generic clients, service scaffolding, and integration plumbing supporting behavioral domains."),
    "D17": ("Configuration, experiments & runtime controls", "Feature switches, checked-in defaults, thresholds, experiment IDs, configuration loading, and runtime control surfaces."),
    "D18": ("Observability, side effects & event recording", "Metrics, logging, post-response side effects, event publication, tracing, and operational observability."),
    "D19": ("Build, packaging & reproducibility", "Build manifests, packaging, dependency locks/notices, scripts, examples, benchmarks, and files needed to reproduce or understand runnable boundaries."),
}

# Documented component roles are from the root README at the frozen snapshot. They are
# hypotheses to verify during component audit, not conclusions that implementation matches docs.
COMPONENT_DEFAULTS = {
    "[root]": ["D00"],
    "docs": ["D00", "D05", "D17"],
    "candidate-pipeline": ["D01", "D16"],
    "thunder": ["D02", "D16"],
    "simclusters": ["D03", "D16"],
    "phoenix-rankall": ["D04", "D16"],
    "phoenix-rankall-strato": ["D04", "D12", "D16"],
    "vm-ranker": ["D06", "D16"],
    "grox": ["D09", "D16"],
    "media-model-proxy": ["D09", "D16"],
    "clip": ["D09", "D15"],
    "adult-content": ["D09", "D15"],
    "pnsfwmedia": ["D09"],
    "agatha": ["D10", "D15", "D16"],
    "bdsm": ["D10", "D15", "D16"],
    "user-cred-v2": ["D10", "D16"],
    "botmaker": ["D11", "D16"],
    "botmaker-rules": ["D11"],
    "scarecrow": ["D11", "D16"],
    "safety-label-user-agg": ["D11", "D16"],
    "visibility-filtering": ["D12", "D16"],
    "visibility-filtering-client": ["D12", "D16"],
    "abuse-enforcement-service": ["D13", "D16"],
    "under-the-hood": ["D14", "D16"],
    "home-mixer": ["D01"],
    "phoenix": ["D05", "D03", "D15", "D16"],
}

BUILD_NAMES = {
    "BUILD", "BUILD.bazel", "Cargo.toml", "Cargo.lock", "pyproject.toml", "NOTICE",
    "THIRD_PARTY_NOTICES.md", "requirements.txt", "setup.py", "setup.cfg",
}
CONFIG_EXTS = {".yaml", ".yml", ".toml", ".ini", ".json", ".serviceloadedtunablemap"}
IDL_EXTS = {".proto", ".thrift"}
DOC_EXTS = {".md", ".rst", ".txt"}


def add(domains: list[str], *ids: str) -> None:
    for d in ids:
        if d not in domains:
            domains.append(d)


def structural_flags(path: str, ext: str, text: str) -> dict[str, bool]:
    low = path.lower()
    name = Path(path).name.lower()
    parts = [p.lower() for p in Path(path).parts]
    is_test = (
        any(p in {"test", "tests", "integrationtest", "loadtest"} for p in parts)
        or name.startswith("test_") or name.endswith("_test.py") or name.endswith("test.rs")
        or "test" in name and ext in {".scala", ".java"}
    )
    is_fixture = any(p in {"fixture", "fixtures"} for p in parts) or "mock_" in name or name.startswith("mock")
    is_example = any(p in {"example", "examples", "example_data", "reference", "notebooks"} for p in parts)
    is_schema = ext in IDL_EXTS or any(p in {"schema", "thrift"} for p in parts)
    marker = text[:5000].lower()
    is_generated = (
        any(p in {"proto_gen", "gen"} for p in parts)
        or name.endswith("_pb2.py") or name.endswith("_pb2_grpc.py")
        or "generated code" in marker or "auto-generated" in marker or "autogenerated" in marker
        or "@generated" in marker or "do not edit" in marker and "generated" in marker
        or (path.startswith("thunder/schema/") and ext == ".rs" and "rustfmt_skip" in marker)
    )
    is_doc = ext in DOC_EXTS
    is_config = ext in CONFIG_EXTS or any(p in {"config", "configs"} for p in parts) or "config" in name or "param" in name
    is_build = Path(path).name in BUILD_NAMES or ext in {".bazel", ".lock"} or name.startswith("build.") or name == "build"
    is_asset = ext in {".jpg", ".jpeg", ".png", ".gif", ".bin", ".zip"}
    is_vendor = any(p in {"vendor", "third_party", "third-party", "external"} for p in parts)
    contains_embedded_tests = ("#[cfg(test)]" in text or "@test" in text or "unittest" in marker or "pytest" in marker) and not is_test
    return dict(is_test=is_test, is_fixture=is_fixture, is_example=is_example,
                is_generated=is_generated, is_vendor=is_vendor, contains_embedded_tests=contains_embedded_tests,
                is_schema=is_schema, is_doc=is_doc, is_config=is_config, is_build=is_build, is_asset=is_asset)


def classify(path: str, component: str, ext: str, flags: dict[str, bool]) -> tuple[list[str], str, str]:
    """Return ordered domains, confidence, basis.

    Order matters: first domain is the primary audit owner. Secondary domains ensure
    cross-domain code cannot disappear when specialists split work.
    """
    p = path.lower()
    rel = path.split("/", 1)[1] if "/" in path else path
    r = rel.lower()
    domains = list(COMPONENT_DEFAULTS.get(component, []))
    confidence = "HIGH"
    basis = f"component:{component}"

    # Home Mixer gets path-specific ownership; component default D01 remains a secondary
    # where orchestration relevance is real.
    if component == "home-mixer":
        if r.startswith("scorers/"):
            domains = ["D05", "D01"]
            if any(k in r for k in ("divers", "slate")): add(domains, "D06")
            basis = "home-mixer/scorers"
        elif r.startswith("filters/"):
            domains = ["D07", "D01"]
            if "vf_" in r or "visibility" in r or "brazil_2026_election" in r: add(domains, "D12")
            basis = "home-mixer/filters"
        elif r.startswith("selectors/"):
            domains = ["D06", "D01"]
            if "blend" in r or "who_to_follow" in r or "prompt" in r: add(domains, "D08")
            basis = "home-mixer/selectors"
        elif r.startswith("ads/") or r.startswith("frames/"):
            domains = ["D08", "D01"]
            basis = "home-mixer/blending"
        elif r.startswith("sources/"):
            domains = ["D03", "D01"]
            if "thunder" in r: domains.insert(0, "D02")
            basis = "home-mixer/sources"
        elif r.startswith("candidate_hydrators/") or r.startswith("query_hydrators/"):
            domains = ["D01", "D16"]
            if any(k in r for k in ("visibility", "vf_")): add(domains, "D12")
            if any(k in r for k in ("socialgraph", "block", "mute", "follow")): add(domains, "D07")
            if any(k in r for k in ("phoenix", "score")): add(domains, "D05")
            basis = "home-mixer/hydration"
        elif r.startswith("params/"):
            domains = ["D17", "D01", "D05"]
            basis = "home-mixer/params"
        elif r.startswith("side_effects/"):
            domains = ["D18", "D01"]
            basis = "home-mixer/side_effects"
        elif r.startswith("clients/"):
            domains = ["D16", "D01"]
            basis = "home-mixer/clients"
        elif r.startswith("candidate_pipeline/"):
            domains = ["D01"]
            if "for_you" in r or "blend" in r: add(domains, "D08")
            if "phoenix" in r: add(domains, "D03", "D05")
            basis = "home-mixer/candidate_pipeline"
        elif (r.startswith("models/") or r.startswith("util/") or r.startswith("bin/")
              or r in {"lib.rs", "main.rs", "server.rs", "config.rs", "dark_traffic_setup.rs"}
              or r.endswith("_server.rs")):
            domains = ["D01", "D16"]
            if r == "config.rs": add(domains, "D17")
            if "dark_traffic" in r: add(domains, "D18")
            basis = "home-mixer/core-server"
        else:
            confidence = "LOW"
            basis = "home-mixer/unexpected-current-path"

    # Phoenix is both retrieval and ranking. Use explicit path/name semantics where available;
    # generic model/serving infrastructure remains deliberately cross-domain.
    elif component == "phoenix":
        retrieval_keys = ("retrieval", "two_tower", "sid_", "sid-", "sid.", "rankall", "index")
        ranking_keys = ("ranker", "ranking", "recsys_model", "recsys_attention", "loss_recsys", "gen_recs")
        train_keys = ("/train/", "/training/", "/eval/", "train_", "trainer", "optim", "dataset", "checkpoint", "quickstart", "training.md")
        if any(k in "/" + r for k in train_keys):
            domains = ["D15", "D16"]
            if any(k in r for k in retrieval_keys): add(domains, "D03")
            if any(k in r for k in ranking_keys): add(domains, "D05")
            basis = "phoenix/training-eval"
        elif any(k in r for k in retrieval_keys) and not any(k in r for k in ranking_keys):
            domains = ["D03", "D16"]
            basis = "phoenix/retrieval-explicit"
        elif any(k in r for k in ranking_keys) and not any(k in r for k in retrieval_keys):
            domains = ["D05", "D16"]
            basis = "phoenix/ranking-explicit"
        elif r.startswith("reference/"):
            domains = ["D19", "D15", "D03", "D05"]
            basis = "phoenix/reference"
        elif r.startswith("xrex/models/") or r.startswith("xrex/inference/") or r.startswith("crates/serving/"):
            domains = ["D05", "D03", "D16"]
            basis = "phoenix/shared-model-serving"
        elif r.startswith("xrex/data/"):
            domains = ["D15", "D16", "D03", "D05"]
            basis = "phoenix/data"
        elif r.startswith("xrex/cuda/") or r.startswith("xrex/cutedsl/") or r.startswith("xrex/pallas/") or r.startswith("xrex/utils/"):
            domains = ["D16", "D15", "D05"]
            basis = "phoenix/compute-infra"
        elif r.startswith("xrex/configs/") or "config" in r or "settings" in r:
            domains = ["D17", "D15", "D03", "D05"]
            basis = "phoenix/config"
        elif r.startswith("python/common/") or r.startswith("crates/common/"):
            domains = ["D16", "D03", "D05", "D15"]
            basis = "phoenix/common-infra"
        elif r in {"readme.md", "quickstart.md", "training.md", "notice", "third_party_notices.md"}:
            domains = ["D19", "D15", "D03", "D05"]
            basis = "phoenix/docs"
        else:
            domains = ["D16", "D15", "D03", "D05"]
            basis = "phoenix/fallback-cross-domain"

    # Specific cross-domain path refinements elsewhere.
    elif component == "phoenix-rankall-strato":
        domains = ["D04", "D12", "D16"]
        basis = "rankall-strato/admission-vf-bridge"
    elif component == "visibility-filtering":
        domains = ["D12"]
        if any(k in r for k in ("client", "hydration", "models", "safety_label_source", "twemcache")): add(domains, "D16")
        if r.startswith("rules/"): add(domains, "D17")
        basis = "visibility-filtering"
    elif component == "abuse-enforcement-service":
        domains = ["D13"]
        if r.startswith("service-lib/rules/"): add(domains, "D17")
        if any(k in r for k in ("growthbook", "config", "allowlist")): add(domains, "D17")
        add(domains, "D16")
        basis = "abuse-enforcement"
    elif component in {"agatha", "bdsm"}:
        domains = ["D10"]
        if any(k in r for k in ("training", "train", "quantile", "model")): add(domains, "D15")
        add(domains, "D16")
        basis = f"{component}/account-signals"
    elif component in {"clip", "adult-content"}:
        domains = ["D09"]
        if any(k in r for k in ("train", "training", "calibr", "notebook", "dataset")): add(domains, "D15")
        basis = f"{component}/media-model"
    elif component == "media-model-proxy":
        domains = ["D09", "D16"]
        if "config" in r: add(domains, "D17")
        if "test" in r or "loadtest" in r: add(domains, "D19")
        basis = "media-model-proxy"
    elif component == "grox":
        domains = ["D09", "D16"]
        if r.startswith("config/"): add(domains, "D17")
        if r.startswith("flows/") or r.startswith("core/plans/") or r.startswith("core/tasks/"): add(domains, "D11")
        basis = "grox/content-understanding"
    elif component in {"botmaker", "botmaker-rules", "scarecrow", "safety-label-user-agg"}:
        domains = ["D11"]
        if component != "botmaker-rules": add(domains, "D16")
        if component == "botmaker-rules" or "config" in r: add(domains, "D17")
        basis = f"{component}/label-system"
    elif component == "under-the-hood":
        domains = ["D14", "D16"]
        basis = "under-the-hood"
    elif component == "user-cred-v2":
        domains = ["D10", "D16"]
        basis = "user-cred-v2"
    elif component == "simclusters":
        domains = ["D03", "D16"]
        basis = "simclusters"
    elif component == "thunder":
        domains = ["D02"]
        if any(k in r for k in ("schema", "kafka", "config", "strato", "service", "deserial")): add(domains, "D16")
        basis = "thunder"
    elif component == "phoenix-rankall":
        domains = ["D04", "D16"]
        if "config" in r: add(domains, "D17")
        basis = "phoenix-rankall"
    elif component == "vm-ranker":
        domains = ["D06", "D16"]
        basis = "vm-ranker"
    elif component == "visibility-filtering-client":
        domains = ["D12", "D16"]
        basis = "visibility-filtering-client"
    elif component == "candidate-pipeline":
        domains = ["D01", "D16"]
        if "side_effect" in r: add(domains, "D18")
        basis = "candidate-pipeline"
    elif component == "safety-label-user-agg":
        domains = ["D11", "D16"]
        basis = "safety-label-user-agg"

    # Structural/cross-cutting additions. These never erase behavioral ownership.
    if flags["is_config"]:
        add(domains, "D17")
    if flags["is_schema"]:
        add(domains, "D16")
    if flags["is_build"] or flags["is_example"]:
        add(domains, "D19")
    if any(k in p for k in ("metrics", "logging", "logger", "trace", "telemetry", "side_effect")):
        add(domains, "D18")
    if any(k in p for k in ("training", "/train", "trainer", "/eval", "calibrat", "notebooks/")) and component not in {"home-mixer", "candidate-pipeline"}:
        add(domains, "D15")

    if not domains:
        raise RuntimeError(f"Unclassified file: {path}")
    for d in domains:
        if d not in DOMAINS:
            raise RuntimeError(f"Unknown domain {d} for {path}")
    return domains, confidence, basis


def treatment(flags: dict[str, bool]) -> str:
    if flags.get("is_symlink"):
        return "SYMLINK_REFERENCE"
    if flags["is_generated"]:
        return "BOUNDARY_TRACE_GENERATED"
    if flags["is_fixture"]:
        return "FIXTURE_EVIDENCE"
    if flags["is_test"]:
        return "TEST_EVIDENCE"
    if flags["is_doc"]:
        return "DOC_CONTEXT_VERIFY_AGAINST_CODE"
    if flags["is_build"]:
        return "REPRO_BUILD_REVIEW"
    if flags["is_example"]:
        return "EXAMPLE_REFERENCE_REVIEW"
    if flags["is_asset"]:
        return "ASSET_PROVENANCE_REVIEW"
    return "FULL_SOURCE_REVIEW"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    with MANIFEST.open(newline="", encoding="utf-8") as f:
        manifest = list(csv.DictReader(f))
    for m in manifest:
        path = m["path"]
        fp = ROOT / path
        text = ""
        if fp.exists() and m["utf8_text"] == "True":
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        ext = m["extension"] if m["extension"] != "[no extension]" else ""
        flags = structural_flags(path, ext, text)
        flags["is_symlink"] = m.get("is_symlink", "False") == "True"
        domains, confidence, basis = classify(path, m["top_component"], ext, flags)
        rows.append({
            "path": path,
            "top_component": m["top_component"],
            "primary_domain": domains[0],
            "secondary_domains": ";".join(domains[1:]),
            "all_domains": ";".join(domains),
            "cross_domain": "YES" if len(domains) > 1 else "NO",
            "classification_confidence": confidence,
            "classification_basis": basis,
            "review_treatment": treatment(flags),
            **{k: "YES" if v else "NO" for k, v in flags.items()},
            "lines": m["lines"],
            "bytes": m["bytes"],
        })

    if len(rows) != 2016:
        raise RuntimeError(f"Expected 2016 baseline files; got {len(rows)}")
    if len({r['path'] for r in rows}) != len(rows):
        raise RuntimeError("Duplicate paths in mapping")

    cols = list(rows[0].keys())
    with (OUT / "file_domain_map.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader(); w.writerows(rows)

    # Domain summary: count a file once in every assigned domain, making cross-domain workload explicit.
    dcounts = Counter(); dlines = Counter(); primary = Counter();
    for r in rows:
        primary[r["primary_domain"]] += 1
        for d in r["all_domains"].split(";"):
            dcounts[d] += 1
            dlines[d] += int(r["lines"] or 0)
    with (OUT / "domain_summary.csv").open("w", newline="", encoding="utf-8") as f:
        fields = ["domain_id", "domain_name", "primary_files", "assigned_files_including_cross_domain", "assigned_lines_including_cross_domain"]
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for d in DOMAINS:
            w.writerow({"domain_id": d, "domain_name": DOMAINS[d][0], "primary_files": primary[d],
                        "assigned_files_including_cross_domain": dcounts[d], "assigned_lines_including_cross_domain": dlines[d]})

    # Structural summary.
    roles = ["is_symlink", "is_test", "contains_embedded_tests", "is_fixture", "is_example", "is_generated", "is_vendor", "is_schema", "is_doc", "is_config", "is_build", "is_asset"]
    with (OUT / "structural_summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["flag", "files"])
        for flag in roles:
            w.writerow([flag, sum(r[flag] == "YES" for r in rows)])

    # Manual-attention list is not an error: medium confidence means deliberately broad cross-domain ownership.
    manual = [r for r in rows if r["classification_confidence"] != "HIGH"]
    with (OUT / "manual_attention.csv").open("w", newline="", encoding="utf-8") as f:
        fields = ["path", "top_component", "primary_domain", "secondary_domains", "classification_confidence", "classification_basis", "review_treatment"]
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in manual: w.writerow({k:r[k] for k in fields})

    # Update the central coverage ledger without claiming review occurred.
    ledger_path = AN / "coverage_ledger.csv"
    with ledger_path.open(newline="", encoding="utf-8") as f:
        old = list(csv.DictReader(f))
    by_path = {r["path"]: r for r in rows}
    fields = list(old[0].keys())
    # Replace old single domain slot with useful classification columns while preserving review state.
    for extra in ["primary_domain", "secondary_domains", "classification_confidence", "review_treatment"]:
        if extra not in fields: fields.append(extra)
    for r in old:
        m = by_path[r["path"]]
        r["domain"] = m["all_domains"]
        r["primary_domain"] = m["primary_domain"]
        r["secondary_domains"] = m["secondary_domains"]
        r["classification_confidence"] = m["classification_confidence"]
        r["review_treatment"] = m["review_treatment"]
    with ledger_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(old)

    print(f"Mapped {len(rows)} baseline files across {len(DOMAINS)} audit domains")
    print(f"Medium-confidence deliberate cross-domain assignments: {len(manual)}")
    print("Unclassified: 0; duplicate paths: 0")

if __name__ == "__main__":
    main()
