# Bolsa Família — reproducible data collection

Independent project using Brazil's CGU Transparency Portal API. Public code and methodology are separated from the private website. No credentials, personal records or large datasets belong in Git.

Python 3.10+; standard library only. Run `python scripts/extract.py catalog`, configure `PORTAL_TRANSPARENCIA_API_KEY` securely, then run `collect --start YYYYMM --end YYYYMM --city IBGE_CODE`. Omit city only after a validated pilot and a national cost/coverage estimate. `--kind beneficiaries` collects individual payment rows, removes CPF/NIS from published display data and groups annual amounts using source identity rather than names. Source responses remain local and ignored by Git.

API responses are paginated until an empty array. Rate limiting, transient retry, original-byte SHA-256 manifests and scope checks are implemented. Empty results are missing coverage, never implicit zero. Hashes are locally computed evidence, not official CGU signatures. Monthly beneficiary counts must never be summed into annual unique persons. Annual amounts sum available months; beneficiary series uses monthly averages. Partial years and geographic coverage must be disclosed. Current series starts March 2023; predecessor programs and inflation adjustment are pending.

**Initial implementation: no authenticated production collection or certified national totals yet.** Synthetic tests only. No scheduler or deployment is activated. The Portuguese methodology documents exact calculations and known limits.
