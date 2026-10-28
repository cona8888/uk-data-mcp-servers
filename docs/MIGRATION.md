# Standalone repository import

Date: **28 October 2026**.

Destination: [cona8888/uk-data-mcp-servers](https://github.com/cona8888/uk-data-mcp-servers), branch `main`.

The owner created this repository as **public**. The import preserves that visibility and copies only the MCP project, not unrelated private research files or the source repository's history.

## Imported project

Source repository: `cona8888/UK_infra`.

Source commit: `7434e9965ac6690e060a881a4b10a2eaa45c7087`.

Source directory: `mcp/uk-data-mcp-servers/`.

Source project tree: `3a7927ee38051cfb9ebefee67f9d1ddfe80dcd1d`.

The 45 original project files are copied to the new repository root without changes. This includes runtime code, the 36-entry source registry, seven test modules, documentation, Docker files, client templates, the live-check script and the saved Birmingham example. Git blob hashes provide the byte-for-byte comparison with the source snapshot.

Three files are new: `AGENTS.md`, this import record, and [EXISTING_PROJECTS.md](EXISTING_PROJECTS.md). The original README and software notices are retained. The original `UK_infra` branch and draft pull request are not modified or merged by this import.

## Validation scope

This task checks transfer integrity and the committed repository contents. It does not change the implementation or perform a new engineering assessment.

[VALIDATION.md](VALIDATION.md) and `live-checks-2026-10-27.json` are inherited records dated **27 October 2026**. Their recorded 86 passing offline tests and 18 successful live checks describe the earlier execution, not a fresh run on the import date. No runtime test suite, live provider suite or Docker build was rerun for this repository transfer. The saved Birmingham response retains its original retrieval timestamps and observation-quality warnings.

Before changing dependencies or deploying elsewhere, reproduce the checks in `VALIDATION.md`. Dataset availability, provider terms and software compatibility can change after those recorded checks.

## Start from the standalone repository

```bash
git clone https://github.com/cona8888/uk-data-mcp-servers.git
cd uk-data-mcp-servers
```

Then follow the platform-specific installation and MCP client instructions in [README.md](../README.md). The package is at the repository root; the old `mcp/uk-data-mcp-servers` prefix is not part of the new layout. No server is automatically deployed or registered with an AI client by committing these files.
