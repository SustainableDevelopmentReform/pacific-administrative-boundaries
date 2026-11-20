# Publishing

This page describes how a release is published. The repository (code, configuration,
documentation, licence, STAC JSON, raw manifests and provenance) goes to GitHub. The data
and the STAC catalog go to AWS S3. Both targets are set in `config/publish.yml`:

| Key | Value |
|---|---|
| `repo_url` | GitHub repository (STAC `about`/`documentation` links and providers point here) |
| `s3_bucket`, `s3_prefix` | `s3://csdr-public-datasets/pacific-administrative-boundaries/` |
| `https_base` | public HTTPS URL of the same prefix (STAC asset hrefs and the root `self` link) |
| `version` | release version, also the git tag used in links to GitHub files (`git_ref` overrides it) |

`data/` is the published root: `data/catalog.json` becomes `<prefix>/catalog.json`, and
`data/processed/FJI/fji_admin.parquet` becomes `<prefix>/processed/FJI/fji_admin.parquet`.
STAC links are relative, so the tree works the same on a local disk and on S3.

## What is published

| Item | GitHub | S3 (`s3://<bucket>/<prefix>/`) |
|---|---|---|
| Code: `pab/`, `scripts/`, `tests/`, `Makefile`, `pyproject.toml`, `uv.lock` | yes | no |
| Configuration: `config/` (countries, levels, EEZ selection, source registers) | yes | no |
| Docs: `README.md`, `docs/`, `CHANGELOG.md`, `CITATION.cff`, `LICENSE` | yes | no |
| STAC: `data/catalog.json`, `data/collection.json`, `data/**/*.stac-item.json` | yes | yes |
| Provenance and checks: `data/**/provenance.json`, `data/combined/partition_checks.json` | yes | yes |
| Raw manifests: `data/raw/**/manifest.json` | yes (STAC items link to them there) | no |
| Processed GeoParquet: `data/processed/**/*.parquet` | no (gitignored) | yes |
| Combined GeoParquet: `data/combined/*.parquet` | no (gitignored) | yes |
| Raw original files: `data/raw/**` other than manifests | no | no |

## What is not published

* **Raw downloads** (decision D-021), including the Marine Regions archives, whose
  publisher asks that its download not be re-hosted. The project has no right to
  redistribute the original files. Every source's manifest (metadata and checksums only)
  is in the GitHub repository, so the provenance chain stays complete. `pab cache <ISO3>`
  re-downloads the originals from their sources; the LINZ layers need your own LINZ API
  key (see [methods.md](methods.md#reproducing-the-build)).
* **The LINZ API key.** It lives in a local, gitignored `.env` file and is never written
  to a register, manifest, STAC item or report.
* **Licence-restricted rows.** There are none in v0.1.0. If a future build has any, they
  go to local `data/processed/<ISO3>/<iso3>_admin_restricted.parquet` files, which are
  gitignored, have no STAC item and are skipped by `pab publish`.
* **Private working notes, agent run logs, and the root `prompts.md`.** All are
  gitignored. Check `git status` before the first commit anyway.

Sources used under a data-use agreement (decisions D-019, D-020: the SPC Pacific Maritime
Boundaries EEZ polygons, and the SPC PCRAFI electoral constituencies of the Cook Islands)
*are* published. Their rows keep their public licence (`license = CC-BY-NC-SA-4.0`) and
name the agreement in `license_agreement`; the STAC items list both. Downstream users are
bound by the public licence unless they hold their own agreement. The LINZ layers (Cook
Islands, Niue, Tokelau) are CC BY 4.0 and are published under that licence.

## Commands

Run these from the repository root after `make all`, once the QA has been reviewed.

```bash
make stac            # pab stac --base-url <https_base> --check: published hrefs, validate, check
make publish-dryrun  # pab publish --dry-run: lists every object, writes reports/publish_dryrun.md
make publish         # pab publish: upload (existing keys are skipped; add --overwrite to replace)
make publish-verify  # pab publish --verify: read the catalog back over HTTPS
```

* `pab publish` uploads with obstore. Credentials come from the standard AWS environment
  variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`), or from
  boto3's credential chain (profiles, SSO) when boto3 is installed. Set the bucket region
  with `--region` or `AWS_REGION`.
* Content types are set per object: `application/vnd.apache.parquet` for GeoParquet,
  `application/geo+json` for STAC Items, and `application/json` for the Catalog, the
  Collection (the STAC media type for both) and the provenance files.
* Without `--overwrite`, keys that already exist are skipped (a warning is logged when the
  size differs). Re-run with `--overwrite` after a rebuild.
* `pab publish --verify [--base-url <url>]` opens `<https_base>/catalog.json` with
  pystac, validates the catalog, the collection and every item, sends a HEAD request for
  every asset (parquet, provenance, and the raw manifests on GitHub, which resolve once
  the release tag is pushed), and reads the smallest GeoParquet file over HTTP with
  DuckDB to compare its row count with `table:row_count`.
* For HTTP access the bucket or prefix must be publicly readable (or fronted by
  CloudFront). Parquet readers use HTTP range requests; S3 and CloudFront both support
  them.
* The bucket is in `ap-southeast-2`. `https_base` in `config/publish.yml` uses the global
  `s3.amazonaws.com` host. Confirm that `pab publish --verify` passes with it; otherwise
  switch to `https://csdr-public-datasets.s3.ap-southeast-2.amazonaws.com/...` and
  rebuild the STAC.
* The v0.1.0 dry run lists 77 objects, 530.6 MB: 25 GeoParquet files (530.2 MB), 25
  STAC items, the catalog and collection, and 25 provenance and check files.

## Release checklist

1. `uv run ruff check --no-fix .` and `uv run pytest -q` pass. CI runs both on every push
   and pull request.
2. `make all` has been run, the QA has been reviewed, and the docs reflect any changes.
3. The version is set in `pyproject.toml`, `pab/__init__.py`, `PRODUCT_VERSION` in
   `pab/stac.py`, `config/publish.yml` and `CITATION.cff`, and `CHANGELOG.md` has an entry.
4. Commit, so the next build records the git commit in `provenance.json` and in the STAC
   items, then rebuild the STAC (`make stac`), commit again and tag:
   `git tag v0.1.0 && git push && git push --tags`. The tag must exist for the STAC links
   to GitHub files to resolve.
5. `make publish-dryrun`, review `reports/publish_dryrun.md`, then `make publish` and
   `make publish-verify`.
6. Create a GitHub release from the tag that links to `<https_base>/catalog.json`.

`repo_url` in `config/publish.yml` is provisional. Confirm the GitHub organisation and
repository name before tagging, because every STAC item links to files on GitHub at the
release tag.
