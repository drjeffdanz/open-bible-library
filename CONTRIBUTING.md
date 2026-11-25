# Contributing

Thank you for helping build the library. The one rule that matters most: **if you cannot show that a work may be redistributed, it does not go in.**

## Adding a source

1. Find the source's own license statement: a LICENSE file, a copyright page, or a rights field in its metadata. A third-party site saying "public domain" is not enough.
2. Classify it:
   - **open**: public domain, CC0, CC BY, CC BY-SA, ODbL, or a clear "may be freely copied" statement.
   - **open-nd**: CC BY-ND. Archive verbatim only.
   - **excluded**: CC BY-NC or CC BY-NC-ND (the library feeds paid products), and anything else: "all rights reserved", "personal use only", "permission required", fair-use excerpts, or no license at all. Add it to `catalog/EXCLUDED.md` with the reason.
3. Add an entry to `catalog/sources.yaml` with `license`, an `evidence` URL that shows it, `attribution` if the license requires credit, and the upstream `commit` if you vendor it.
4. Decide where it lives:
   - **vendored** into `library/<group>/<name>/` only if it is tier `open`, mostly text, and each file is under 50 MB.
   - **mirror** (large GitHub repos) or **fetch** (other hosts) otherwise; add a handler in `tools/fetch.py` if needed and a line to `.github/workflows/build-archive.yml`.
5. Run `python tools/validate.py --write-notice` and then `python tools/validate.py`.
6. Open a pull request with one source per PR.

## Things to watch for

- **Old text, new edition.** A 19th-century text is public domain, but a modern edition's introduction, notes, translation, cover art or markup may not be. Check what you are actually copying.
- **Translations of ancient works.** Augustine is public domain; a 1990s translation of Augustine is not.
- **Compilations.** A repository with an open license can still contain files under other terms. Read the README of every subfolder.
- **Site terms.** CCEL, Bible Gateway, Bible Hub, Blue Letter Bible and similar sites restrict bulk copying even of public-domain texts. Use Project Gutenberg, Wikisource, archive.org scans with clear rights, or the original open dataset instead.
- **Images.** Manuscript photos are usually under the holding institution's terms. Link to them; do not copy them.
- **Jurisdiction.** "Public domain" in this project means public domain in the United States. Note known exceptions (such as the KJV in the UK).
