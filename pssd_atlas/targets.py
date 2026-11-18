"""Target dossiers and a drug-binding comparison.

Two questions a drug-discovery group asks first:
  1. For each candidate target: is it druggable, do drugs already exist, is it
     expressed in nerve tissue?                        (Open Targets Platform)
  2. Which proteins do the implicated drugs actually bind, and which are shared
     across drug classes?                              (ChEMBL binding constants)
"""

from __future__ import annotations

import json
import statistics
import urllib.request

from .http import USER_AGENT, Client

OT = "https://api.platform.opentargets.org/api/v4/graphql"
CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"
# The most relevant tissues available. No dorsal root ganglion or peripheral nerve sample is
# offered, so sensory-neuron genes look absent here even though they matter most.
TISSUES = {"Brain - Spinal cord (cervical c-1)": "spinal_cord",
           "Brain - Hypothalamus": "hypothalamus", "Brain - Nucleus accumbens (basal ganglia)": "accumbens",
           "Skin - Not Sun Exposed (Suprapubic)": "skin"}
MARKETED = {"APPROVAL", "PHASE_4"}

_QUERY = """query($id: String!) { target(ensemblId: $id) {
  approvedSymbol approvedName
  tractability { label modality value }
  drugAndClinicalCandidates { count rows { maxClinicalStage drug { name } } }
  baselineExpression(page: {index: 0, size: 3000}) { rows { datasourceId unit median tissueBiosampleFromSource } }
} }"""


def _gql(query: str, variables: dict) -> dict:
    req = urllib.request.Request(OT, data=json.dumps({"query": query, "variables": variables}).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read())
    if data.get("errors"):
        raise RuntimeError(f"Open Targets: {data['errors'][0].get('message', data['errors'])[:200]}")
    return data["data"]


def dossier(symbol: str) -> dict | None:
    hits = _gql('query($q: String!) { search(queryString: $q, entityNames: ["target"], page: {index: 0, size: 5}) '
                '{ hits { id name } } }', {"q": symbol})["search"]["hits"]
    hit = next((h for h in hits if h["name"].upper() == symbol.upper()), None)
    if not hit:
        return None
    t = _gql(_QUERY, {"id": hit["id"]})["target"]
    drugs = t["drugAndClinicalCandidates"]["rows"]
    # Salts and formulations share a first word ("PROPAFENONE HYDROCHLORIDE"): count the parent once.
    marketed = sorted({r["drug"]["name"].split()[0].capitalize() for r in drugs if r["maxClinicalStage"] in MARKETED})
    gtex = {r["tissueBiosampleFromSource"]: r["median"] for r in t["baselineExpression"]["rows"]
            if r["datasourceId"] == "gtex" and r["median"] is not None}
    top = max(gtex, key=gtex.get) if gtex else ""
    return {
        "symbol": t["approvedSymbol"], "ensembl": hit["id"], "name": t["approvedName"],
        "small_molecule": [x["label"] for x in t["tractability"] if x["value"] and x["modality"] == "SM"],
        "marketed_drugs": marketed, "clinical_candidates": t["drugAndClinicalCandidates"]["count"],
        "expression_tpm": {key: gtex.get(tissue) for tissue, key in TISSUES.items()},
        "top_tissue": top, "top_tissue_tpm": gtex.get(top),
        "url": f"https://platform.opentargets.org/target/{hit['id']}",
    }


def _molecule(client: Client, name: str) -> dict | None:
    mols = client.get_json(f"{CHEMBL}/molecule.json", {"pref_name__iexact": name, "limit": 5})["molecules"]
    return mols[0] if mols else None


def _gene(client: Client, target_id: str, cache: dict) -> str | None:
    """Gene symbol for a single-protein ChEMBL target; None for complexes, families and cell lines."""
    if target_id not in cache:
        t = client.get_json(f"{CHEMBL}/target/{target_id}.json")
        gene = None
        if t.get("target_type") == "SINGLE PROTEIN" and len(t.get("target_components", [])) == 1:
            syn = t["target_components"][0].get("target_component_synonyms", [])
            gene = next((s["component_synonym"] for s in syn if s["syn_type"] == "GENE_SYMBOL"), None)
        cache[target_id] = gene
    return cache[target_id]


def binding(client: Client, drugs: list[dict], log=lambda m: None) -> tuple[dict, dict]:
    """(median pKi per drug and human protein, basic chemistry per drug), from ChEMBL."""
    genes: dict = {}
    cells: dict[str, dict] = {}
    profiles: dict[str, dict] = {}
    for d in drugs:
        name = d["name"]
        mol = _molecule(client, name)
        if not mol:
            log(f"  ChEMBL: {name} not found")
            continue
        cid = mol["molecule_chembl_id"]
        props = mol.get("molecule_properties") or {}
        profiles[name] = {"chembl": cid, "formula": props.get("full_molformula"), "weight": props.get("full_mwt"),
                          "approved": mol.get("first_approval"),
                          "url": f"https://www.ebi.ac.uk/chembl/compound_report_card/{cid}/"}
        vals: dict[str, list[float]] = {}
        offset = 0
        while True:
            page = client.get_json(f"{CHEMBL}/activity.json", {
                "molecule_chembl_id": cid, "standard_type": "Ki", "target_organism": "Homo sapiens",
                "pchembl_value__isnull": "false", "limit": 1000, "offset": offset})
            for a in page["activities"]:
                if a.get("standard_relation") not in ("=", None):
                    continue  # ">" / "<" are bounds, not measurements
                gene = _gene(client, a["target_chembl_id"], genes)
                if gene:
                    vals.setdefault(gene, []).append(float(a["pchembl_value"]))
            offset += 1000
            if offset >= page["page_meta"]["total_count"]:
                break
        cells[name] = {g: {"pki": round(statistics.median(v), 2), "n": len(v)} for g, v in vals.items()}
        log(f"  ChEMBL: {name}: {len(cells[name])} proteins with a measured Ki")
    return cells, profiles


def analyse(client: Client, targets: list[dict], drugs: list[dict], log=lambda m: None) -> dict:
    out = []
    for t in targets:
        d = dossier(t["symbol"])
        if d is None:
            log(f"  Open Targets: {t['symbol']} not found")
            continue
        out.append({**d, "hypothesis": t.get("hypothesis", ""), "rationale": t.get("rationale", "")})
    log(f"- Open Targets: {len(out)} target dossiers")
    cells, profiles = binding(client, [d for d in drugs if not d.get("control")], log)
    return {"targets": out, "binding": cells, "profiles": profiles}
