# 08_sealed_then_edited_dengue

**What was faked:** After sealing, platelet Count changed from 1,13,000 to 30,000, and the original QR code was copied onto the edited page.

**Which document was changed:** `lab_report_1.pdf`

**How it was faked:** after sealing, the page was re-printed with a changed value and the genuine QR code was copied onto it. The QR code is real, but it no longer matches the page.

## The documents in this folder

### `discharge_summary.pdf` - discharge summary

Written by the hospital when the patient goes home. It states the diagnosis, the dates of the stay, the treating doctor and the key lab results.

- QR seal: valid seal, matches the page (sealed by Kalpataru Surgical Hospital, stay IPD/26/98115)
- Patient: Ekaja Warrior, 27, Female
- Issued by: Kalpataru Surgical Hospital
- Stay: 08 Jun 2026 to 11 Jun 2026
- Diagnosis: Dengue fever with thrombocytopenia
- Lab values it quotes: platelet count 1,13,000, 1,60,000

### `hospital_bill.pdf` - hospital bill

The hospital's final bill: every charge for the stay, line by line, with a grand total.

- QR seal: valid seal, matches the page (sealed by Kalpataru Surgical Hospital, stay IPD/26/98115)
- Patient: Ekaja Warrior, 27, Female
- Issued by: Kalpataru Surgical Hospital
- Stay: 08 Jun 2026 to 11 Jun 2026
- Diagnosis: Dengue fever with thrombocytopenia
- 6 line items, total Rs. 15,150.00

### `lab_report_1.pdf` - lab report

A test report from the laboratory: what was tested, the result, and the normal range.

- QR seal: Altered after sealing
- Patient: Ekaja Warrior, 27, Female
- Issued by: Precision Pathology Laboratory
- Sample taken: 08 Jun 2026, reported 08 Jun 2026
- Results: Haemoglobin 12.9 g/dL; Total WBC Count 3,200 /cumm; Platelet Count 30,000 /cumm; Haematocrit (PCV) 45.8 %; NS1 Antigen (Dengue) Positive

### `lab_report_2.pdf` - lab report

A test report from the laboratory: what was tested, the result, and the normal range.

- QR seal: no seal
- Patient: Ekaja Warrior, 27, Female
- Issued by: Precision Pathology Laboratory
- Sample taken: 10 Jun 2026, reported 10 Jun 2026
- Results: Platelet Count 1,60,000 /cumm; Haematocrit (PCV) 41.5 %

### `pharmacy_bill.pdf` - pharmacy bill

The chemist's invoice for medicines bought for this treatment.

- QR seal: valid seal, matches the page (sealed by Mahalaxmi Pharmacy, stay IPD/26/98115)
- Patient: Ekaja Warrior
- Issued by: Mahalaxmi Pharmacy
- 4 line items, total Rs. 811.50
- Invoice date: 08 Jun 2026

## What MedCore reports in the Claim check screen

**Verdict: Hold for review**

1. **Serious: Altered after sealing** (check 1, Editing signs)  
   Platelet count: signed '1,13,000', printed '30,000'
2. **Serious: Lab value differs from the discharge summary** (check 2, Documents agree?)  
   The discharge summary quotes platelet count as 1,13,000, but the lab reports show 30,000 in lab_report_1.pdf; 1,60,000 in lab_report_2.pdf.
