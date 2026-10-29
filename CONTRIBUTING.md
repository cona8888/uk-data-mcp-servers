# Help improve Groundwork

Useful contributions include clearer setup instructions, accessible UI fixes,
reproducible bug reports and adapters for underrepresented UK nations.

## Report a problem or suggest a source

[Open an issue](https://github.com/cona8888/uk-data-mcp-servers/issues/new).
Include your operating system, Python version, the steps you tried and the error.
For a data source, include its official documentation, geographic coverage,
access requirements and licence.

Use a public demonstration point or synthetic data. Remove private site details,
personal information, API keys and account data. Do not upload original reports
unless their redistribution terms permit it.

## Work on the code

Read [AGENTS.md](AGENTS.md) and the [architecture guide](docs/ARCHITECTURE.md).
Install from a checkout:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q -m "not live"
python -m ruff check .
node --check src/uk_data_mcp/web/app.js
node --test tests/frontend/report-validation.test.cjs
```

Use your virtual environment's Python executable. Tests use synthetic or saved
public data. Live provider checks are opt-in; keep requests small and rate-limited.
Node.js is needed only for the two frontend checks above; CI uses Node.js 22.

Keep source dates, units, licence notices, quality flags and coverage gaps with
each result. Empty data must not become a safety claim. Design parameters stay
unknown unless a separately reviewed method establishes them.

Describe the problem, resulting behaviour and checks in your pull request.
Code is MIT licensed; provider data retain their own terms.
