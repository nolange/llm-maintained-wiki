# /wiki-ask — Answer a question using the wiki

Answer the user's question using the wiki as the knowledge base.

## Steps

1. **Orient** — Read `<vault>/wiki/_index` (tab-separated: filename, tags, title) to see what articles exist.

2. **Select** — Identify the 3–5 most relevant articles for the question based on title and tags. Prefer specificity: a narrowly-tagged article on the exact topic beats a broad overview.

3. **Read** — Read the selected articles in full.

4. **Follow links** — If the answer requires more context and an article links to another relevant article, read that too. Stop after two hops — do not traverse the entire wiki.

5. **Answer** — Respond directly and concisely. For every claim, cite the source article inline: `(→ article-name.md)`.

## Be explicit about what the wiki covers

Distinguish clearly between:
- What the wiki **states directly**
- What is **reasonably inferred** from wiki content
- What the wiki **does not cover** (gaps worth noting)

Do not hallucinate facts not present in the provided articles. If the wiki is silent on something, say so.

## Output format

**For brief factual questions:** Answer inline. No output file needed.

**For substantial answers** (more than a few sentences):
- Answer inline
- Also write the answer to `<vault>/outputs/YYYY-MM-DD-<topic>.md`
- Tell the user the output path so they can file it back into the wiki if useful

Format: clean markdown, suitable for filing back into the wiki as an outputs/ document.

## Vault location

Read vault path from `~/.config/wiki/config.toml` → `vault.path`.
