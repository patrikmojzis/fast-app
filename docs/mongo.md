# Mongo Diagnostics

FastApp ships with a MongoDB diagnostics CLI intended for short, targeted performance investigations.

Use it when you want to answer questions like:

- Which collections are active right now?
- Are we looking at reads, writes, or command-heavy traffic?
- Which query shapes are repeating?
- Are we missing an index, or is the current index already good enough?

The command surface is:

```bash
fast-app mongo stats ...
fast-app mongo profile ...
```

## Mental model

There are 2 modes and they solve different problems.

### `stats`

Low-overhead sampler built from Mongo `serverStatus` and `top`.

Use it for:

- quick triage
- deciding which namespace to inspect next
- checking whether your traffic burst actually hit Mongo

Do not use it as the final answer for index design.

### `profile`

Short-lived profiler capture built from `<db>.system.profile`.

Use it for:

- recurring query-shape discovery
- collection scan detection
- candidate index suggestions
- confirming whether a hot path is already covered by an index

This is the mode to use when you are trying to decide which index to add.

## Safety

`stats` is read-only.

`profile` is *not* read-only:

- it temporarily changes the selected database profiler level
- Mongo writes profiler rows into `<db>.system.profile`
- it restores the original profiler state automatically after the window ends

It does not write to your app collections.

Because it changes database profiler state, `profile` requires:

```bash
--dangerously-enable-profiler
```

## Basic usage

Quick sampler:

```bash
fast-app mongo stats --seconds 5
```

Focus on specific collections:

```bash
fast-app mongo stats --seconds 5 --namespace lead --namespace order
```

Capture profiler findings:

```bash
fast-app mongo profile --dangerously-enable-profiler --seconds 15
```

Capture everything in a short window:

```bash
fast-app mongo profile --dangerously-enable-profiler --capture-all --seconds 5
```

JSON output for scripts or AI agents:

```bash
fast-app mongo profile --dangerously-enable-profiler --capture-all --seconds 5 --json
```

## Recommended workflow

### 1. Start with `stats`

Use `stats` to answer: "did my traffic actually touch Mongo, and where?"

Example:

```bash
fast-app mongo stats --seconds 3 --namespace lead --namespace order
```

What it prints:

- `Server summary (global Mongo counters)`:
  counters across Mongo for the whole sample window
- `Displayed namespaces`:
  totals for the rows actually printed below
- namespace table:
  per-namespace read/write rate and time

Interpretation:

- if global counters move but your namespace table is empty, your traffic likely hit a different collection or database
- if your namespace rows appear, move to `profile`

### 2. Run `profile` on a narrow scope

Prefer namespace filters early.

```bash
fast-app mongo profile \
  --dangerously-enable-profiler \
  --capture-all \
  --seconds 5 \
  --namespace lead \
  --namespace order
```

This keeps the report small and makes the findings usable.

### 3. Narrow to suspicious findings

Collection scans only:

```bash
fast-app mongo profile \
  --dangerously-enable-profiler \
  --capture-all \
  --seconds 5 \
  --namespace lead \
  --only-collection-scans
```

Only surviving index suggestions:

```bash
fast-app mongo profile \
  --dangerously-enable-profiler \
  --capture-all \
  --seconds 5 \
  --namespace lead \
  --only-suggestions
```

Thresholded noisy app traffic:

```bash
fast-app mongo profile \
  --dangerously-enable-profiler \
  --capture-all \
  --seconds 5 \
  --namespace lead \
  --min-count 3 \
  --min-docs-examined 100 \
  --min-scan-ratio 3
```

### 4. Turn profiler output into index work

The profiler is best treated as:

1. find the hot query family
2. inspect the suggested key order
3. compare with existing indexes
4. validate with `explain("executionStats")` before shipping

If the report prints an index candidate, that means:

- the shape repeated
- the heuristics think the query is still wasteful enough to be worth attention
- the candidate is not already covered by an existing index prefix

If the report prints an `Existing index notes` row, that means:

- the shape was seen
- the tool deliberately suppressed the candidate because it appears already covered

## Triggering traffic deliberately

Both `stats` and `profile` emit a ready line to `stderr`.

Wait for it before generating traffic from another terminal or agent command.

`stats` ready line:

```text
Mongo activity sampling started for `<db>`. Waiting ...
```

`profile` ready line:

```text
Mongo profiler enabled for `<db>`. Capturing for ...
```

This matters if you want the capture window to line up with your request burst.

## Agent usage

For agents and scripts, prefer:

- `--namespace` to stay focused
- `--limit` to keep the output bounded
- `--json` for structured consumption
- `--only-suggestions` when the goal is index hunting

## Useful recipes

### Read-only health check

```bash
fast-app mongo stats --seconds 5 --namespace lead
```

### Show only likely new index work

```bash
fast-app mongo profile \
  --dangerously-enable-profiler \
  --capture-all \
  --seconds 5 \
  --namespace lead \
  --only-suggestions
```

### Investigate only collection scans

```bash
fast-app mongo profile \
  --dangerously-enable-profiler \
  --capture-all \
  --seconds 5 \
  --only-collection-scans
```

### Include writes too

```bash
fast-app mongo profile \
  --dangerously-enable-profiler \
  --capture-all \
  --seconds 5 \
  --include-writes
```

### Machine-readable capture

```bash
fast-app mongo profile \
  --dangerously-enable-profiler \
  --capture-all \
  --seconds 5 \
  --namespace lead \
  --json
```

## How to read the profiler table

Columns:

- `namespace`: collection namespace
- `op`: grouped Mongo operation, usually `find` or `aggregate`
- `plan`: winning plan summary such as `COLLSCAN` or `IXSCAN {...}`
- `count`: how many profile rows collapsed into this grouped finding
- `totalMs`: cumulative latency for the grouped finding
- `avgMs`: average latency per occurrence
- `scan/ret`: `docsExamined / nreturned`
- `shape`: normalized filter/sort shape

Rules of thumb:

- `COLLSCAN` is always worth attention
- high `scan/ret` usually means wasted reads
- repeated findings matter more than one-offs
- a good `IXSCAN` with low `scan/ret` usually does not need a new index

## What the tool is trying to suppress

The profiler intentionally avoids noisy or misleading suggestions.

It suppresses:

- `_id` lookups
- candidates already covered by an existing index prefix
- weak suggestions where the observed scan behavior is not bad enough

That is deliberate. The goal is not to print every possible index shape. The goal is to print the ones still worth human attention.

## Common caveats

### `stats` is a sampler, not a proof

`stats` is useful for triage. `profile` is the authoritative mode for query-shape debugging.

### `profile` is database-wide for the selected database

During the capture window, Mongo profiling is enabled for the whole selected database.
Keep the window short and use namespace filters in the report.

### Installed package vs source tree

If behavior looks wrong while developing FastApp itself, verify which `fast_app` package your current shell is executing.

Example:

```bash
python -c "import fast_app; print(fast_app.__file__)"
```

If you are validating uninstalled source changes, you may need to run with an explicit `PYTHONPATH` pointing at the FastApp repo.

## Related docs

- `docs/cli.md`
- `docs/models.md`
