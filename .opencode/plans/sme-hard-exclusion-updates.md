# SME Hard Exclusion Updates

Apply 4 prompt-only changes to `DOC_REQUEST_RELEVANCE_PROMPT` in `external_agent_prompts.py`. No code hook changes.

## File
`src/agents/external_agent/prompt_manager/external_agent_prompts.py`

## Changes

### Edit 1 — Hard Excl #1, Work rosters (line 143)
**Old:**
```
1. Work rosters, timesheets, or employment records: INCLUDE ONLY if the incident was employment-related (occurred during work hours, at a workplace, or attendance/timing is explicitly questioned in case facts).
```
**New:**
```
1. Work rosters, timesheets, or employment records: INCLUDE ONLY if the incident was employment-related (occurred during work hours, at a workplace, including coming from or going to work, or attendance/timing is explicitly questioned in case facts).
```

### Edit 2 — Hard Excl #2, Insurance claims history (line 144)
**Old:**
```
2. Insurance claims history: INCLUDE ONLY if INITIAL REVIEW explicitly records prior claims for the INSURED. Prior policies, inactive policies, or third-party claims are NOT the insured's prior claims.
```
**New:**
```
2. Insurance claims history: INCLUDE ONLY if INITIAL REVIEW or ADDITIONAL INFORMATION explicitly records prior claims for the INSURED with a non-Suncorp (external) insurer. If no mention of claims outside Suncorp exists, assume no external prior claims and exclude. Prior policies, inactive policies, or third-party claims are NOT the insured's prior claims.
```

### Edit 3 — Hard Excl #3, Criminal history (line 145)
**Old:**
```
     3. Criminal history or background checks: INCLUDE ONLY if INITIAL REVIEW or ADDITIONAL INFORMATION alleges a criminal element, prior offending, or law enforcement involvement beyond the current incident for a party directly involved in this claim, OR mentions court listings or criminal concerns for a party directly involved in this claim.
```
**New:**
```
    3. Criminal history or background checks: INCLUDE ONLY if INITIAL REVIEW or ADDITIONAL INFORMATION alleges a criminal element, prior offending, or law enforcement involvement beyond the current incident for a party directly involved in this claim, OR mentions court listings or criminal concerns for a party directly involved in this claim. Exclude criminal history for third parties — they are not direct parties to the claim.
```

### Edit 4 — Hard Excl #6, Tenancy/rental (line 148)
**Old:**
```
6. Tenancy/rental documents: INCLUDE ONLY when the party is a tenant. Exclude for owner-occupiers.
```
**New:**
```
6. Tenancy/rental documents: INCLUDE ONLY when the party is a tenant OR the insured holds a landlord policy (renting the property to others). Exclude for owner-occupiers.
```
