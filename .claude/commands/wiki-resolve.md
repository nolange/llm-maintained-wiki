# /wiki-resolve — Resolve a lint case interactively

Resolve a lint case file produced by the Lint AI. The user invokes this as:
```
/wiki-resolve queue/lint/open/YYYY-MM-DD-<topic>.md
```

## Setup

1. Read `~/.config/wiki/config.toml` to get `resolver.mode` (`direct` or `branch`) and `vault.path`.

2. Read the specified case file from `<vault>/queue/lint/open/`.

3. Read all articles listed in the case file's `articles:` frontmatter field.

4. Present the findings clearly to the user:
   - Which articles are involved
   - What the issues are
   - What the Lint AI recommended

## Working through the case

Work interactively with the user — do not make large or destructive changes without confirmation.

When editing articles:
- Preserve existing content unless it is directly contradicted by another article
- Update `status:` to `stable` in frontmatter for articles that are fully resolved
- Never change the `folder:` frontmatter key if the user set it
- Keep changes focused on what the case file identifies — do not refactor unrelated content

If a contradiction cannot be resolved without more information:
- Add an `## Unresolved` section to the case file describing exactly what needs human input
- Do not guess — flag it and move on

## Completing the case

### If `resolver.mode = "direct"` (single-user / personal)

1. Edit wiki articles directly on the current branch
2. Move the case file: rename from `queue/lint/open/` to `queue/lint/resolved/`
3. Suggest the user run `git add -A && git commit -m "resolve: <case-name>"`

### If `resolver.mode = "branch"` (multi-user / work)

1. Before making any edits, run:
   ```
   git checkout -b wiki/resolve/<case-name>
   ```
   where `<case-name>` is the case filename without the date prefix and `.md` extension.

2. Edit wiki articles on that branch.

3. Move the case file to `queue/lint/resolved/`.

4. Commit and push:
   ```
   git add -A
   git commit -m "resolve: <case-name>"
   git push origin wiki/resolve/<case-name>
   ```

5. Open a PR:
   ```
   gh pr create --title "Wiki resolve: <case-name>" --body "<summary of findings and changes>"
   ```

6. Add a `## PR` section to the resolved case file with the PR URL for traceability.

## After completing

Summarise for the user:
- What was changed and in which articles
- What was left unresolved (if anything) and why
- What they should review before merging (branch mode) or committing (direct mode)
