# Party Name Insertion into Document Details

Party insertion into doc details is handled deterministically — we scan the template text for four categories of markers and swap them with the computed party name phrase:

1. **Personal pronouns** — the words `"your"` and `"you"` as standalone terms in the text. The first occurrence of each is replaced with the party name phrase.

2. **Named person placeholders** — `[Name]`, `[INSERT NAME]`, `enter name of person`, `<INSERT NAME>`, and `<INSERT WITNESS>`. These are template-level tokens explicitly marking where a person's name belongs. First match gets replaced.

3. **Alternative construct** — `"your/enter name of person's"` where the template offers both a pronoun and a placeholder as `/`-separated options. This is matched and replaced as a single atomic unit, preventing the two halves from being independently swapped and producing redundant output like `"Merc's/Merc's"`.

4. **Impersonal fallback** — when no personal pronoun or person placeholder exists anywhere in the text, we check if the doc starts with `"A copy of "`. If it does, the party name phrase is inserted right after that prefix. If it doesn't, the text is left unchanged — no person to attribute to.
