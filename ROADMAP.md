# Daemonstrate — Roadmap

Items listed roughly in order of conviction, not timeline. Each entry includes motivation, a sketch of the implementation surface, and known caveats. If you want to work on one, open an issue and tag the entry name so the conversation has somewhere to live.

---

## Opportunistic compute scheduling (a.k.a. deferred mode)

**Status:** idea · exploring implementation space

### Why

Daemonstrate is expensive to run — especially on first-run, or after a big feature lands. The post-commit hook blunts this by only refreshing scopes whose files changed, but on a busy day a developer can still chew through a non-trivial slice of their Anthropic session-window tokens just keeping diagrams fresh. The tradeoff is unpleasant: *either* you have stale diagrams *or* you spend tokens you'd rather be using for the work you're doing right now.

Most Anthropic plans operate on a rolling session window. Tokens inside that window that go unused *expire* — they don't roll into the next window. Today, daemonstrate ignores that fact and runs whenever commits land, whether or not that moment is a good one to spend.

The idea: **run daemonstrate opportunistically, near the end of each session window, on whatever commits accumulated during it.** The cost moves from *"budget I have to consciously spend on diagrams"* to *"budget that would have expired anyway."* The post-commit hook stops being a tax on every commit and starts being a signal that the diagram *should be* refreshed *eventually*.

This is the same pattern as spot instances, off-peak batch jobs, and overnight backups — workload deferral to a cheaper window. The shape fits daemonstrate unusually well because diagram refresh is batch-friendly, non-blocking, and staleness-tolerant for hours at a time.

### Three implementation sketches

Ordered from least to most ambitious.

#### 1. Scheduled cron (ships today)

Ship a `daemonstrate schedule` invocation that the user sets up via their system's cron, Windows Task Scheduler, or the Claude Code `/schedule` routine. It fires at a fixed clock time the user picks — typically 30 minutes before their session window usually expires.

**What's needed:**

- A `--deferred-run` flag on the skill that implies `/daemonstrate all` with non-interactive defaults and a prominent log-to-file path.
- A documented README recipe: *"schedule this cron, point it at the repos you want auto-maintained, done."*
- `scripts/install-schedule.sh` — writes a reasonable entry in `~/.daemonstrate/cron.d/` and reports what clock time it chose and why.

**Caveats:**

- The cron clock is a *proxy* for "last 20 min of session." If the user's session started 90 minutes before the cron fires, tokens aren't actually about to expire — the intended savings evaporate.
- Multi-repo users need a cron per repo or one cron that walks a watchlist. The watchlist file probably belongs in `~/.daemonstrate/repos.list`.
- Clock-scheduled runs happen whether the user committed or not, which means daemonstrate has to be smart enough to short-circuit on "nothing changed since last run" and log the no-op rather than pay the exploration cost.

#### 2. Local queue + `DAEMONSTRATE_MODE=deferred`

A lighter post-commit hook that doesn't run daemonstrate — it just records the commit SHA in a per-repo queue file:

```
$OUT_DIR/.daemonstrate-queue
  <sha>  <timestamp>
  <sha>  <timestamp>
  ...
```

A separate drainer process (scheduled via mechanism 1, or manually triggered via `/daemonstrate drain`) reads the queue, coalesces commits per scope, and runs daemonstrate in incremental mode on the merged delta. After a successful run the queue is cleared.

**What's needed:**

- `scripts/post-commit-queue.sh` — the lightweight hook body. Replaces the current hook body in the install script when `DAEMONSTRATE_MODE=deferred`.
- `scripts/drain-queue.sh` — drain + invoke daemonstrate on the delta.
- A `--drain` flag on the skill that reads the queue, computes the set of scopes touched since the oldest queued commit, and runs incremental refresh on just those.

**Caveats:**

- Queue files in `.git/` don't always survive `git gc` or worktree reconfiguration. Keep the queue in `$OUT_DIR/.daemonstrate-queue` alongside the scopes catalog — same lifecycle as the rest of daemonstrate's state.
- Queue can grow unboundedly if the drainer never runs. Needs a soft cap (trim to last N commits) or a warning threshold surfaced at the next commit.
- Multi-branch workflow: a queued SHA on branch A becomes meaningless if branch A is deleted without merging. The drainer should filter queue entries to those reachable from the current `HEAD`.

#### 3. Session-window-aware daemon

The "true" version — a background process that:

1. Knows when the user's current session window started.
2. Wakes up at T-20 minutes, checks whether any tracked repo has queued commits, and fires daemonstrate on each.
3. Sleeps until the next window boundary.

This is the purest form of *"use the tokens or lose them."*

**What's needed:**

- **Session-start detection.** This is the hard part. The Anthropic SDK doesn't expose a public "when did my current window start" endpoint. Candidates: parse Claude Code's local telemetry/cache, watch for the first API call of a new window via a wrapper, or have the user stamp session-start manually via a slash-command at the top of each coding session.
- A daemon process — `daemonstrate-watchdog` — packaged as a launchd plist (macOS), systemd unit (Linux), or Windows Service.
- IPC between the daemon and per-repo post-commit hooks (hooks still queue; daemon reads the queue).

**Caveats:**

- Daemons are real software. Silent failures, zombie processes, log rotation, startup order, permission prompts on fresh installs — all real problems that take more engineering than the feature may warrant for a v1. Consider gating this path behind a "brave user" opt-in install.
- Cross-device work (laptop + desktop sharing a repo) needs the daemon to deduplicate — two machines both firing at T-20 minutes would double the cost the scheduling was meant to save.
- Session-window semantics vary across plans. The daemon must degrade gracefully when assumptions break (free tier, direct API-key billing, enterprise quota, usage-based seats).

### Recommended shipping order

1. **Mechanism 1 (cron)** — ship first. Low-effort, gives users a working knob today even if the knob is crude.
2. **Mechanism 2 (queue)** — ship second, once a few users are running scheduled daemonstrate and hit the "stale since the last cron fired" problem.
3. **Mechanism 3 (daemon)** — only if Mechanism 2 proves insufficient, and only if we can answer the session-start-detection question without reverse-engineering Claude Code internals.

### Cross-cutting questions to resolve before any of this ships

- **Default behavior.** Opt-in via env var, or opt-in via a config key in `.daemonstrate-scopes.json`? Former is global, latter is per-repo. Probably per-repo, with a global override.
- **Cost visibility.** How does the user see *"n commits queued, next refresh at HH:MM"*? Claude Code status-line integration? A CLI command? A summary the post-commit hook prints right after the commit lands?
- **Failure mode.** If the scheduled run fails (network, quota, skill error), does it retry immediately, wait for the next window, or surface a notification? Silent failures on a batch job are how diagrams end up two weeks stale without anyone noticing.

---

## Builder coverage for hand-write diagram types

**Status:** spec'd in `SKILL.md` · not started

The builder natively renders 5 of the 8 diagram types Claude can pick in Phase 1:

| Type | Builder flag |
|---|---|
| System Flowchart | `--out-portfolio` / `--out-detailed` |
| Process Flowchart | `--out-journey` |
| Workflow Diagram | inside `--out-detailed` per-scope pages |
| Swimlane Flowchart | `--out-swimlane` |
| Data Flow Diagram | `--out-dfd` |

The remaining three — **Document Flowchart**, **EPC (Event-driven Process Chain)**, and **Influence Diagram** — are hand-written when a scope picks them, per `SKILL.md` §"Unsupported-combo handling." That works but it's slow and error-prone, and it makes these types de-facto second-class.

**What's needed:**

- For each type, a `build_{type}.py` renderer module consumed by `drawio_builder.py` via a new `--out-{type}` flag.
- Visual-vocabulary rules in `references/drawio-format.md` capturing the diagram's standard shapes (e.g., EPC's event-hexagons + function-rects alternation; Influence Diagram's oval-decision / rounded-uncertainty / rectangle-objective grammar).
- Eval coverage in `skills/daemonstrate/evals/evals.json` — at least one repo per type where the scope naturally calls for it.

Priority based on how often these types come up in real scopes: **Influence Diagram > Document Flowchart > EPC**.

---

## Overlay support for portfolio / detailed / journey renderers

**Status:** spec'd in `SKILL.md` · helper framework already exists

Overlays (error paths, latency, data state, tier gates, etc.) currently apply only to Swimlane and DFD outputs. The `apply_overlay_*` helpers in `drawio_builder.py` already work on any already-built `Cell` list, so extending overlay support to the remaining renderers is mechanical:

1. Pass the overlay block through to each renderer's Cell-building code.
2. Call the relevant `apply_overlay_*` helper after the base diagram's cells are assembled and before XML serialization.
3. Emit the overlay legend on each affected page.

**Caveats:**

- The portfolio (single-page poster) has less real-estate for a legend. Consider a compact legend variant.
- Detailed overview pages may apply overlays only to per-scope detail pages rather than the overview itself — overlay on the overview risks visually dominating what's supposed to be a scannable top-level map.

---

## Lower-priority / nice-to-have

- **`.drawio.svg` companion export.** GitHub inlines `.drawio` files only when a companion `.svg` exists. Add an optional `--emit-svg` flag that writes a rendered SVG alongside each `.drawio` output.
- **Scope catalog migration tool.** Handle v1 → v2 catalog upgrades explicitly for users whose catalogs predate the scope-first refactor, instead of the current "treat missing fields as null" implicit migration.
- **Webhook mode.** Instead of a post-commit hook, trigger daemonstrate from a server-side Git hook (or GitHub Actions workflow) so diagrams update regardless of which developer or machine pushed. Opens the door to centralized / team-shared architecture docs.
- **Side-by-side diagram diff.** When a daemonstrate run produces a material change to an `architecture-*.drawio`, generate a side-by-side HTML page comparing old vs. new so reviewers can actually read the diff. Raw `.drawio` XML diffs are unreadable.
