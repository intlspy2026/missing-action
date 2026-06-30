# How `parse_form_to_doc_request` works

A walkthrough of the doc-request parser in `agents/external_agent/utils.py`, end-to-end with a concrete payload. The same logic applies to `parse_form_to_key_concerns` (rationale ↔ concern) and `parse_form_to_enquiries` (enquiry_detail ↔ enquiry) — only the field names change.

## Step 1: What BE has before sending the form

`previous` is the last-known `DocRequestSet`, e.g.:

```python
previous = DocRequestSet(
    document_set=[
        DocRequest(doc_type="Police Report",  doc_details="Need police report from local station for incident on 2026-04-01"),
        DocRequest(doc_type="Medical Records", doc_details="Hospital admission notes from City Hospital"),
        DocRequest(doc_type="Engineer Report", doc_details="Vehicle damage assessment from approved engineer"),
    ],
    version=2,
    update_notes=None,
)
```

## Step 2: What `build_form_doc_request(previous)` ships to FE

One textarea per item. `label` carries the topic, `default_value` the detail. The topic is *not* a form field — it's a static label.

```python
[
    {"type": "textarea", "id": "doc_details_1", "label": "Police Report",   "default_value": "Need police report from local station ..."},
    {"type": "textarea", "id": "doc_details_2", "label": "Medical Records", "default_value": "Hospital admission notes ..."},
    {"type": "textarea", "id": "doc_details_3", "label": "Engineer Report", "default_value": "Vehicle damage assessment ..."},
]
```

## Step 3: User edits item 2 on the RHS, submits

FE serialises the form as a flat dict — keys are component IDs, values are the textarea contents. The labels are *not* sent because they were never form fields:

```python
form_payload = {
    "doc_details_1": "Need police report from local station for incident on 2026-04-01",
    "doc_details_2": "Hospital admission notes AND discharge summary from City Hospital",   # ← edited
    "doc_details_3": "Vehicle damage assessment from approved engineer",
}
```

This is the `form_payload` the parser receives, along with `previous` (same as Step 1).

## Step 4: Parser walkthrough

```python
def parse_form_to_doc_request(form_payload, *, previous=None):
    doc_details: Dict[int, str] = {}
    for k, v in (form_payload or {}).items():
        m = re.fullmatch(r"doc_details_(\d+)", str(k))
        if m:
            doc_details[int(m.group(1))] = (v or "").strip()
    ...
```

After the loop:

```python
doc_details = {
    1: "Need police report from local station for incident on 2026-04-01",
    2: "Hospital admission notes AND discharge summary from City Hospital",
    3: "Vehicle damage assessment from approved engineer",
}
```

The regex `r"doc_details_(\d+)"` with `fullmatch` anchors both ends, so `doc_details_2` matches and captures `2`. Anything else in `form_payload` (e.g. unrelated form keys) is ignored.

```python
prev_items = list(previous.document_set)   # 3 items, ordered as built
items: List[DocRequest] = []

for idx in sorted(doc_details):            # [1, 2, 3]
    if idx - 1 >= len(prev_items):
        continue
    doc_type_text   = prev_items[idx - 1].doc_type      # ← recovered from previous by position
    doc_details_text = doc_details[idx]                  # ← from form payload
    if doc_type_text:
        items.append(DocRequest(doc_type=doc_type_text, doc_details=doc_details_text))
```

Iteration trace:

| `idx` | `prev_items[idx-1].doc_type` | `doc_details[idx]` | Appended |
|---|---|---|---|
| 1 | `"Police Report"`   | `"Need police report ..."`              | ✓ unchanged |
| 2 | `"Medical Records"` | `"Hospital admission notes AND ..."`    | ✓ user edit captured |
| 3 | `"Engineer Report"` | `"Vehicle damage assessment ..."`       | ✓ unchanged |

## Step 5: Result

```python
DocRequestSet(
    document_set=[
        DocRequest(doc_type="Police Report",  doc_details="Need police report ..."),
        DocRequest(doc_type="Medical Records", doc_details="Hospital admission notes AND discharge summary from City Hospital"),
        DocRequest(doc_type="Engineer Report", doc_details="Vehicle damage assessment ..."),
    ],
    version=3,           # bumped from previous.version (2) + 1
    update_notes=None,
)
```

## The key invariant

The parser relies on **positional alignment between `form_payload` keys and `previous.document_set`**:

- Builder emits `doc_details_{idx}` where `idx = enumerate(previous.document_set, start=1)`.
- Parser reads `prev_items[idx - 1]` to recover `doc_type`.

This invariant holds **as long as the form payload and `previous` correspond to the same render**. That's true for direct RHS edits (which is the only path that calls this parser). Add / delete / regenerate flows go through the chat → LLM regeneration path, which produces a new `DocRequestSet` and a new form — the parser is never asked to reconcile a payload against a stale `previous`.

## Edge cases worth noting

| Situation | Behaviour |
|---|---|
| User clears a textarea (`""`) | Item still appended with empty `doc_details`. Existing `doc_type` retained. If you want clearing to drop the row, add a guard. |
| `form_payload` contains an `idx` beyond `len(prev_items)` | Skipped via `if idx - 1 >= len(prev_items): continue`. Defensive — shouldn't normally occur. |
| `previous=None` | `prev_items=[]`, every iteration skips, returns empty `DocRequestSet`. The parser cannot reconstruct topics without `previous`, so callers must always pass it. |
| Index gap (e.g. only `doc_details_1` and `doc_details_3` arrive) | `idx=2` is simply absent; iteration covers only the present indices. Any item at `prev_items[1]` is silently dropped. Worth flagging if FE could ever omit fields, since the corresponding doc would vanish from the result. |
