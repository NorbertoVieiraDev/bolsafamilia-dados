# Bolsa Família — reproducible official data

Independent project using CGU's Transparency Portal monthly files, with authenticated API reconciliation. The private website repository is separate. Credentials, raw personal records and large datasets do not belong in Git.

The national history contains **43 monthly files, March 2023–September 2026, 859,194,021 source rows**. File hashes, row counts, monetary totals and coverage are in `reports/history/source-manifest.json`. API pilots matched amounts and quantities for São Paulo/202601, Rio Branco/202303 and Rio de Janeiro/202406; this is sample reconciliation, not API certification of every cell.

CSV geography uses SIAFI identifiers, not IBGE. The site uses explicit `siafi-XXXX` keys. Retroactive rows with older payroll references remain included. Monthly quantities count distinct non-null NIS by municipality plus each row without NIS. Annual quantity charts use monthly averages; they do not claim annual unique people or all household members. Partial years and absent data are explicit.

Nominal historical amounts and IPCA-adjusted amounts are presented side by side in the main indicator, time-series table and CSV. The official SGS 433 series consulted on 2026-11-06 ends September 2026. Each monthly municipal amount is adjusted to that common base before annual/geographic sums. Missing indices fail explicitly. Individual name/amount lists are explicitly nominal.

Python 3.10+ is required. API collection uses the standard library; bulk processing requires pinned DuckDB from `requirements.txt`. Run `scripts/bulk.py --help`, `scripts/pages_data.py --help`, and `python -m unittest discover -s tests -v` after installation. The bounded manual GitHub Actions pilot uses `PORTAL_TRANSPARENCIA_API_KEY` stored as a repository secret. The website does not use that key.

Sanitized lookup assets contain only names, amounts and normalized search names, not CPF/NIS/source person keys. The owner explicitly authorized their public Pages destinations. Source identities stay local for exact annual grouping, including homonym separation. Lookup data and large originals are hosted/stored outside Git. The public repository carries the reproducible method, official-source records and aggregate evidence. There is no automatic schedule; future updates must use new audited immutable releases.
