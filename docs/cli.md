# CLI Overview

FastApp ships with a modular CLI. Run `fast-app -h` from a project root to list commands.

- `init` — scaffold a new FastApp project in the current directory
- `make` — generate code from templates (models, resources, middlewares, etc.)
- `publish` — copy optional feature modules (socketio, notification channels)
- `migrate` / `seed` — execute your app-level database migrations and seeders
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

Common types include `model`, `resource`, `schema`, `middleware`, `observer`, `policy`, `event`, `factory`, `migration`, `command`, `room`, and more (see `fast_app/cli/make_command.py`).

Example:
```python
fast-app make model User
fast-app make resource UserResource
fast-app make schema UserSchema
fast-app make middleware AuthMiddleware
fast-app make observer UserObserver
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

### `fast-app seed`

Execute a seeder from `app/db/seeders/<name>.py`.

```bash
fast-app seed UserSeeder
```

Supports contract-based seeders (implementing `fast_app.contracts.seeder.Seeder`) and legacy `seed()` / `run()` functions.

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

### `fast-app version`

Print the installed FastApp version (reads `pyproject.toml` first, then package metadata).

```bash
fast-app version
```

Useful for confirming the framework version in CI or debugging.
