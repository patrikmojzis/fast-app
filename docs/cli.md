# CLI Overview

FastApp ships with a modular CLI. Run `fast-app -h` from a project root to list commands.

- `init` — scaffold a new FastApp project in the current directory
- `make` — generate code from templates (models, resources, middlewares, etc.)
- `publish` — copy optional feature modules (socketio, notification channels)
- `migrate` / `seed` — execute your app-level database migrations and seeders
- `mongo` — inspect MongoDB activity, temporary profiler findings, and candidate index suggestions
- `indexes` — inspect and synchronize MongoDB indexes declared on models
- `serve` — run the development ASGI server via Hypercorn with auto-reload
- `work` — start the async_farm worker supervisor (with optional TUI)
- `exec` — discover and run app-specific async commands from `app/cli`
- `version` — print the installed FastApp version

All commands accept `-h`/`--help` for detailed usage.

## Command Reference

### `fast-app init`

Scaffold the starter project (using templates under `fast_app/templates/project_structure`).

```bash
fast-app init
```

Copies the template files into the current directory and prints suggested next steps.

### `fast-app make`

Create boilerplate files from FastApp templates.

```bash
fast-app make <type> <Name>
```

Common types include `model`, `controller`, `resource`, `schema`, `rule`, `middleware`, `observer`, `policy`, `event`, `factory`, `migration`, `command`, `room`, and more (see `fast_app/cli/make_command.py`).

Example:
```python
fast-app make model User
fast-app make controller user_controller
fast-app make resource UserResource
fast-app make schema UserSchema
fast-app make rule LongitudeRule
fast-app make middleware AuthMiddleware
fast-app make observer UserObserver
```

You can override the destination directory with `--path` (relative to the project root):

```bash
fast-app make observer UserObserver --path app/observers/custom
```

### `fast-app publish`

Copy optional packaged modules into your project.

```bash
fast-app publish <package>
```

Available packages live in `fast_app/templates/publish`. If you request an unknown package, the CLI lists the available ones.

### `fast-app migrate`

Run a migration from `app/db/migrations/<name>.py`.

```bash
fast-app migrate AddIndexToUsers
```

The command loads the migration module, prefers classes implementing `fast_app.contracts.migration.Migration`, and falls back to legacy functions (`migrate()`, `run()`). It reports success or failure in the console.

Override the migrations directory with `--path` (relative to the project root):

```bash
fast-app migrate AddIndexToUsers --path app/db/migrations
```

### `fast-app mongo`

Inspect MongoDB activity with a coarse stats window or capture grouped profiler findings with tighter candidate index suggestions.

For a workflow-oriented guide with interpretation notes and common recipes, see `docs/mongo.md`.

```bash
fast-app mongo stats
fast-app mongo stats --seconds 5 --limit 10
fast-app mongo profile --dangerously-enable-profiler --seconds 15
fast-app mongo profile --dangerously-enable-profiler --capture-all --include-writes --json
```

`stats` samples `serverStatus` and `top` over a bounded time window and prints both global Mongo counters and the totals for the displayed namespace rows. It is best used as a low-overhead activity sampler, not as the final word on index bottlenecks.

If you want to trigger reads during the sampling window, wait for the stderr line `Mongo activity sampling started for <db>...` before generating traffic.

`profile` temporarily changes the selected database profiler level for the requested window, waits briefly for profiler rows to flush, reads a bounded slice of matching `system.profile` rows, groups recurring query shapes, applies namespace and threshold filters, suppresses obviously redundant index suggestions, and records when a finding is already covered by an existing index prefix. Because that change is intrusive and database-wide for the selected database, `profile` requires `--dangerously-enable-profiler`.

When you need to trigger traffic from another terminal or agent command, wait for the stderr line `Mongo profiler enabled for <db>...` before starting reads or writes you want to observe.

Useful options:
- `--database` overrides `DB_NAME` / `TEST_DB_NAME`
- `--namespace` / `--exclude-namespace` focus on specific collections such as `lead` or `db.lead`
- `--json` prints structured JSON for scripts and AI agents
- `--limit` keeps the output bounded
- `--max-profile-docs` caps how many profiler rows are scanned from the selected window
- `--only-collection-scans`, `--only-suggestions`, `--min-count`, `--min-docs-examined`, and `--min-scan-ratio` help isolate suspicious findings on noisy apps
- human-readable profiler output also prints existing-index notes for visible findings that were suppressed as redundant suggestions
- `--capture-all` switches from slow-op profiling to full capture for the window
- `--include-writes` includes write operations in grouped profiler findings

### `fast-app indexes`

Inspect and reconcile MongoDB indexes declared on model metadata (`Model.indexes`).

```bash
fast-app indexes status
fast-app indexes status --verbose
fast-app indexes check
fast-app indexes sync --dry-run
fast-app indexes sync
fast-app indexes sync --drop-stale
```

`status` prints drift summary without changing the database.
Use `--verbose` to print collection-level details and declared index names even when there is no drift.

`check` is CI-oriented and exits with:
- `0` when there is no drift
- `2` when drift is detected
- `1` on runtime errors

`sync` creates missing indexes and recreates changed ones.

`sync --dry-run` previews changes and exits with:
- `0` when no changes are needed
- `3` when changes would be applied
- `1` on runtime errors

By default, stale indexes are kept. Use `--drop-stale` to remove indexes that are not declared by model metadata.

### `fast-app seed`

Execute a seeder from `app/db/seeders/<name>.py`.

```bash
fast-app seed UserSeeder
```

Supports contract-based seeders (implementing `fast_app.contracts.seeder.Seeder`) and legacy `seed()` / `run()` functions.

Override the seeders directory with `--path` (relative to the project root):

```bash
fast-app seed UserSeeder --path app/db/seeders
```

### `fast-app serve`

Launch the development Hypercorn server with auto-reload.

```bash
fast-app serve [--bind 0.0.0.0:8000] [--app app.modules.asgi.app:app] [--reload-dir path]
```

- Enforces `--reload` and `--debug` flags automatically.
- Watches the project and optional directories for changes.
- `--log-level` allows overriding the default `debug` noise level.

Intended for local development only.

### `fast-app work`

Start the async_farm supervisor to process background jobs.

```bash
fast-app work [--tui] [--verbose]
```

- Default mode runs the supervisor until shutdown.
- `--tui` launches the interactive dashboard (`SupervisorTUI`).
- Respects environment variables such as `MIN_WORKERS`, `MAX_WORKERS`, and `PREFETCH_PER_WORKER` for tuning.

### `fast-app exec`

Discover and run async commands defined in your app’s `app/cli` package.

```bash
fast-app exec --list               # show available commands
fast-app exec reports:daily --date 2024-01-01
```

- Auto-discovers classes extending `fast_app.Command` under `app/cli`.
- Supports an optional `app.cli.provider.get_commands()` hook for manual registration.
- Validates that command `execute()` methods are async; otherwise raises an error.

Override the app command directory with `--path` (relative to the project root):

```bash
fast-app exec --list --path app/cli/admin
```

### `fast-app version`

Print the installed FastApp version (reads `pyproject.toml` first, then package metadata).

```bash
fast-app version
```

Useful for confirming the framework version in CI or debugging.
