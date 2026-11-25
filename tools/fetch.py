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
    <out>/<noncommercial id>/...          non-commercial only; never ship in paid products
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
EBIBLE_NC = {"CC-BY-NC-ND-3.0", "CC-BY-NC-ND-4.0"}

SEFARIA_OPEN = "open"
SEFARIA_NC = "noncommercial"


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

GUTENBERG_LOCC = ("BR", "BS", "BT", "BV", "BX")


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


def fetch_gutenberg(src, out, limit):
    m = Manifest(out / src["id"], src["id"], "Public domain in the USA (per book)")
    cat = http_get("https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv").decode("utf-8")
    rows = [r for r in csv.DictReader(io.StringIO(cat))
            if r.get("Type") == "Text" and any(
                c.strip().startswith(GUTENBERG_LOCC) for c in (r.get("LoCC") or "").split(";"))]
    rows = [r for i, r in enumerate(rows) if in_shard(i)]
    for i, r in enumerate(rows):
        if limit and i >= limit:
            break
        n = r["Text#"]
        try:
            rdf = http_get(f"https://www.gutenberg.org/cache/epub/{n}/pg{n}.rdf", delay=2).decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            m.skip(n, f"rdf failed: {e}")
            continue
        rights = re.search(r"<dcterms:rights>(.*?)</dcterms:rights>", rdf, re.S)
        rights = rights.group(1).strip() if rights else ""
        if rights != "Public domain in the USA.":
            m.skip(n, f"rights: {rights or 'missing'}")
            continue
        url = f"https://www.gutenberg.org/cache/epub/{n}/pg{n}.txt"
        try:
            text = http_get(url, delay=2).decode("utf-8", "replace")
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


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--limit", type=int, default=0, help="stop after N items (for testing)")
    ap.add_argument("--shard", default="0/1", help="process only shard I of N, e.g. 2/4 (eBible, Sefaria, Gutenberg)")
    a = ap.parse_args()
    global SHARD
    i, n = (int(x) for x in a.shard.split("/"))
    SHARD = (i, n)
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
    elif src["id"] == "ebible-nc":
        fetch_ebible(src, out, EBIBLE_NC, a.limit)
    elif src["id"] == "bsb":
        fetch_files(src, out, BSB_FILES)
    elif src["id"] == "openbible-cross-references":
        fetch_files(src, out, [src["upstream"]])
    elif src["id"] == "sefaria-open":
        fetch_sefaria(src, out, SEFARIA_OPEN, a.limit)
    elif src["id"] == "sefaria-nc":
        fetch_sefaria(src, out, SEFARIA_NC, a.limit)
    elif src["id"] == "gutenberg-christian":
        fetch_gutenberg(src, out, a.limit)
    else:
        sys.exit(f"{a.source} is {src['method']}; nothing to fetch")


if __name__ == "__main__":
    main()
