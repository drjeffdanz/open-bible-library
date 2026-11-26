#!/usr/bin/env python3
"""Fetch the parts of the Open Bible Library that are too large for git
or that live outside GitHub, keeping only what the license allows.

Usage:
    python tools/fetch.py list
    python tools/fetch.py <source-id> [--out DIR] [--limit N] [--shard I/N]

Every downloaded file is recorded in <out>/<source-id>/MANIFEST.json with
its source URL, license and SHA-256. Anything whose license cannot be
confirmed is skipped and listed under "skipped" with the reason.

Output is routed by tier:
    <out>/<source-id>/...                 open (any use, attribution as required)
    <out>/ebible-nd/...                   CC BY-ND: keep verbatim
Non-commercial (NC) material is never fetched: the library also feeds paid products.
"""

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog" / "sources.yaml"
EBIBLE_CSV = ROOT / "catalog" / "ebible-licenses.csv"
USER_AGENT = "open-bible-library-fetch/1.0 (+https://github.com/drjeffdanz/open-bible-library)"

EBIBLE_OPEN = {"public-domain", "CC-BY-4.0", "CC-BY-SA-4.0", "CC-BY-SA-3.0"}
EBIBLE_ND = {"CC-BY-ND-4.0"}

SEFARIA_OPEN = "open"


def sefaria_class(value):
    """Classify a Sefaria version's license field. Anything unrecognised is 'unknown' and skipped."""
    v = str(value or "unknown").strip().lower().replace("_", "-").replace(" ", "-")
    if v in ("pd", "public-domain", "cc0", "cc-0", "cc0-1.0"):
        return "open"
    if v.startswith("cc-by"):
        if "-nd" in v:
            return "unknown"  # no-derivatives versions are left out; none are expected
        if "-nc" in v:
            return "noncommercial"
        return "open"
    return "unknown"

GUTENBERG_LOCC = ("BM", "BR", "BS", "BT", "BV", "BX")


def load_catalog():
    with open(CATALOG, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {s["id"]: s for s in data["sources"]}


def http_get(url, retries=4, delay=1.0):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            time.sleep(delay)
            return data
        except Exception as e:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            print(f"  retry {attempt + 1} for {url}: {e}", file=sys.stderr)
            time.sleep(2 ** attempt * 2)
    return None


SHARD = (0, 1)  # (index, count); set from --shard
DEADLINE = None  # time.monotonic() value after which long fetchers stop; set from --max-minutes


def out_of_time():
    return DEADLINE is not None and time.monotonic() > DEADLINE


def in_shard(i):
    return i % SHARD[1] == SHARD[0]


class Manifest:
    def __init__(self, out_dir, source_id, license_note):
        suffix = f"-shard{SHARD[0]}of{SHARD[1]}" if SHARD[1] > 1 else ""
        self.path = out_dir / f"MANIFEST{suffix}.json"
        self.data = {"source": source_id, "license": license_note,
                     "fetched": time.strftime("%Y-%m-%d"), "files": [], "skipped": []}

    def add(self, file_path, url, license_):
        h = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
        self.data["files"].append({"path": str(file_path), "url": url,
                                   "license": license_, "sha256": h})

    def skip(self, item, reason):
        self.data["skipped"].append({"item": item, "reason": reason})

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  {len(self.data['files'])} files kept, {len(self.data['skipped'])} skipped -> {self.path}")


# ---------------------------------------------------------------- mirrors

def fetch_mirror(src, out):
    dest = out / src["id"]
    if dest.exists():
        print(f"  {dest} exists, skipping clone")
        return
    subprocess.run(["git", "clone", "--depth", "1", src["upstream"], str(dest)], check=True)
    commit = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(["rm", "-rf", str(dest / ".git")], check=True)
    (dest / "SOURCE.json").write_text(json.dumps({
        "id": src["id"], "upstream": src["upstream"], "commit": commit,
        "license": src["license"], "evidence": src["evidence"],
        "tier": src["tier"], "fetched": time.strftime("%Y-%m-%d")}, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- eBible

def ebible_live_license(tid):
    """Re-read the translation's copyright page so the license is checked at download time."""
    page = http_get(f"https://ebible.org/{tid}/copyright.htm").decode("utf-8", "replace")
    m = re.search(r"creativecommons\.org/(licenses|publicdomain)/([a-z\-]+)/?([\d.]*)", page)
    if m:
        if m.group(1) == "publicdomain":
            return "public-domain"
        ver = m.group(3).rstrip(".")
        if ver == "4":
            ver = "4.0"
        # No version on the page: report it plainly so it never matches the catalog and is skipped.
        return f"CC-{m.group(2).upper()}-{ver}" if ver else f"CC-{m.group(2).upper()}-unversioned"
    if re.search(r"public domain", page, re.I):
        return "public-domain"
    return "unknown"


def fetch_ebible(src, out, wanted, limit):
    m = Manifest(out / src["id"], src["id"], "per translation")
    with open(EBIBLE_CSV, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["license"] in wanted]
    rows = [r for i, r in enumerate(rows) if in_shard(i)]
    for i, row in enumerate(rows):
        if limit and i >= limit:
            break
        tid = row["translation_id"]
        try:
            live = ebible_live_license(tid)
        except Exception as e:  # noqa: BLE001
            m.skip(tid, f"could not read copyright page: {e}")
            continue
        if live != row["license"]:
            m.skip(tid, f"license changed: catalog says {row['license']}, page now says {live}")
            continue
        url = f"https://ebible.org/Scriptures/{tid}_usfm.zip"
        try:
            blob = http_get(url)
        except Exception as e:  # noqa: BLE001
            m.skip(tid, f"download failed: {e}")
            continue
        dest = out / src["id"] / tid
        dest.mkdir(parents=True, exist_ok=True)
        zip_path = dest / f"{tid}_usfm.zip"
        zip_path.write_bytes(blob)
        (dest / "LICENSE.txt").write_text(
            f"{row['title']} ({row['language']})\nLicense: {row['license']}\n"
            f"Source: https://ebible.org/{tid}/copyright.htm\n", encoding="utf-8")
        m.add(zip_path, url, row["license"])
        print(f"  [{i + 1}/{len(rows)}] {tid} {row['license']}")
    m.save()


# ---------------------------------------------------------------- simple files

def fetch_files(src, out, files):
    m = Manifest(out / src["id"], src["id"], src["license"])
    for url in files:
        name = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
        dest = out / src["id"] / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(http_get(url))
        m.add(dest, url, src["license"])
        print(f"  {name}")
    m.save()


BSB_FILES = [
    "https://bereanbible.com/bsb.txt",
    "https://bereanbible.com/bsb_usfm.zip",
    "https://bereanbible.com/bsb_usx.zip",
    "https://bereanbible.com/bsb.xlsx",
    "https://bereanbible.com/bsb_tables.xlsx",
    "https://bereanbible.com/bsb_concordance.xlsx",
    "https://bereanbible.com/bsb_topical_index.xlsx",
    "https://literalbible.com/blb.txt",
    "https://readersbible.com/brb.txt",
]


# ---------------------------------------------------------------- Sefaria

def fetch_sefaria(src, out, wanted, limit):
    m = Manifest(out / src["id"], src["id"], "per text version")
    books = json.loads(http_get(
        "https://raw.githubusercontent.com/Sefaria/Sefaria-Export/master/books.json"))["books"]
    books = [b for b in books if b.get("versionTitle") != "merged"]
    books = [b for i, b in enumerate(books) if in_shard(i)]
    for i, b in enumerate(books):
        if limit and i >= limit:
            break
        url = b["json_url"]
        try:
            raw = http_get(url, delay=0.2)
            doc = json.loads(raw)
        except Exception as e:  # noqa: BLE001
            m.skip(url, f"download failed: {e}")
            continue
        lic = sefaria_class(doc.get("license"))
        if lic != wanted:
            m.skip(url, f"license '{doc.get('license')}' ({lic}) not allowed in {src['id']}")
            continue
        rel = urllib.parse.unquote(url.split("/sefaria-export/json/", 1)[1])
        dest = out / src["id"] / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        m.add(dest, url, doc.get("license"))
        if i % 200 == 0:
            print(f"  [{i}/{len(books)}] {rel}")
    m.save()


# ---------------------------------------------------------------- Project Gutenberg

PG_START = re.compile(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG.*?\*\*\*", re.I)
PG_END = re.compile(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG", re.I)


# Project Gutenberg asks bulk downloaders to use a mirror rather than www.gutenberg.org.
# gutenberg.pglaf.org is run by PGLAF (Project Gutenberg's parent) and has the same
# /cache/epub layout. www.gutenberg.org is only a fallback.
PG_BASES = ("https://gutenberg.pglaf.org", "https://www.gutenberg.org")


def pg_get(path, delay=1.0):
    """Fetch a Project Gutenberg path, trying each base in PG_BASES. Returns (bytes, url)."""
    err = None
    for base in PG_BASES:
        url = base + path
        try:
            return http_get(url, retries=3, delay=delay), url
        except Exception as e:  # noqa: BLE001
            err = e
            print(f"  {url} failed: {e}", file=sys.stderr)
    raise err


def fetch_gutenberg(src, out, limit):
    m = Manifest(out / src["id"], src["id"], "Public domain in the USA (per book)")
    cat = pg_get("/cache/epub/feeds/pg_catalog.csv")[0].decode("utf-8")
    rows = [r for r in csv.DictReader(io.StringIO(cat))
            if r.get("Type") == "Text" and any(
                c.strip().startswith(GUTENBERG_LOCC) for c in (r.get("LoCC") or "").split(";"))]
    rows = [r for i, r in enumerate(rows) if in_shard(i)]
    for i, r in enumerate(rows):
        if limit and i >= limit:
            break
        if out_of_time():
            for rest in rows[i:]:
                m.skip(rest["Text#"], "time budget reached; not fetched in this run")
            print(f"  time budget reached after {i} of {len(rows)} books")
            break
        n = r["Text#"]
        try:
            rdf = pg_get(f"/cache/epub/{n}/pg{n}.rdf", delay=2)[0].decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            m.skip(n, f"rdf failed: {e}")
            continue
        rights = re.search(r"<dcterms:rights>(.*?)</dcterms:rights>", rdf, re.S)
        rights = rights.group(1).strip() if rights else ""
        if rights != "Public domain in the USA.":
            m.skip(n, f"rights: {rights or 'missing'}")
            continue
        try:
            raw, url = pg_get(f"/cache/epub/{n}/pg{n}.txt", delay=2)
            text = raw.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            m.skip(n, f"text failed: {e}")
            continue
        s, e_ = PG_START.search(text), PG_END.search(text)
        if not (s and e_):
            m.skip(n, "could not find Project Gutenberg header/footer to strip")
            continue
        body = text[s.end():e_.start()].strip() + "\n"
        title = re.sub(r"[^\w\- ]", "", r["Title"])[:80].strip().replace(" ", "_")
        dest = out / src["id"] / f"{n}_{title}.txt"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            f"Title: {r['Title']}\nAuthor: {r['Authors']}\nLanguage: {r['Language']}\n"
            f"Rights: Public domain in the USA. Source text digitized by Project Gutenberg volunteers.\n\n" + body,
            encoding="utf-8")
        m.add(dest, url, "Public domain in the USA")
        print(f"  [{i + 1}/{len(rows)}] {n} {r['Title'][:60]}")
    m.save()


# ---------------------------------------------------------------- Internet Archive

ARCHIVE_QUERY = (
    'mediatype:texts AND possible-copyright-status:NOT_IN_COPYRIGHT AND year:[1450 TO 1930] '
    'AND subject:(bible OR commentaries OR theology OR sermons OR "church history" '
    'OR "fathers of the church" OR creeds OR "greek language, biblical" OR "hebrew language" '
    'OR concordances OR "christian literature" OR patristic) '
    'AND NOT collection:(inlibrary OR printdisabled OR lendinglibrary) AND NOT sponsor:(Google)'
)
RESTRICTIVE = re.compile(r"all rights reserved|non-?commercial|by-nc|permission|restricted", re.I)
LAST_PD_YEAR = 1930  # US: works published before 1931 are public domain as of 2026


def archive_ids():
    ids, cursor = [], None
    while True:
        params = {"q": ARCHIVE_QUERY, "fields": "identifier", "count": "10000"}
        if cursor:
            params["cursor"] = cursor
        page = json.loads(http_get("https://archive.org/services/search/v1/scrape?" + urllib.parse.urlencode(params)))
        ids += [d["identifier"] for d in page.get("items", [])]
        cursor = page.get("cursor")
        if not cursor:
            return sorted(ids)


def archive_check(md):
    """Return None if the item is clearly public domain in the US and unrestricted, else the reason."""
    if md.get("possible-copyright-status") != "NOT_IN_COPYRIGHT":
        return f"copyright status {md.get('possible-copyright-status')!r}"
    year = re.match(r"\d{4}", str(md.get("year") or md.get("date") or ""))
    if not year or int(year.group()) > LAST_PD_YEAR:
        return f"publication year {md.get('year') or md.get('date')!r} not before 1931"
    if "google" in str(md.get("sponsor", "")).lower():
        return "Google-digitized (carries usage restrictions)"
    if str(md.get("access-restricted-item", "")).lower() == "true":
        return "access-restricted item"
    for key in ("rights", "licenseurl", "possible-copyright-status-note"):
        if md.get(key) and RESTRICTIVE.search(str(md.get(key))):
            return f"{key}: {md.get(key)}"
    return None


def fetch_archive(src, out, limit):
    m = Manifest(out / src["id"], src["id"], "Public domain in the USA (per item)")
    ids = [x for i, x in enumerate(archive_ids()) if in_shard(i)]
    for i, ident in enumerate(ids):
        if limit and i >= limit:
            break
        if out_of_time():
            for rest in ids[i:]:
                m.skip(rest, "time budget reached; not fetched in this run")
            print(f"  time budget reached after {i} of {len(ids)} items")
            break
        try:
            meta = json.loads(http_get(f"https://archive.org/metadata/{ident}", delay=0.5))
        except Exception as e:  # noqa: BLE001
            m.skip(ident, f"metadata failed: {e}")
            continue
        md = meta.get("metadata", {})
        reason = archive_check(md)
        if reason:
            m.skip(ident, reason)
            continue
        txt = [f["name"] for f in meta.get("files", []) if f["name"].endswith("_djvu.txt")]
        if not txt:
            m.skip(ident, "no OCR text file")
            continue
        url = f"https://archive.org/download/{ident}/{urllib.parse.quote(txt[0])}"
        try:
            body = http_get(url, delay=0.5).decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            m.skip(ident, f"text failed: {e}")
            continue
        dest = out / src["id"] / f"{ident}.txt"
        dest.parent.mkdir(parents=True, exist_ok=True)
        first = lambda v: (v[0] if isinstance(v, list) else v) or ""  # noqa: E731
        dest.write_text(
            f"Title: {first(md.get('title'))}\nAuthor: {first(md.get('creator'))}\n"
            f"Published: {first(md.get('publisher'))} {first(md.get('year') or md.get('date'))}\n"
            f"Scan: https://archive.org/details/{ident}\n"
            f"Rights: Public domain in the USA (published before 1931). OCR text; may contain recognition errors.\n\n"
            + body, encoding="utf-8")
        m.add(dest, url, "Public domain in the USA")
        if i % 100 == 0:
            print(f"  [{i}/{len(ids)}] {ident}")
    m.save()


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--limit", type=int, default=0, help="stop after N items (for testing)")
    ap.add_argument("--shard", default="0/1", help="process only shard I of N, e.g. 2/4 (eBible, Sefaria, Gutenberg, archive.org)")
    ap.add_argument("--max-minutes", type=float, default=0,
                    help="stop the Gutenberg and archive.org fetchers after this many minutes and keep what was "
                         "fetched (the rest is listed as skipped in the manifest); 0 = no limit")
    a = ap.parse_args()
    global SHARD, DEADLINE
    i, n = (int(x) for x in a.shard.split("/"))
    SHARD = (i, n)
    if a.max_minutes:
        DEADLINE = time.monotonic() + a.max_minutes * 60
    cat = load_catalog()
    out = Path(a.out)

    if a.source == "list":
        for s in cat.values():
            if s["method"] in ("mirror", "fetch"):
                print(f"{s['id']:28} {s['tier']:14} {s['method']}")
        return

    src = cat.get(a.source)
    if not src:
        sys.exit(f"unknown source id: {a.source}")
    if src["tier"] == "excluded":
        sys.exit(f"{a.source} is excluded and must not be fetched")
    print(f"Fetching {src['id']} ({src['tier']}) -> {out}")

    if src["method"] == "mirror":
        fetch_mirror(src, out)
    elif src["id"] == "ebible-open":
        fetch_ebible(src, out, EBIBLE_OPEN, a.limit)
    elif src["id"] == "ebible-nd":
        fetch_ebible(src, out, EBIBLE_ND, a.limit)
    elif src["id"] == "bsb":
        fetch_files(src, out, BSB_FILES)
    elif src["id"] == "openbible-cross-references":
        fetch_files(src, out, [src["upstream"]])
    elif src["id"] == "sefaria-open":
        fetch_sefaria(src, out, SEFARIA_OPEN, a.limit)
    elif src["id"] == "gutenberg-christian":
        fetch_gutenberg(src, out, a.limit)
    elif src["id"] == "archive-org-pd":
        fetch_archive(src, out, a.limit)
    else:
        sys.exit(f"{a.source} is {src['method']}; nothing to fetch")


if __name__ == "__main__":
    main()
