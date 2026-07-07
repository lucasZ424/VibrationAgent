# Operator UI

Start the local API and open the browser UI:

```powershell
.\.venv\Scripts\python.exe scripts\start_operator.py
```

The script starts `apps.api.main:app` with Uvicorn on `127.0.0.1:8000`, waits for
`/health`, and opens:

```text
http://127.0.0.1:8000/operator
```

Press `Ctrl+C` in the terminal to stop the server.

Useful options:

```powershell
.\.venv\Scripts\python.exe scripts\start_operator.py --port 8010
.\.venv\Scripts\python.exe scripts\start_operator.py --no-browser
.\.venv\Scripts\python.exe scripts\start_operator.py --restart
.\.venv\Scripts\python.exe scripts\start_operator.py --stop
```

Use `--restart` after backend or UI code changes if an older API process is
already listening on the same port. Use `--stop` to shut down the operator API
without opening the browser.

After any out-of-process corpus reindex, Qdrant rebuild, or
`taxonomy/corpus_standards.yaml` catalog rebuild, restart the API before
trusting retrieval results:

```powershell
.\.venv\Scripts\python.exe scripts\start_operator.py --restart
```

The reindex command clears caches only in its own process. A separately running
API process can still hold the old runtime lexical payload cache or standard
catalog cache until it is restarted. In-process callers may instead invoke the
runtime retrieval-state clear helper directly.

The UI sends `/query` requests and renders the human-readable
`structured_result.answer` first. Raw JSON remains visible for diagnostics.

By default the Chunks Dir field is `data/chunks`, matching the current
file-backed retrieval workflow.
