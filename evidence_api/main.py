# main.py — Resident Evidence Deck API (copy-paste ready)

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx, re, time, os

app = FastAPI(title="Resident Evidence Deck API", version="0.1.0")

# ---- CORS: allow everything in dev so your file:// index2.html can call the API ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # dev-friendly
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- External endpoints ----
CROSSREF = "https://api.crossref.org/works/"
NCBI_SUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
NCBI_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

UNPAYWALL = "https://api.unpaywall.org/v2/"
UNPAYWALL_EMAIL = os.getenv("UNPAYWALL_EMAIL", "").strip()  # optional; leave blank to skip

# ---- Map short keys -> your section titles (keep in sync with frontend) ----
EVIDENCE_SECTIONS = {
    "Presenting Symptoms": "Presenting Symptoms",
    "Diagnostic Criteria": "Diagnostic Criteria",
    "Initial Workup": "Initial Workup",
    "Management (Initial)": "Management (Initial)",
    "Ongoing Management / Follow-up": "Ongoing Management / Follow-up",
    "Complications": "Complications",
    "Adverse Effects (Tx)": "Adverse Effects (Tx)",
    "Clinical Pearls": "Clinical Pearls",
}

# ---- Helpers ----
def _num(x):
    try:
        if x is None: return None
        x = str(x).strip().replace("%","")
        return float(x)
    except:
        return None

METRIC_PATTERNS = [
    ("sens", r"sensitiv\w*\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)\s*%"),     # Sensitivity 88%
    ("spec", r"specificit\w*\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)\s*%"),   # Specificity 76%
    ("ppv",  r"\bPPV\b\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)\s*%"),         # PPV 72%
    ("npv",  r"\bNPV\b\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)\s*%"),         # NPV 90%
    ("lrp",  r"LR\+\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)"),              # LR+ 3.2
    ("lrn",  r"LR-\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)"),               # LR- 0.4
    ("nnt",  r"\bNNT\b\s*[:=]?\s*([0-9]+)"),                        # NNT 10
]

def extract_metrics(text: str):
    text = text or ""
    out = {}
    for key, pat in METRIC_PATTERNS:
        m = re.search(pat, text, re.I)
        if m:
            out[key] = _num(m.group(1))
    return out

async def crossref_by_doi(client: httpx.AsyncClient, doi: str):
    r = await client.get(CROSSREF + doi)
    r.raise_for_status()
    j = r.json().get("message", {})
    title = (j.get("title") or [""])[0]
    authors = j.get("author") or []
    year = (j.get("issued") or {}).get("date-parts", [[None]])[0][0]
    label = f"{authors[0]['family']} et al., {year}" if authors else (str(year) if year else "Study")
    url = j.get("URL") or f"https://doi.org/{doi}"
    return {"title": title, "label": label, "url": url, "doi": doi}

async def pubmed_by_pmid(client: httpx.AsyncClient, pmid: str):
    params = {"db":"pubmed","retmode":"json","id":pmid}
    r = await client.get(NCBI_SUMMARY, params=params)
    r.raise_for_status()
    res = r.json()["result"][pmid]
    title = res.get("title","")
    year = (res.get("pubdate","") or "").split(" ")[0]
    label = f"{(res.get('sortfirstauthor') or 'Study')} et al., {year}"
    # abstract text
    fr = await client.get(NCBI_FETCH, params={"db":"pubmed","rettype":"abstract","retmode":"text","id":pmid})
    abstract = fr.text
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    # pmcid if available
    pmcid = None
    for a in res.get("articleids") or []:
        if a.get("idtype") == "pmcid":
            pmcid = a.get("value")
            break
    return {"title":title, "label":label, "url":url, "pmid":pmid, "pmcid":pmcid, "abstract":abstract}

async def unpaywall_best_url(client: httpx.AsyncClient, doi: str):
    if not doi or not UNPAYWALL_EMAIL:
        return None
    try:
        r = await client.get(f"{UNPAYWALL}{doi}", params={"email": UNPAYWALL_EMAIL})
        if r.status_code != 200:
            return None
        j = r.json()
        oa = j.get("best_oa_location") or {}
        return oa.get("url") or oa.get("url_for_pdf")
    except:
        return None

# ---- Endpoints ----
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/extract")
async def extract(
    condition: str = Query(..., description="Exact condition name as in your app"),
    section: str = Query(..., description="Exact section title as in your app"),
    doi: str | None = Query(None, description="DOI like 10.1000/xyz123"),
    pmid: str | None = Query(None, description="PubMed ID"),
):
    """
    Returns a list of EvidenceLine items your frontend already knows how to render
    (statement + metrics + source with link). For MVP we pull basic metadata and
    scrape metrics from abstract text if present.
    """
    async with httpx.AsyncClient(timeout=25.0, headers={"User-Agent":"ResidentEvidenceDeck/0.1"}) as client:
        meta, abstract_text, link = {}, "", None

        if doi:
            try:
                meta = await crossref_by_doi(client, doi)
                link = await unpaywall_best_url(client, doi) or meta.get("url")
            except Exception:
                pass

        if pmid and not meta:
            try:
                m = await pubmed_by_pmid(client, pmid)
                abstract_text = m.get("abstract","")
                meta = {k:v for k,v in m.items() if k not in ("abstract",)}
                link = meta.get("url")
            except Exception:
                pass

        if not meta:
            # Nothing resolved
            return JSONResponse({"items": []})

        metrics = extract_metrics(abstract_text or meta.get("title",""))

        # Simple, safe statement templates per section (customize later)
        if section == "Diagnostic Criteria":
            statement = f"Diagnostic performance reported in {meta.get('label','the study')}."
        elif section == "Presenting Symptoms":
            statement = f"Symptom findings reported in {meta.get('label','the study')}."
        elif section == "Initial Workup":
            statement = f"Workup yield reported in {meta.get('label','the study')}."
        elif section == "Management (Initial)":
            statement = f"Initial management outcomes summarized in {meta.get('label','the study')}."
        else:
            statement = f"Key results summarized in {meta.get('label','the study')}."

        item = {
            "condition": condition,
            "section": section,
            "statement": statement,
            "metrics": {k:v for k,v in metrics.items() if v is not None},
            "source": {
                "label": meta.get("label") or meta.get("title") or "study",
                "url": link or meta.get("url"),
                "doi": meta.get("doi"),
                "pmid": pmid,
                "pmcid": meta.get("pmcid"),
            },
            "ts": int(time.time()*1000)
        }
        return {"items":[item]}
