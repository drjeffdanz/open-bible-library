# Open Bible Library

A free, open archive of historical Bible study resources: original-language texts, translations, lexicons, cross-references, church fathers, Jewish commentary, classic Christian books and biblical geography. Built in the open, in the spirit of [Lastbook](https://lastbook.org/): collect what is free to share, keep it organized, and make it available offline.

**Every item here is public domain or openly licensed, and every license was checked at its source.** Anything that could not be confirmed is left out and listed in [catalog/EXCLUDED.md](catalog/EXCLUDED.md).

## What is in it

The library has two layers.

1. **In this repository (`library/`, about 530 MB):** 14 core datasets that anyone may use for any purpose, including commercial use.
2. **In the monthly archive (GitHub Releases):** everything too large for git or hosted outside GitHub, fetched by `tools/fetch.py` and filtered by license. That includes up to about 20,000 public-domain books from the Internet Archive (commentaries, lexicons, theology, sermons, church fathers, published before 1931), tens of thousands more pre-1931 Internet Archive books and religious periodical issues that pass stricter per-item checks (`archive-org-pd-extended`), about 440 open Bible translations from eBible.org, the Berean Bibles, Sefaria's openly licensed texts, Project Gutenberg's public-domain religious books, the MACULA syntax datasets and the Perseus and First1KGreek corpora.

Non-commercial (NC) material is not collected at all, because the library also feeds paid study material. Everything here can be used commercially under its license.

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
| `library/septuagint/swete-lxx` | Swete's Septuagint (1909-1930), Greek | Text public domain; edition CC BY-SA 4.0 |
| `library/cross-references/tsk-crossreferences-org` | Treasury of Scripture Knowledge, phrase-level, anchored to KJV and BSB | CC BY 4.0 |
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

The **Build archive** workflow does this for every source on the 1st of each month, or on demand from the Actions tab. A full run has 200 jobs and takes a day or more, mostly the Internet Archive downloads. To add one source to an existing release, run it with `only` set to the source id and `tag` set to that release (for example `archive-2026-11`).

## License rules

- Public domain, CC0, CC BY, CC BY-SA, ODbL: allowed in `library/` and in the main archive.
- CC BY-ND: allowed in the main archive only, stored verbatim; never edit, merge or re-translate these files.
- CC BY-NC and CC BY-NC-ND: excluded. The library feeds paid study material, so non-commercial licenses never apply here.
- Anything else, or anything without a clear license: excluded.

"Public domain" here means public domain in the United States. Some works (for example the King James Version in the UK) are still protected elsewhere.

`tools/validate.py` runs on every pull request and blocks non-open material, uncatalogued folders, files over 50 MB and known problem material.

## Using the library in paid products

Everything in `library/` and the main `archive-YYYY-MM` release may be used in commercial work, including a paid study archive, if you follow each license:

- **Public domain and CC0:** no conditions.
- **CC BY (and ODbL):** credit the source as shown in `library/NOTICE.md`.
- **CC BY-SA:** credit the source, and if you publish a modified version or a derivative of that dataset (for example an edited lexicon or a reworked text), that derivative must also be released under CC BY-SA. Quoting it in your own teaching material with credit is fine; selling an edited copy of the dataset under exclusive terms is not.
- **CC BY-ND:** use only verbatim copies, with credit.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The short version: one source per pull request, with a link to the page that shows its license.

## License of this repository

The tools and documentation (`tools/`, `catalog/`, `.github/`, and the top-level `.md` files) are MIT licensed; see [LICENSE](LICENSE). Every dataset keeps its own license, shown in `catalog/sources.yaml` and `library/NOTICE.md`.
