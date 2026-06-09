# Broken English After Party Insertion

Templates from `standards.py` whose wording causes grammatically broken output after the party insertion feature runs. All affected docs use the `"A copy of"` prepend fallback — the possessive phrase gets inserted before a determiner (`the`, `any`, `all`), producing `"A copy of Merc's the/any/all..."`.

---

## Motor — 15 broken

| # | Doc Type | Broken output (example with `Merc's`) |
|---|----------|---------------------------------------|
| 1 | Purchase Documents | `"A copy of Merc's the purchase documents..."` |
| 2 | Service and Maintenance History | `"A copy of Merc's the service and maintenance history..."` |
| 3 | Roadworthy Documents | `"A copy of Merc's the roadworthy certificate..."` |
| 4 | Toll Statements | `"A copy of Merc's the subject vehicle toll account statements..."` |
| 5 | Photographs of Incident Scene | `"A copy of Merc's any photographs taken at the incident scene..."` |
| 6 | Claims/Insurance History | `"A copy of Merc's any documents relating to prior insurance/claims..."` |
| 7 | CCTV Footage | `"A copy of Merc's any CCTV footage..."` |
| 8 | Medical Records | `"A copy of Merc's all medical records..."` |
| 9 | Prior Insurance Documents | `"A copy of Merc's any documents for prior insurance..."` |
| 10 | Rideshare Receipts | `"A copy of Merc's any rideshare receipts..."` |
| 11 | Email/Text Message Correspondence | `"A copy of Merc's any correspondence confirming..."` |
| 12 | Motor Sport/Racetrack Evidence | `"A copy of Merc's any information regarding..."` |
| 13 | Towing Records | `"A copy of Merc's any towing records..."` |
| 14 | Vehicle Agreement/Contracts | `"A copy of Merc's any relevant agreements..."` |
| 15 | Financial Statements (Business) | `"...businesses that Merc's/insert name hold directorships..."` *(business insured only)* |

---

## Property — 22 broken

| # | Doc Type | Broken output (example with `Merc's`) |
|---|----------|---------------------------------------|
| 1 | Photographs of Damage Post-Event | `"A copy of Merc's any photographs taken post the damage-event..."` |
| 2 | Claims/Insurance History | `"A copy of Merc's any documents relating to prior insurance/claims..."` |
| 3 | CCTV Footage | `"A copy of Merc's any CCTV footage..."` |
| 4 | Fire Report | `"A copy of Merc's the Fire Report..."` |
| 5 | Prior Insurance Documents | `"A copy of Merc's any documents for prior insurance..."` |
| 6 | Tenancy Agreements | `"A copy of Merc's the tenancy agreement..."` |
| 7 | Inspection Reports | `"A copy of Merc's the pre-purchase or pre-existing inspection reports..."` |
| 8 | Service, Maintenance and/or Repair Reports | `"A copy of Merc's any receipts, invoices, reports..."` |
| 9 | Contract of Sale | `"A copy of Merc's the complete and signed final copy of the contract of sale..."` |
| 10 | Rideshare Receipts | `"A copy of Merc's any rideshare receipts..."` |
| 11 | Mobile Phone Related Documents | `"A copy of Merc's the IDs, serial numbers, IMEI numbers."` |
| 12 | Email/Text Message Correspondence | `"A copy of Merc's any correspondence confirming..."` |
| 13 | Property Manager Correspondence | `"A copy of Merc's any correspondence from the property manager..."` |
| 14 | Council Correspondence | `"A copy of Merc's any correspondence from the council..."` |
| 15 | Tenant Correspondence | `"A copy of Merc's any correspondence from the tenant..."` |
| 16 | Development Application | `"A copy of Merc's any paperwork in relation to the development..."` |
| 17 | Condition Report | `"A copy of Merc's the <ENTRY/EXIT> report..."` |
| 18 | Leak Detection Report | `"A copy of Merc's any plumbers/leak detection report..."` |
| 19 | Business Records | `"A copy of Merc's the relevant business records..."` |
| 20 | Business Insurance Records | `"A copy of Merc's any business insurance documents..."` |
| 21 | Booking Schedules | `"A copy of Merc's any booking schedules..."` |
| 22 | Financial Statements (Business) | `"...businesses that Merc's/insert name hold directorships..."` *(business insured only)* |

---

**Total: 37 broken (15 Motor + 22 Property).**

**Root cause:** The `"A copy of"` prepend inserts the possessive phrase before a determiner (`the`, `any`, `all`), producing ungrammatical output. The two Financial Statements (Business) entries have the separate issue of `"/insert name"` being left behind when `"you"` is replaced for business insured type.
