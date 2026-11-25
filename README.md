# Open Bible Library

A free, open archive of historical Bible study resources: original-language texts, translations, lexicons, cross-references, church fathers, Jewish commentary, classic Christian books and biblical geography. Built in the open, in the spirit of [Lastbook](https://lastbook.org/): collect what is free to share, keep it organized, and make it available offline.

**Every item here is public domain or openly licensed, and every license was checked at its source.** Anything that could not be confirmed is left out and listed in [catalog/EXCLUDED.md](catalog/EXCLUDED.md).

## What is in it

The library has three layers.

1. **In this repository (`library/`, about 510 MB):** 12 core datasets that anyone may use for any purpose, including commercial use.
2. **In the monthly archive (GitHub Releases):** everything too large for git or hosted outside GitHub, fetched by `tools/fetch.py` and filtered by license. That includes about 440 open Bible translations from eBible.org, the Berean Bibles, Sefaria's openly licensed texts, Project Gutenberg's public-domain theology and church history books, the MACULA syntax datasets and the Perseus and First1KGreek corpora.
3. **In a separate non-commercial archive:** material that may be shared only for non-commercial use (ETCBC databases, CC BY-NC Sefaria texts, CC BY-NC-ND translations). It never enters `library/`.

### In the repository

| Folder | Contents | License |
| --- | --- | --- |
| `library/hebrew-bible/oshb` | Westminster Leningrad Codex with lemmas and morphology | WLC public domain; morphology CC BY 4.0 |
| `library/greek-new-testament/sblgnt` | SBL Greek New Testament with apparatus | CC BY 4.0 |
| `library/greek-new-testament/morphgnt-sblgnt` | Morphological tagging of the SBLGNT | CC BY-SA 3.0 |
| `library/greek-new-testament/byzantine-robinson-pierpont` | Robinson-Pierpont Byzantine Text 2018, parsed, with apparatus | Public domain (CC0) |
| `library/greek-new-testament/nestle1904` | Nestle 1904 text, morphology, XML, Berean glosses | Public domain / CC0; XML markup CC BY-SA 4.0 |
| `library/greek-new-testament/cntr-transcriptions` | Transcriptions of early Greek manuscripts and historic editions (TR, WH, RP) | CC BY-SA 4.0 |
| `library/tagged-bibles/stepbible` | STEPBible tagged Hebrew and Greek Bibles, lexicons, proper names, versification | CC BY 4.0 |
| `library/lexicons/openscriptures-hebrew-lexicon` | Brown-Driver-Briggs and Strong's Hebrew lexicons | Texts public domain; markup CC BY 4.0 |
| `library/lexicons/strongs` | Strong's Greek and Hebrew dictionaries | Public domain |
| `library/lexicons/abbott-smith` | Abbott-Smith, Manual Greek Lexicon of the NT (1922) | Public domain |
| `library/church-fathers/apostolic-fathers` | Greek Apostolic Fathers (corrected Lake text) | CC BY-SA 4.0 |
| `library/geography/openbible-geocoding` | Every identifiable place in the Bible, with coordinates and sources | CC BY 4.0; OSM geometry ODbL |

Attribution for each dataset is in [library/NOTICE.md](library/NOTICE.md). The full list of sources, with the evidence link for each license, is [catalog/sources.yaml](catalog/sources.yaml).

## Getting the full archive

Open the **Releases** page and download the latest `archive-YYYY-MM` release. Each source is packed separately and split into parts under 2 GB:

```sh
cat ebible-open-shard0of2.tar.gz.part* | tar -xzf -
```

Each archive includes a `MANIFEST*.json` listing every file, its license, its source URL and its SHA-256, plus the items that were skipped and why.

To build it yourself:

```sh
pip install pyyaml
python tools/fetch.py list                     # what can be fetched
python tools/fetch.py ebible-open --out dist   # one source
```

The **Build archive** workflow does this for every source on the 1st of each month, or on demand from the Actions tab.

## License rules

- Public domain, CC0, CC BY, CC BY-SA, ODbL: allowed in `library/` and in the main archive.
- CC BY-ND: allowed in the main archive only, stored verbatim; never edit, merge or re-translate these files.
- CC BY-NC and CC BY-NC-ND: non-commercial archive only. Do not use them in anything sold, including a paid study archive.
- Anything else, or anything without a clear license: excluded.

"Public domain" here means public domain in the United States. Some works (for example the King James Version in the UK) are still protected elsewhere.

`tools/validate.py` runs on every pull request and blocks non-open material, uncatalogued folders, files over 50 MB and known problem material.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The short version: one source per pull request, with a link to the page that shows its license.

## License of this repository

The tools and documentation (`tools/`, `catalog/`, `.github/`, and the top-level `.md` files) are MIT licensed; see [LICENSE](LICENSE). Every dataset keeps its own license, shown in `catalog/sources.yaml` and `library/NOTICE.md`.
