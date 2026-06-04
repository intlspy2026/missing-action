# Narrative Document Derivation — Mental Health Records Issue

## The Case

**Investigation type**: Policy Exclusion | Intentional or Deliberate Acts

**Insured's narrative**: *"I hit a pole as my son has been suffering mental health and something triggered him as he was upset I then drove into a light pole"*

The insured admits deliberately driving into the pole but cites her son's mental health episode as the trigger.

## What Happened

The system has logic to derive document requests from the claimant's narrative. When the narrative explains why the incident occurred (e.g., *"the car was on the street because we were doing pest control in the garage"*), it correctly requests the pest control invoice to verify the explanation. This works well for objective causes like work arrangements, service bookings, and physical circumstances.

But applied to THIS case:

1. **Y = son's mental health episode**. The system identifies this as the reason the incident occurred.
2. **Blocked — son is not a party to the claim**. The system should not request documents from or about non-parties (like family members, witnesses).
3. **The system pivots**. Instead of stopping, it reinterprets the cause as **the insured's own mental health** and requests her mental health treatment records.

Three iterations of fixes failed to stop the pivot. Each time the system found a way to produce mental health records for the insured:

| Iteration | What was fixed | System output |
|-----------|---------------|--------------|
| 1 (original) | — | Son's mental health treatment records |
| 2 | Tightened scope so documents must be about a direct party | **Insured's** mental health records — system pivoted from son to insured |
| 3 | Told system not to reinterpret the blocked cause | Still insured's mental health records |

## Root Cause

The document derivation logic was designed for **objective, verifiable causes** — employment records, service invoices, booking records. It was not designed for psychological or emotional explanations where the "cause" is a mental state description. The system sees "mental health mentioned in the narrative" and concludes "medical records must exist → I should request them." It will not let go of this, even when blocked from the correct target.

## Fix Applied

### 1. Request scope tightened

Previously, the system only prevented requesting documents **from** non-parties. It did not prevent requesting records **about** non-parties from a direct party.

**Now**: the system will only request documents that belong to or are about parties directly involved in the claim. It will not request records of non-parties (family members, witnesses, third parties) — even when the request is addressed to the insured.

### 2. Narrative explanation logic limited to objective causes

The logic that derives documents from narrative explanations now applies **only to objective, concrete causes** — work arrangements, service bookings, physical circumstances, logistics, business records. It no longer applies to psychological or emotional explanations (mental state, emotional distress, mental health episodes). For such explanations, no documents are derived.

## Result

After applying both changes, this case now correctly produces **no document requests** from the narrative. The system no longer requests mental health records for the insured, her son, or any other party. Output is empty as intended.
