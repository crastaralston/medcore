# 09_borrowed_sealed_report_typhoid

**What was faked:** lab_report_1.pdf is a genuine sealed report, but it belongs to Lila Patla's stay IPD/26/94295, not this patient's stay IPD/26/59291.

**Which document was changed:** `lab_report_1.pdf`

**How it was faked:** a genuine, correctly sealed lab report from another patient's hospital stay was put into this claim.

## The documents in this folder

### `discharge_summary.pdf` - discharge summary

Written by the hospital when the patient goes home. It states the diagnosis, the dates of the stay, the treating doctor and the key lab results.

- QR seal: valid seal, matches the page (sealed by Shree Sai Multispeciality Hospital, stay IPD/26/59291)
- Patient: Orinder Sachdev, 41, Male
- Issued by: Shree Sai Multispeciality Hospital
- Stay: 04 Aug 2026 to 08 Aug 2026
- Diagnosis: Enteric fever (Typhoid)
- Lab values it quotes: widal o 1:320

### `hospital_bill.pdf` - hospital bill

The hospital's final bill: every charge for the stay, line by line, with a grand total.

- QR seal: valid seal, matches the page (sealed by Shree Sai Multispeciality Hospital, stay IPD/26/59291)
- Patient: Orinder Sachdev, 41, Male
- Issued by: Shree Sai Multispeciality Hospital
- Stay: 04 Aug 2026 to 08 Aug 2026
- Diagnosis: Enteric fever (Typhoid)
- 6 line items, total Rs. 21,300.00

### `lab_report_1.pdf` - lab report

A test report from the laboratory: what was tested, the result, and the normal range.

- QR seal: valid seal, matches the page (sealed by Lifecare Path Lab, stay IPD/26/94295)
- Patient: Lila Patla, 36, Female
- Issued by: Lifecare Path Lab
- Sample taken: 10 Jul 2026, reported 10 Jul 2026
- Results: Haemoglobin 13.2 g/dL; Total WBC Count 5,100 /cumm; Platelet Count 1,81,000 /cumm; Haematocrit (PCV) 40.6 %; Widal Test (S. Typhi O) 1:320; Widal Test (S. Typhi H) 1:320

### `pharmacy_bill.pdf` - pharmacy bill

The chemist's invoice for medicines bought for this treatment.

- QR seal: valid seal, matches the page (sealed by Mahalaxmi Pharmacy, stay IPD/26/59291)
- Patient: Orinder Sachdev
- Issued by: Mahalaxmi Pharmacy
- 4 line items, total Rs. 856.00
- Invoice date: 04 Aug 2026

## What MedCore reports in the Claim check screen

**Verdict: Hold for review**

1. **Serious: Sealed documents come from different hospital stays** (check 2, Documents agree?)  
   Each document's seal names the stay it belongs to, and they do not agree. IPD/26/59291: discharge_summary.pdf, hospital_bill.pdf, pharmacy_bill.pdf; IPD/26/94295: lab_report_1.pdf.
2. **Serious: Patient name differs between documents** (check 2, Documents agree?)  
   'Lila Patla' on the lab report, 'Orinder Sachdev' on the discharge summary.
3. **Serious: Patient age differs between documents** (check 2, Documents agree?)  
   Age 36 on the lab report, 41 on the discharge summary.
4. **Serious: Patient sex differs between documents** (check 2, Documents agree?)  
   Female on the lab report, Male on the discharge summary.
