# /wiki-log — Dump session findings to the wiki queue

You are in a work session (bug hunting, feature design, research, etc.). This skill captures knowledge worth keeping without interrupting the primary task.

## What to collect

Review the current session for anything worth preserving:
- Discoveries about how the codebase works
- Patterns or anti-patterns found
- Decisions made and the reasoning behind them
- Guideline candidates — things that should become documented rules or conventions
- Open questions worth investigating later
- External URLs discovered and why they are relevant

**Err on the side of too much rather than too little.** The Wiki AI will curate later.

## How to write the entry

1. Read `~/.config/wiki/config.toml` to get `user.name`.

2. Determine today's date in `YYYY-MM-DD` format.

3. Choose a short kebab-case topic name describing the session (e.g. `tsn-scheduler-bug`, `sbom-tooling-research`).

4. Write the entry to:
   ```
   <vault>/queue/session-log/open/YYYY-MM-DD-<username>-<topic>.md
   ```

5. Use this format:
   ```markdown
   ---
   tags: [relevant, tags]
   author: <user.name from config>
   source-files: [list of relevant file paths, if applicable]
   ---

   ## Findings
   - Concrete things discovered during this session

   ## Guideline candidates
   - Things that should become documented rules or enforced conventions

   ## Open questions
   - Unresolved things worth investigating in a future session

   ## Links
   - https://example.com — why this URL is relevant
   ```

## Rules

- Do **not** read or touch any files in `wiki/` directly
- Do **not** edit `wiki/_index` or any other registry files
- Only write to `queue/session-log/open/`
- If `source-files` is empty, omit the key rather than leaving it as an empty list
- Tags should be specific (prefer `tsn-scheduling` over `tsn`)

## After writing

Tell the user:
- The path of the file written
- A one-line summary of what was captured
