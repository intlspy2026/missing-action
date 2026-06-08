# External Agent — Party Assignment Feature Spec

## Overview

Adds party assignment chips to each document in the Document Requests section. Users select which parties each document applies to, then click "Preview update" on the LHS to inject proper party names into the document wording. The backend applies English grammar rules for possessive forms.

---

## Files Changed

| File | Type |
|------|------|
| `agents/external_agent/schemas.py` | Schema — added `assigned_parties` to `DocRequest`, `"preview_update"` to `HITLDecision` intent |
| `agents/external_agent/utils.py` | 6 new functions, 2 modified — core logic |
| `agents/external_agent/prompt_manager/external_agent_prompts.py` | 1 new prompt — LLM-based fallback |
| `agents/external_agent/external_agent_graph.py` | 4 changes — flow integration |

---

## New/Modified Functions

### utils.py

| Function | Line | Purpose |
|----------|------|---------|
| `_to_title_case()` | 16 | Helper — `"insured_name"` → `"Insured Name"` |
| `build_chips_from_insured_details()` | 20 | Generates `info_chipbox` data from non-empty `insured_details` |
| `build_quick_action_preview_update()` | 36 | Returns quick_action artifact for LHS button |
| `categorise_parties()` | 48 | Buckets chip keys into `insured_names`, `driver_names`, `other_names` |
| `build_party_possessive_phrase()` | 84 | Grammar engine — generates English possessive phrase |
| `apply_party_names_to_doc_details()` | 121 | Post-processes doc_details to insert party names |
| `build_form_doc_request()` | 435 | **Modified** — accepts `insured_details`, adds chips |
| `parse_form_to_doc_request()` | 638 | **Modified** — extracts `doc_{N}_chips` from form payload |

### external_agent_graph.py

| Location | Line | Purpose |
|----------|------|---------|
| Imports | 20, 42 | Added `PARTY_NAME_INSERTION_PROMPT`, `build_quick_action_preview_update`, `apply_party_names_to_doc_details` |
| `route_interrupt()` | 950 | Moved `step_to_state_key` to top; added preview_update detection at line 977 |
| `_resolve_hitl_artifact()` | 366 | Added `"preview_update"` to intent parse check |
| `generate_doc_request_async()` | 1291 | Added preview_update handling; artifact now includes quick_action + chips |

### schemas.py

| Change | Line |
|--------|------|
| `DocRequest.assigned_parties: Optional[List[str]] = None` | 61 |
| `HITLDecision.intent` — added `"preview_update"` | 120 |

---

## Complete Flow

### Phase A — Initial Form Rendering (first time user sees doc requests)

```
1. generate_doc_request_async()                    graph.py:1270
   │
   ├─ LLM pipeline runs (draft or feedback path)   graph.py:1353-1539
   │  └─ parsed = DocRequestSet(document_set=[...]) graph.py:1533
   │
   ├─ insured_details = state.get("insured_details") graph.py:1538
   │
   ├─ BUILD THE FORM ────────────────────────────────────────
   │  artifact = build_form_doc_request(parsed, insured_details)  graph.py:1540
   │  │
   │  │  Inside build_form_doc_request()             utils.py:435
   │  │  ├─ chip_data = build_chips_from_insured_details(insured_details)  utils.py:442
   │  │  │  └─ Iterates non-empty keys → [{label, value, description}]     utils.py:20-33
   │  │  │
   │  │  └─ For each doc, appends info_chipbox:       utils.py:459-471
   │  │     └─ defaultValue = dr.assigned_parties     (currently None — no prior selection)
   │  │
   │  └─ Returns [workflow_stage artifact]
   │
   ├─ ADD QUICK ACTION BUTTON ──────────────────────────────
   │  artifact.append(build_quick_action_preview_update())  graph.py:1541-1542
   │  │
   │  │  Inside build_quick_action_preview_update():  utils.py:36-45
   │  │  └─ Returns {type:"quick_action", data:[{label:"Preview update", prompt:"..."}]}
   │  │
   │  └─ artifact = [workflow_stage, quick_action]
   │
   ├─ prepare_hitl_task(..., artifact=artifact)       graph.py:1544-1551
   │  └─ Wraps into Content object for frontend
   │
   └─ Command(goto="route_interrupt", ...)            graph.py:1565
         │
         ▼
2. route_interrupt()                                  graph.py:946
   └─ interrupt(hitl_task)                            graph.py:966
      └─ PAUSED. Frontend renders:
         RHS: doc form with chips ← from workflow_stage
         LHS: "Preview update" button ← from quick_action
```

---

### Phase B — User Selects Chips + Clicks "Preview Update"

```
3. route_interrupt() RESUMES                           graph.py:968
   │
   ├─ hitl_text = "Preview update document requests with assigned parties"  graph.py:969
   │
   ├─ DETECT PREVIEW UPDATE                            graph.py:977
   │  if "preview update" in hitl_text.lower() and pending_step == "doc_request_review":
   │
   ├─ hitl_decision = HITLDecision(intent="preview_update", ...)  graph.py:978
   │
   ├─ PARSE CHIP SELECTIONS FROM FORM DATA ─────────────────
   │  _resolve_hitl_artifact(state, pending_step, incoming_artifact, intent="preview_update")  graph.py:979
   │  │
   │  │  Inside _resolve_hitl_artifact()               graph.py:342
   │  │  ├─ intent in ("accept", "feedback", "preview_update")   graph.py:366  ✓ matches
   │  │  │
   │  │  └─ parser_fn(incoming_artifact, previous=previous)      graph.py:368
   │  │     │
   │  │     │  Inside parse_form_to_doc_request()       utils.py:638
   │  │     │  ├─ regex matches "doc_(\d+)_chips"       utils.py:655-660
   │  │     │  │  e.g. form payload has doc_1_chips: ["insured_name", "driver_name"]
   │  │     │  │       → doc_chips[1] = ["insured_name", "driver_name"]
   │  │     │  │
   │  │     │  ├─ Carries forward prev.assigned_parties if no chips  utils.py:675-677
   │  │     │  │
   │  │     │  └─ Creates DocRequest(assigned_parties=["insured_name", "driver_name"])  utils.py:680-684
   │  │     │
   │  │     └─ Returns DocRequestSet with assigned_parties populated
   │  │
   │  └─ canonical_update["doc_request"] = hitl_artifact   graph.py:982-986
   │
   └─ Command(goto="generate_doc_request", update={doc_request: parsed, ...})  graph.py:988-998
         │
         ▼
4. generate_doc_request_async() CALLED AGAIN           graph.py:1270
   │
   ├─ decision.intent == "preview_update"              graph.py:1291  ✓
   │
   ├─ insured_details = state.get("insured_details")   graph.py:1292
   ├─ insured_type = state.get("insured_type")         graph.py:1293
   ├─ doc_request = state.get("doc_request")           graph.py:1294
   │  └─ Now has assigned_parties populated from step 3
   │
   ├─ FOR EACH DOCUMENT ─────────────────────────────────────
   │  for dr in doc_request.document_set:              graph.py:1301
   │  │  assigned_keys = dr.assigned_parties           graph.py:1302
   │  │  e.g. ["insured_name", "driver_name"]
   │  │
   │  ├─ if assigned_keys:                             graph.py:1303
   │  │
   │  │  CALL THE POST-PROCESSING ENGINE ────────────────────
   │  │  apply_party_names_to_doc_details(             graph.py:1304-1309
   │  │      dr.doc_details,                          e.g. "A copy of your Work Roster/Timesheet..."
   │  │      assigned_keys,                           e.g. ["insured_name", "driver_name"]
   │  │      insured_details,                         e.g. {"insured_name":"John Smith", "driver_name":"Jane Doe"}
   │  │      insured_type                             e.g. None (individual)
   │  │  )
   │  │  │
   │  │  │  Inside apply_party_names_to_doc_details()   utils.py:121
   │  │  │  │
   │  │  │  ├─ categorise_parties(assigned_keys, ...)   utils.py:130
   │  │  │  │  │
   │  │  │  │  │  Inside categorise_parties()            utils.py:48
   │  │  │  │  │  ├─ individual path (not business)
   │  │  │  │  │  ├─ "insured_name" → key_lower contains "insured"
   │  │  │  │  │  │  → insured_names.insert(0, "John Smith")     utils.py:77
   │  │  │  │  │  ├─ "driver_name" → key_lower contains "driver"
   │  │  │  │  │  │  → driver_names.append("Jane Doe")            utils.py:73
   │  │  │  │  │  └─ Returns (["John Smith"], ["Jane Doe"], [])
   │  │  │  │
   │  │  │  ├─ build_party_possessive_phrase(          utils.py:134
   │  │  │  │   insured_names=["John Smith"],
   │  │  │  │   driver_names=["Jane Doe"],
   │  │  │  │   other_names=[],
   │  │  │  │   insured_type=None
   │  │  │  │  )
   │  │  │  │  │
   │  │  │  │  │  Inside build_party_possessive_phrase()  utils.py:84
   │  │  │  │  │  ├─ is_business = False
   │  │  │  │  │  ├─ Not branch B (len==1 && no driver && no other)
   │  │  │  │  │  │  → doesn't return "your"
   │  │  │  │  │  ├─ Branch D: insured_names=1 → parts.append("your")   utils.py:103
   │  │  │  │  │  ├─ driver_names → parts.append("Jane Doe's")          utils.py:108
   │  │  │  │  │  ├─ parts = ["your", "Jane Doe's"]
   │  │  │  │  │  ├─ len(parts) == 2
   │  │  │  │  │  └─ Returns "your and Jane Doe's"                      utils.py:117
   │  │  │  │
   │  │  │  ├─ phrase = "your and Jane Doe's"          utils.py:134-136
   │  │  │  │
   │  │  │  ├─ has_personal_ref = True                 utils.py:143-147
   │  │  │  │  (doc_details contains "\byour\b")
   │  │  │  │
   │  │  │  ├─ is_business = False → else branch       utils.py:169
   │  │  │  ├─ phrase != "your" → don't return early   utils.py:170
   │  │  │  │
   │  │  │  ├─ re.sub(r"\byour\b", "your and Jane Doe's", doc_details, count=1)  utils.py:174
   │  │  │  │  "A copy of your Work Roster/Timesheet..."
   │  │  │  │  →
   │  │  │  │  "A copy of your and Jane Doe's Work Roster/Timesheet..."
   │  │  │  │  (later "your"s like "your Manager" stay untouched)
   │  │  │  │
   │  │  │  └─ Returns modified doc_details text        utils.py:181
   │  │  │
   │  │  └─ updated_docs.append(DocRequest(             graph.py:1310-1314
   │  │       doc_type=...,
   │  │       doc_details="A copy of your and Jane Doe's Work Roster...",
   │  │       assigned_parties=["insured_name", "driver_name"]
   │  │     ))
   │  │
   │  └─ ELSE (no chips selected for this doc):        graph.py:1315-1316
   │     └─ updated_docs.append(dr)  ← unchanged
   │
   ├─ parsed = DocRequestSet(document_set=updated_docs) graph.py:1318-1321
   │
   ├─ RE-RENDER FORM WITH UPDATED WORDING ──────────────────
   │  artifact = build_form_doc_request(parsed, insured_details) graph.py:1327
   │  │  └─ Now doc_details has party names baked in
   │  │  └─ defaultValue = dr.assigned_parties (preserves chip state)
   │  │
   │  artifact.append(build_quick_action_preview_update())       graph.py:1329
   │  │  └─ Button for another round of edits
   │  │
   │  prepare_hitl_task(..., artifact=artifact)                  graph.py:1332-1339
   │
   └─ Command(goto="route_interrupt", update={...})              graph.py:1341-1351
         │
         ▼
5. route_interrupt() → interrupt() → PAUSED
   Frontend shows:
   RHS: "A copy of your and Jane Doe's Work Roster/Timesheet..." ← updated text
   LHS: "Preview update" button ← for another round
   User can also accept or provide feedback
```

---

### Phase C — User Accepts

```
6. route_interrupt() resumes                            graph.py:968
   ├─ hitl_text is empty, incoming_artifact has form data
   ├─ No "preview update" in hitl_text → falls through  graph.py:977
   │
   ├─ _classify_hitl(...)                               graph.py:1002
   │  └─ artifact present, no text → intent="accept"
   │
   ├─ _resolve_hitl_artifact(..., intent="accept")      graph.py:1003
   │  └─ parse_form_to_doc_request() → extracts final chip+detail state
   │
   └─ Command(goto="generate_doc_request", update={...}) graph.py:1070-1080
         │
         ▼
7. generate_doc_request_async()                          graph.py:1270
   ├─ decision.intent == "accept"                       graph.py:1278
   └─ goto = _next_section("doc_request", selected_sections)  graph.py:1279
      └─ Moves to next section (additional_enquiries or assemble_plan)
```

---

## How Each Function Gets Called

```
build_quick_action_preview_update()
  ├── called at RENDER TIME (not click time)
  ├── graph.py:1542  ← initial form rendering
  └── graph.py:1329  ← after preview update re-render

build_chips_from_insured_details()
  └── utils.py:442  ← inside build_form_doc_request, at render time

categorise_parties()
  └── utils.py:130  ← inside apply_party_names_to_doc_details

build_party_possessive_phrase()
  └── utils.py:134  ← inside apply_party_names_to_doc_details

apply_party_names_to_doc_details()
  └── graph.py:1304  ← inside generate_doc_request_async, preview_update path

parse_form_to_doc_request() (modified)
  ├── graph.py:368   ← _resolve_hitl_artifact, on preview_update/accept/feedback
  └── graph.py:1003  ← _resolve_hitl_artifact, on accept
```

---

## Grammar Rules

| Scenario | Example Output |
|----------|---------------|
| 1 Insured only | `"your"` |
| 1 Insured + 1 Driver | `"your and Jane Doe's"` |
| 1 Insured + 2 others | `"your, Bob Brown's, and Alice Green's"` |
| 2+ Insured | `"John Smith's and Mary Smith's"` |
| 2+ Insured + 1 other | `"John Smith's, Mary Smith's, and Bob Brown's"` |
| Driver only (no insured assigned) | `"Jane Doe's"` |
| Business insured | `"Acme Corp's"` (never `"your"`) |
| Business + director | `"Acme Corp's and John Smith's"` |
| No chips selected | Unchanged |

---

## Edge Cases

- **No insured_details in state**: chips not rendered, quick action not shown
- **No chips selected for a document**: doc_details stays unchanged
- **Document has no "your" or "A copy of" pattern**: doc_details stays unchanged
- **Business insured**: `"your"` → business name, `"you"` → business name
- **Only first "your" replaced**: later `"your"` references (e.g. "your Manager") stay as-is
- **Chip selections persist**: `parse_form_to_doc_request` carries forward previous `assigned_parties`
- **LLM fallback exists**: `PARTY_NAME_INSERTION_PROMPT` is available for future AI-based insertion
