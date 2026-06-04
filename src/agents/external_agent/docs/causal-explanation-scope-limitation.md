# Causal Explanation Rule — Scope Limitation

## The Case

**Investigation type**: Policy Exclusion | Intentional or Deliberate Acts

**Insured's narrative**: *"I hit a pole as my son has been suffering mental health and something triggered him as he was upset I then drove into a light pole"*

The insured admits deliberately driving into the pole but cites her son's mental health episode as the trigger.

## What Happened

The narrative doc prompt has a **Causal Explanation** rule that says: when the narrative gives a reason (Y) for a circumstance (X) — and Y makes the difference between the incident happening or not — derive a document to verify Y. Example: *"the car was on the street because we were doing pest control in the garage"* → pest control invoice is mandatory. No pest control → car in garage → no incident. This rule works well in Staged Accident cases.

But applied to THIS case:

1. **Y = son's mental health episode**. The LLM determines this is the causal explanation.
2. **Party Scope blocks it**. The son is not a direct party to the claim — we don't request third-party records.
3. **The LLM pivots**. Instead of stopping, it reinterprets Y as **the insured's own mental health** and requests her mental health treatment records.

Three iterations of rule changes failed to stop the pivot — removing "MUST derive," adding "do not reinterpret Y," restructuring as sequential gates, removing case-specific counter-examples. Each time the LLM found a path to produce mental health records for the insured:

| Iteration | Failed Output |
|-----------|--------------|
| 1 (original) | Son's mental health treatment records |
| 2 (Party Scope tightened to block non-party records) | Insured's mental health treatment records — LLM pivoted from son to insured |
| 3 (Causal Explanation: "do not reinterpret Y, move on") | Still insured's mental health records |

## Root Cause

The Causal Explanation rule was designed for **objective, verifiable causes** (employment records, service invoices, booking records). It was not designed for psychological or emotional explanations where the "cause" is a mental state description. The LLM conflates "the narrative mentions mental health → medical records must exist → I should request them." The rule's litmus test (*"would the incident have occurred without Y?"*) creates a mandate the LLM will not let go of — if it cannot request the son's records, it requests the insured's.

## Fix Applied

### 1. Party Scope tightened

The original Party Scope rule only prevented requesting documents **from** non-parties. It did not prevent requesting records **about** non-parties from a direct party.

**Changed from**: *"Only request documents from parties directly involved in the current claim."*

**Changed to**: *"Only request documents that belong to or are about parties directly involved in the current claim. Do not request records of persons who are not direct parties to the claim (e.g., family members, witnesses, third parties) — even when the request is addressed to a direct party."*

### 2. Causal Explanation scope gate

Added an upfront scope exclusion to the Causal Explanation rule:

> This rule applies ONLY to objective, concrete causes — work arrangements, service bookings, physical circumstances, logistics, business records. It does NOT apply to psychological or emotional explanations (e.g., mental state, emotional distress, mental health episode being the stated reason). For such explanations, produce NO output.

This prevents the LLM from entering the litmus test at all when the cause is psychological or emotional.

## Related Changes

- **Party Scope** cross-referenced inside Causal Explanation so gates are not applied in isolation
- Causal Explanation restructured as sequential gates (no "MUST derive")

## Result

After applying both changes, the narrative doc prompt for this case now correctly produces **no documents** — the Causal Explanation rule is blocked at the scope gate before the litmus test ever fires, and no mental health records are derived for any party.

No mental health records. No son. No insured. Output is empty as intended.
