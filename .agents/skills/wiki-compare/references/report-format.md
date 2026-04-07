# Report Format

The wiki-compare skill produces a report in this structure. Use this as the
exact output template.

---

## Wiki Compare Report — `<document filename>`

**Related wiki articles loaded:** `article-a.md`, `article-b.md`, ...

---

### Conflicts

Issues where the wiki and the document say different things.

> **[article-name.md § Section]**
> "Quoted or paraphrased wiki statement"
>
> **[Document § Heading or line ~N]**
> "Quoted or paraphrased document statement"
>
> **Conflict:** One sentence describing the contradiction.

*(Repeat for each conflict. If none: "None found.")*

---

### Wiki Gaps

Things the document covers that the wiki does not mention.

- **Topic**: one-sentence description of what is missing and which article
  should receive it.

*(If none: "None found.")*

---

### Document Issues

Wiki knowledge the document appears to be unaware of or contradicts where the
wiki is likely authoritative.

- **Topic**: what the wiki says vs. what the document says or omits, and why
  this matters.

*(If none: "None found.")*

---

### Cross-link Opportunities

- `article-x.md` ↔ `article-y.md`: one-sentence reason the link adds value.

*(If none: "None found.")*

---

### Proposed Wiki Updates

| # | Article | Change |
|---|---------|--------|
| 1 | `article-a.md` | Add section "X" covering ... |
| 2 | `article-b.md` | Correct value Y from ... to ... |

*Awaiting approval before making changes.*
