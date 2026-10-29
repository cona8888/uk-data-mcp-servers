# Start Groundwork

## The simplest route

Install Python 3.11 or newer from [python.org](https://www.python.org/downloads/).
[Download the project ZIP](https://github.com/cona8888/uk-data-mcp-servers/archive/refs/heads/main.zip),
extract it, and open a terminal inside the extracted folder.

On Windows:

```powershell
py launch.py
```

On macOS or Linux:

```bash
python3 launch.py
```

The launcher creates a project-local `.venv`, installs the application and opens
the local browser workspace. It prints the address and uses an available local
port. Keep the terminal running. Press **Ctrl+C** to stop.

The first installation needs internet access. Later launches reuse the installed
environment when application files are unchanged. Fresh provider queries need
internet; saved examples can be opened offline after installation.

## Your first study

1. Choose **Explore Birmingham demo** for the bundled, dated public example.
2. Open **Historic investigations** to inspect candidates. Read original records
   under their terms before marking one relevant; the app does not interpret them.
3. Open **GI gap register** to see missing evidence and add review notes.
4. Inspect **Sources & provenance** for dates, query outcomes and licences.
5. Choose **Save study JSON** to keep edits. Browser memory is not permanent storage.

For the small-house scenario, save the [Leeds JSON](https://raw.githubusercontent.com/cona8888/uk-data-mcp-servers/main/examples/leeds_small_house_example_2026-10-29.json)
to your computer and choose **Open saved study**. It is a hypothetical project,
with the source date and outstanding questions kept visible.

For a new study, enter the project name, WGS84 latitude/longitude, UK nation and
proposed works. The point is a search location, not a surveyed site boundary.
Use the request limits to keep live searches small, then select **Gather site evidence**.

## Manual installation

Run these commands inside the extracted project folder. No environment activation
is needed.

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m uk_data_mcp app
```

macOS / Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python -m uk_data_mcp app
```

Open the printed local address, normally `http://127.0.0.1:8765`.
The package is installed from this folder; it is not published to PyPI.

## If something goes wrong

| What you see | What to try |
|---|---|
| Python command not found | Install Python 3.11+; on Windows try `python launch.py` if `py` is unavailable |
| Missing `venv` or `ensurepip` on Linux | Install your distribution's Python venv package, then retry |
| Installation fails | Check internet/proxy access to your organisation's approved Python package index; keep the terminal error for an issue |
| Browser does not open | Copy the printed local address into your browser; leave the terminal running |
| Port already in use | Use the launcher's available-port choice, or run the manual app with `--port 8766` |
| App still shows older code after a Git update | Run `launch.py` again, or repeat the manual `pip install .` command and restart |
| A source query is empty, partial or fails | Read its source entry; these outcomes do not establish absence of a ground hazard |

Add `--no-browser` to the launch command to leave the browser closed, or `--help`
to see the options. The app is local and has no multi-user authentication;
use the [deployment guide](DEPLOYMENT.md) before considering a hosted service.

Known example issues and limits are recorded in the [Leeds validation](../examples/leeds_small_house_validation_2026-10-29.json).
Keep private site workspaces out of this public repository.
