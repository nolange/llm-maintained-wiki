# /wiki-compare

Compare an external document against the wiki to find conflicts, gaps, and sync opportunities.

## Usage

```
/wiki-compare <path-to-document>
```

`$ARGUMENTS` is the path to the document to compare (any format: `.adoc`, `.md`, `.txt`, `.pdf`).

---

## Steps

### 1. Load wiki knowledge

Read `wiki/_index`. For each entry parse the tab-separated line: `relative-path<TAB>tags<TAB>title`.
Build a map: `stem → {path, tags, title}`.

### 2. Read the target document

Read `$ARGUMENTS`. If it is a binary format (PDF, docx) use the appropriate extraction tool (`pdftotext`, `pandoc`) to get plain text.

Identify the document's main topics by scanning headings, section titles, key terms, and any explicit tags or labels.

### 3. Find related wiki articles

Match the document's topics against wiki article tags and titles. Cast wide: include any article whose tags overlap with the document's topic area, plus any article whose title contains a key term from the document.

Read the **full body** of every matched article.

### 4. Cross-compare

For each matched article, compare its content against the corresponding section(s) in the document. Produce a structured report:

#### Conflicts
Statements where the two sources contradict each other — different values, opposite procedures, incompatible constraints. For each conflict:
- Quote the relevant passage from the wiki (file + approximate section)
- Quote the relevant passage from the document
- State the nature of the conflict clearly

#### Wiki gaps
Facts, decisions, or constraints present in the document that are **not** covered anywhere in the matched wiki articles. These are candidates for adding to the wiki.

#### Document gaps
Facts or context present in the wiki that the document appears to ignore or be unaware of. Flag these as potential issues in the external document.

#### Cross-links
Wiki articles that are closely related to the document's content but not yet cross-linked to each other.

### 5. Propose actions

After presenting the report, propose concrete actions:

- **Wiki updates**: for each wiki gap or conflict where the document is likely authoritative, state exactly which article to update and what to add or correct.
- **Document issues**: for each document gap or conflict where the wiki is likely authoritative, flag the discrepancy so the user can decide whether to update the external document.

Ask the user which actions to take. Then execute the approved wiki updates directly — read the article, make the targeted change, and write it back. Do not rewrite content that is not affected.

After updating, mention any `_index` tag changes needed.

---

## Hard rules

- Do not invent facts. Only draw conclusions from what the documents actually say.
- Do not rewrite wiki articles wholesale — make surgical, targeted changes.
- If the document is ambiguous or the wiki is ambiguous, say so rather than guessing.
- Do not update the external document unless the user explicitly asks.
- After any wiki update, check whether `wiki/_index` tags for the updated article need updating.
