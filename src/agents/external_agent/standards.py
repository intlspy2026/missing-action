"""
SME-authored quality standards injected into section prompts.

Each constant pair is:
- `<SECTION>_GOLD_STANDARDS` — raw SME content, dropped inside a wrapper tag in
  the draft prompt (the tag is already in the prompt template).
- `<SECTION>_GOLD_STANDARDS_BLOCK` — same content pre-wrapped in tags, intended
  for the SECTION_FEEDBACK_PROMPT slot which uses an include-or-omit pattern.

To update the gold standards, edit the raw constant only; the block constant is
derived automatically.
"""

DOC_REQUEST_GOLD_STANDARDS = """
MOTOR DOCUMENT STANDARDS
- Purchase Documents: A copy of the purchase documents for the subject vehicle - purchase contract /invoice or purchase receipt and contact details of the previous owner (if private sale).
- Registration Certificate: A copy of the registration certificate for the subject vehicle, current at the date of loss - if you cannot locate a copy, this can be obtained from your relevant transport department.
- Telephone Records: Fully itemised telephone call and text records for XXXXXXXXXX and all numbers held in your or joint names, or which you had access to for the period XXX to XXX. This should be in the original, non-editable format provided by your telephone service provider. If the document is provided in a excel spreadsheet, which is able to be edited/modified we are unable to accept this document. For the dates XXXX, please fully itemise all calls and texts made listing the party contacted and reason for the call or text. If you encounter difficulties with your telephone service providers to obtain the above information, please contact the Telecommunications Industry Ombudsman on 1800 062 058 or https://www.tioonline.com.au/consumers/new/.
- Finance Documents: A copy of the finance documents - this should include the initial finance agreement, term of the loan, repayment history, payout figure requests and approximate payout balance. If finance has been finalised, evidence of the finance release letter from your financier.
- Service and Maintenance History: A copy of the service and maintenance history for the subject vehicle, including service reports and receipts through the service provider or parts purchases/tyres replacement and contact details for the service provider.
- Receipts for Modifications: A copy of receipts or evidence for any modifications made to the subject vehicle.
- Roadworthy Documents: A copy of the roadworthy certificate and/or inspection records for the subject vehicle.
- Toll Statements: A copy of the subject vehicle toll account statements for the date XX to XX.
- Photographs of Vehicle: A copy of photographs of the subject vehicle prior to the incident in the original format.
- Photographs of Incident Scene: A copy of any photographs taken at the incident scene including but not limited to; photos of damage to the subject vehicle(s), registration plate(s), and licence(s). Please ensure these.
- Traffic/Driving History: A copy of your (and all listed / regular drivers) traffic history - this can be obtained by each licence holder from your relevant Transport Department.
- Financial Statements: A copy of your full financial statements (cheque / savings / credit card / loans) for all accounts held in your name, joint-name, or business, or in which you have access to, for the period XX to XX. (To protect your personal information, please redact/black out the middle 5-6 digits of all account numbers, card number and redact/black out the expiry date and CCV number (if appropriate) of any financial statements provided. For example, 1234 56XX XXXX 7890, Expiry XX/XX, CVV XXX). These documents will assist in support of your version of events and movements and financial position around the time of loss.
- MyGov/Centrelink: A copy of your MyGov Account Summary, identifying tax assessment information, and/or Centrelink Benefits.
- Criminal History: Provide your/enter name of person's full National Criminal History. Alternatively, complete the Fit2Work online background check consent form sent via email. The instructions to complete the consent form are included in the email. The process in obtaining the background screening will be facilitated through Fit2Work and there is no cost to you for this service.
- Signed Authorities: A signed authority for XXX (attached).
- Claims/Insurance History: A copy of any documents relating to prior insurance/claims made outside of the Suncorp Group for the period XX to XX , including but not limited to; liability assessment, party details, incident description, settlement/repair details, claim outcome, i.e. accepted, declined, withdrawn (if declined, please advise reason), and a copy of any outcome letter.
- Work Roster/Timesheets: A copy of your Work Roster/Timesheet from XXXX for the period XX to XX - this must include the time you started and ended your shift this day. If you cannot provide a time sheet, you must provide a letter from your Manager with these details.
- Witness Contact Details (Known): Full and complete contact details for XXXX.
- Witness Contacts Details (Unknown): Full and complete contact details for any party to confirm version of events.
- CCTV Footage: A copy of any CCTV footage for the period XXXX to XXXX.
- Medical Certificate / Fit to Interview: A signed medical certificate confirming your capacity to participate in an interview.
- Hospital Records: A copy of documents confirming details of your admission into hospital for the period XX to XX, and any subsequent reports relevant to the claim.
- Medical Records: A copy of all medical records (including but not limited to ambulance and hospital records) relating to the motor vehicle incident.
- Prior Insurance Documents: A copy of any documents for prior insurance held for the subject vehicle.
- Police Documents: A copy of documents issued by the Police including but not limited to charge sheet, brief of evidence, court appearance dates and any other document relevant to this matter.
- Court Documents: A copy of the documents issued to you by the Court, including appearance dates, brief of evidence and outcome notices.
- Rideshare Receipts: A copy of any rideshare receipts for the period XXXX to XXXX.
- Email/Text Message Correspondence: A copy of any correspondence (emails or text messages) confirming the event's date and time.
- Request to Interview: We request that XXXX makes themselves available for a recorded interview.
- Motor Sport/Racetrack Evidence: A copy of any information regarding the participation in a motor sport/racetrack event such as Registration paperwork, Handbook with rules, CAMS logbook.
- Keys: A copy of any photographs of all remaining keys for the subject vehicle.
- Towing Records: A copy of any towing records, receipts or payments made for the claimed incident.
- Vehicle Agreement/Contracts: A copy of any relevant agreements of contracts for use of the subject vehicle.

PROPERTY DOCUMENT STANDARDS
- Telephone Records: Fully itemised telephone call and text records for XXXXXXXXXX and all numbers held in your or joint names, or which you had access to for the period XXX to XXX. This should be in the original, non-editable format provided by your telephone service provider. If the document is provided in a excel spreadsheet, which is able to be edited/modified we are unable to accept this document. For the dates XXXX, please fully itemise all calls and texts made listing the party contacted and reason for the call or text. If you encounter difficulties with your telephone service providers to obtain the above information, please contact the Telecommunications Industry Ombudsman on 1800 062 058 or https://www.tioonline.com.au/consumers/new/.
- Photographs of Property: A copy of photographs of the risk address prior to the incident in the original format.
- Photographs of Content: A copy of photographs of the contents being claimed in the original format.
- Photographs of Damage Post-Event: A copy of any photographs taken post the damage-event. Please ensure these photos are in the original format and size, do not rename the photo and ensure the photo(s) are attached to the email as an attachment.
- Financial Statements: A copy of your full financial statements (cheque / savings / credit card / loans) for all accounts held in your name, joint-name, or business, or in which you have access to, for the period XX to XX. (To protect your personal information, please redact/black out the middle 5-6 digits of all account numbers, card number and redact/black out the expiry date and CCV number (if appropriate) of any financial statements provided. For example, 1234 56XX XXXX 7890, Expiry XX/XX, CVV XXX). These documents will assist in support of your version of events and movements and financial position around the time of loss.
- MyGov/Centrelink: A copy of your MyGov Account Summary, identifying tax assessment information, and/or Centrelink Benefits.
- Criminal History: Provide your/enter name of person's full National Criminal History. Alternatively, complete the Fit2Work online background check consent form sent via email. The instructions to complete the consent form are included in the email. The process in obtaining the background screening will be facilitated through Fit2Work and there is no cost to you for this service.
- Claims/Insurance History: A copy of any documents relating to prior insurance/claims made outside of the Suncorp Group for the period XX to XX , including but not limited to; liability assessment, party details, incident description, settlement/repair details, claim outcome, i.e. accepted, declined, withdrawn (if declined, please advise reason), and a copy of any outcome letter.
- Work Roster/Timesheets: A copy of your Work Roster/Timesheet from XXXX for the period XX to XX - this must include the time you started and ended your shift this day. If you cannot provide a time sheet, you must provide a letter from your Manager with these details.
- Witness Contact Details (Known): Full and complete contact details for XXXX.
- Witness Contacts Details (Unknown): Full and complete contact details for any party to confirm version of events.
- CCTV Footage: A copy of any CCTV footage for the period XXXX to XXXX.
- Fire Report: A copy of the Fire Report, or Authority to Obtain this from the relevant emergency services department.
- Medical Certificate / Fit to Interview: A signed medical certificate confirming your capacity to participate in an interview.
- Hospital Documents: A copy of documents confirming details of your admission into hospital for the period XX to XX, and any subsequent reports relevant to the claim.
- Prior Insurance Documents: A copy of any documents for prior insurance held for the risk address.
- Tenancy Agreements: A copy of the tenancy agreement for the period XX to XX.
- Signed Authorities: A signed authority for XXX (attached).
- Police Documents: A copy of documents issued by the Police including but not limited to charge sheet, brief of evidence, court appearance dates and any other document relevant to this matter.
- Court Documents: A copy of the documents issued to you by the Court, including appearance dates, brief of evidence and outcome notices.
- Inspection Reports: A copy of the pre-purchase or pre-existing inspection reports for the risk address.
- Evidence of Ownership: A copy of evidence of ownership documents for all items claimed.
- Schedule of Loss: A completed Schedule of Loss.
- Service, Maintenance and/or Repair Reports: A copy of any receipts, invoices, reports for repairs, maintenance or servicing for XXXX/the risk address.
- Contract of Sale: A copy of the contract of sale for the risk address.
- Rideshare Receipts: A copy of any rideshare receipts for the period XXXX to XXXX.
- Mobile Phone Related Documents: A copy of the IDs, serial numbers, IMEI numbers.
- Email/Text Message Correspondence: A copy of any correspondence (emails or text messages) confirming the event's date and time.
- Property Manager/Council Correspondence: A copy of any correspondence from the property manager and/or council regarding the condition of the property.
- Development Application: A copy of the development application for the risk address.
- Demolition Documents: A copy of documents relating to the demolition of the risk address, including but not limited to; council documents to confirm date of application and approval for the demolition, any quotes for the demolition, and any invoices for the demolition.
- Condition Report: A copy of the Entry/Exit report conducted at the start/end of the tenancy.
- Leak Detection Report: A copy of any plumbers/leak detection report obtained as a result of the claimed damage.
- Business Records (Business Activity/Use of Property Only): A copy of the relevant business records including BAS Statements, Profit and Loss Statement, Tax Statements for the period XX to XX.
- Business Insurance Records (Business Activity/Use of Property Only): A copy of any business insurance documents for the risk address.
- Booking Schedules (Business Activity/Use of Property Only): A copy of any booking schedules for events at the risk address.
- Request to Interview: We request that XXXX makes themselves available for a recorded interview.
"""

DOC_REQUEST_GOLD_STANDARDS_BLOCK = f"""<GOLD_STANDARDS>
{DOC_REQUEST_GOLD_STANDARDS}
</GOLD_STANDARDS>
"""
