---
name: wiki-resolve
description: >
  Resolve a lint case file produced by the Lint AI. Reads the case file,
  loads the affected wiki articles, presents the issues to the user, and
  applies approved fixes. Supports both direct-edit (single-user) and
  branch+MR (multi-user) resolver modes. Use when given a lint case file
  from queue/lint/open/.
compatibility: >
  Intended to be run from the vault directory (~/wiki). Vault path and
  resolver.mode read from ~/.config/wiki/config.toml. Branch mode requires git.
argument-hint: [<case-file>]
disable-model-invocation: true
allowed-tools: Read Write Bash(git:*) Bash(${CLAUDE_SKILL_DIR}/../wiki-context/scripts/wiki:*)
---

Resolve a lint case file produced by the Lint AI. The user invokes this as:
```
/wiki-resolve [queue/lint/open/YYYY-MM-DD-<topic>.md]
```

The case file argument is optional. If omitted, the most recent file in `queue/lint/open/` is used.

## Setup

1. Resolve the vault root:
   - Check if the current working directory is inside a vault: look for `wiki/_index` in the cwd or any ancestor directory. If found, use that ancestor as the vault root.
   - Otherwise, read `vault.path` from `~/.config/wiki/config.toml`.

   Then read `resolver.mode` (`direct` or `branch`) from `~/.config/wiki/config.toml`.

2. Resolve the case file:
   - If an argument was given, use it (relative to vault root if not absolute).
   - If no argument was given, list `<vault>/queue/lint/open/`, pick the file with the latest date in its name, and tell the user which file was selected before proceeding.

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
2. Run `${CLAUDE_SKILL_DIR}/../wiki-context/scripts/wiki check --fix` to normalize any frontmatter
3. Move the case file: rename from `queue/lint/open/` to `queue/lint/resolved/`
4. Only if the user requests to commit: `git add -A && git commit -m "resolve: <case-name>"`

### If `resolver.mode = "branch"` (multi-user / work)

1. Before making any edits, run:
   ```
   git checkout -b wiki/resolve/<case-name>
   ```
   where `<case-name>` is the case filename without the date prefix and `.md` extension.

2. Edit wiki articles on that branch.

3. Run `${CLAUDE_SKILL_DIR}/../wiki-context/scripts/wiki check --fix` to normalize any frontmatter.

4. Move the case file to `queue/lint/resolved/`.

5. Commit and push. If the user requests opening a merge request, include push options (GitLab, requires Git 2.18+):
   ```
   git add -A
   git commit -m "resolve: <case-name>"

   # GitLab — open MR via push options:
   git push origin wiki/resolve/<case-name> \
     -o merge_request.create \
     -o merge_request.title="Wiki resolve: <case-name>" \
     -o merge_request.description="<summary of findings and changes>" \
     -o merge_request.remove_source_branch

   # GitHub or plain push (no push-option support):
   git push origin wiki/resolve/<case-name>
   # Then open the merge/pull request via the web UI or your git host's CLI.
   ```

6. If a merge request was opened, add a `## MR` section to the resolved case file with the URL for traceability.

## After completing

Summarise for the user:
- What was changed and in which articles
- What was left unresolved (if anything) and why
- What they should review before merging (branch mode) or committing (direct mode)
