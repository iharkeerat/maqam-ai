"""Upgrade 21: source-specific external evidence coverage audit.

The output is an evidence map and fail-closed claim eligibility evaluation;
it is NOT a dataset of observed sung pronunciation alternatives and it does
NOT produce real-world alignment scores. Published descriptions alone never
pass the acquired-and-adjudicated study gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SOURCE_STATES = {"PUBLIC_DESCRIPTION_ONLY", "LOCAL_40_RECORD_EXCERPT_UNRECONCILED", "LOCAL_FULL_SOURCE_NOT_ADJUDICATED", "INDEPENDENTLY_ADJUDICATED_SOURCE"}


class CoverageError(ValueError):
    pass


def load_registry(path: Path) -> dict[str, Any]:
    r = json.loads(path.read_text(encoding="utf-8"))
    if r.get("schema_version") != "1.0":
        raise CoverageError("Unknown source registry schema")
    sources, specs = r.get("sources"), r.get("claim_specs")
    if not isinstance(sources, list) or not sources or not isinstance(specs, list) or not specs:
        raise CoverageError("Missing source records or claim specifications")
    source_ids = set()
    for s in sources:
        if not isinstance(s, dict) or s.get("evidence_level") not in SOURCE_STATES:
            raise CoverageError("Unrecognized source evidence type")
        sid = s.get("id")
        if not isinstance(sid, str) or not sid or sid in source_ids:
            raise CoverageError("Missing or duplicated source id")
        source_ids.add(sid)
        if not isinstance(s.get("url"), str) or not s["url"].startswith("https://"):
            raise CoverageError("Missing HTTPS source reference")
        present, absent = s.get("declared_fields"), s.get("not_documented")
        if not isinstance(present, list) or not isinstance(absent, list) or set(present) & set(absent):
            raise CoverageError("Contradictory declared/missing fields")
        if len(set(present)) != len(present) or len(set(absent)) != len(absent):
            raise CoverageError("Duplicate field records")
        if s["evidence_level"] == "INDEPENDENTLY_ADJUDICATED_SOURCE":
            # No self-promotion to gold via a public metadata JSON file.
            raise CoverageError("Independent adjudication cannot be asserted in metadata registry")
    ids=set()
    for q in specs:
        qid=q.get("id")
        if not isinstance(qid,str) or not qid or qid in ids:
            raise CoverageError("Duplicate or missing claim id")
        ids.add(qid)
        if not isinstance(q.get("requirements"),list) or not q["requirements"] or len(set(q["requirements"])) != len(q["requirements"]):
            raise CoverageError("Missing or duplicate requirements")
    return r


def audit_registry(registry:dict[str,Any], *, excerpt_path:Path|None=None) -> dict[str,Any]:
    """Discover candidate sources; never confuse field coverage with validated observations."""
    entries=[]
    for claim in registry["claim_specs"]:
        requirements=set(claim["requirements"])
        matches=[]
        union=set()
        for s in registry["sources"]:
            declared=set(s["declared_fields"])
            union.update(declared)
            matches.append({"source_id":s["id"],"description_contains_all_fields":requirements<=declared,
                            "covered_fields":sorted(requirements & declared),
                            "missing_fields":sorted(requirements-declared),
                            "artifact_observed":"LOCAL_EXCERPT_ONLY" if s["evidence_level"]=="LOCAL_40_RECORD_EXCERPT_UNRECONCILED" else "NOT_INGESTED",
                            "eligible_confirmatory_records":0})
        candidates=[x["source_id"] for x in matches if x["description_contains_all_fields"]]
        entries.append({"claim":claim["id"],"question_scope":claim["scope"],
                        "single_source_descriptions_matching":candidates,
                        "cross_source_field_union_covers_spec":requirements<=union,
                        "cross_source_union_not_valid_gold":True,
                        "eligible_confirmatory_cases":0,
                        "confirmatory_status":"BLOCKED_NO_SAME_ITEM_INDEPENDENT_ADJUDICATED_GOLD",
                        "by_source":matches})
    excerpt={"status":"NOT_CHECKED", "rows":0, "multiple_transcriptions_per_spelling":None,
             "sha256":None, "externally_verified_sung_variants":0}
    if excerpt_path is not None:
        from .lexical_evidence import parse_source_excerpt
        from .ambiguity_u17 import inventory
        if excerpt_path.is_symlink() or not excerpt_path.is_file():
            raise CoverageError("A regular source excerpt file is required")
        data=excerpt_path.read_bytes()
        rows=parse_source_excerpt(data.decode("utf-8-sig"))
        inv=inventory(rows)
        excerpt={"status":"EXCERPT_ONLY_NOT_UPSTREAM_RECONCILED",
                 "rows":inv["lexical_records"],
                 "multiple_transcriptions_per_spelling":inv["source_documented_multiple_transcriptions"],
                 "sha256":hashlib.sha256(data).hexdigest(),
                 "externally_verified_sung_variants":0}
    return {"schema_version":"1.0", "upgrade":"21", "as_of_date":registry["as_of_date"],
            "sources_listed":len(registry["sources"]),"source_descriptions_not_original_gold":True,
            "linguistic_sample":excerpt,"claim_coverage":entries,
            "overall_real_world_advantage":"NOT_MEASURED",
            "scientific_go_no_go":"NO_GO_FOR_REAL_WORLD_PRONUNCIATION_RHYTHM_SUPERIORITY",
            "frontend_production_build":"NOT_VERIFIED",
            "notes":["Public descriptions have been inspected but no new underlying dataset bytes were acquired.",
                     "No merging of different recordings, dictionaries, and lyric pairs into fake same-item gold.",
                     "The only local external lexical excerpt is not verified for sung syllable boundaries.",
                     "Documented music syllable-alignment corpora exist; task-specific rights and annotation checks remain before use."]}


def save_report(report:dict[str,Any], output_dir:Path)->None:
    output_dir.mkdir(parents=True,exist_ok=True)
    (output_dir/"SOURCE_COVERAGE_REPORT.json").write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    lines=["# MAQAM AI Upgrade 21 — Prospective Evidence Coverage Audit","",
           "This is a **source discovery and sufficiency audit**, not validation of musical accuracy.",
           f"Sources described: **{report['sources_listed']}**. Confirmatory external items: **0**.", ""]
    for claim in report["claim_coverage"]:
        names=", ".join(claim["single_source_descriptions_matching"]) or "none"
        lines.extend([f"## {claim['claim']}",f"Source descriptions containing all declared fields: {names}.",
                      "Eligible confirmed items: **0** — source bytes and annotation independence are not verified.",""])
    lines.extend(["## Study decision","**NO-GO for real-world pronunciation–rhythm superiority claims.**",
                  "Source datasets must be evaluated individually at matching observation units; independent corpora cannot be artificially combined.",
                  "The next empirical step is to obtain a reproducible licensed sample from a lyric–Taal annotated source and verify its annotation schema, then separately seek genuinely attested alternative pronunciations.",""])
    (output_dir/"SOURCE_COVERAGE_REPORT.md").write_text("\n".join(lines),encoding="utf8")


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry",type=Path,required=True)
    p.add_argument("--excerpt",type=Path)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    reg=load_registry(args.registry)
    result=audit_registry(reg,excerpt_path=args.excerpt)
    save_report(result,args.out)
    print(json.dumps({"status":result["scientific_go_no_go"],"sources":result["sources_listed"],
                      "claims":len(result["claim_coverage"])},sort_keys=True))


if __name__=="__main__":
    main()
