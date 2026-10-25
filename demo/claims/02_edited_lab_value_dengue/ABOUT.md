# 02_edited_lab_value_dengue

**What was faked:** Platelet Count changed from 89,000 to 36,000.

**Which document was changed:** `lab_report_1.pdf`

**How it was faked:** the document was re-printed with the new value, so the file itself looks perfect. Only checks 2 and 3 can catch this, unless the document was sealed.

## The documents in this folder

### `discharge_summary.pdf` - discharge summary

Written by the hospital when the patient goes home. It states the diagnosis, the dates of the stay, the treating doctor and the key lab results.

- QR seal: no seal
- Patient: Advik Maharaj, 20, Male
- Issued by: Navjeevan Nursing Home
- Stay: 25 May 2026 to 30 May 2026
- Diagnosis: Dengue fever with thrombocytopenia
- Lab values it quotes: platelet count 89,000, 1,20,000

### `hospital_bill.pdf` - hospital bill

The hospital's final bill: every charge for the stay, line by line, with a grand total.

- QR seal: no seal
- Patient: Advik Maharaj, 20, Male
- Issued by: Navjeevan Nursing Home
- Stay: 25 May 2026 to 30 May 2026
- Diagnosis: Dengue fever with thrombocytopenia
- 6 line items, total Rs. 28,800.00

### `lab_report_1.pdf` - lab report

A test report from the laboratory: what was tested, the result, and the normal range.

- QR seal: no seal
- Patient: Advik Maharaj, 20, Male
- Issued by: Precision Pathology Laboratory
- Sample taken: 25 May 2026, reported 25 May 2026
- Results: Haemoglobin 12.7 g/dL; Total WBC Count 4,200 /cumm; Platelet Count 36,000 /cumm; Haematocrit (PCV) 45.0 %; NS1 Antigen (Dengue) Positive

### `lab_report_2.pdf` - lab report

A test report from the laboratory: what was tested, the result, and the normal range.

- QR seal: no seal
- Patient: Advik Maharaj, 20, Male
- Issued by: Precision Pathology Laboratory
- Sample taken: 29 May 2026, reported 29 May 2026
- Results: Platelet Count 1,20,000 /cumm; Haematocrit (PCV) 42.6 %

### `pharmacy_bill.pdf` - pharmacy bill

The chemist's invoice for medicines bought for this treatment.

- QR seal: no seal
- Patient: Advik Maharaj
- Issued by: Shree Ganesh Medical & General Stores
- 4 line items, total Rs. 1,191.50
- Invoice date: 30 May 2026

## What MedCore reports in the Claim check screen

**Verdict: Hold for review**

1. **Serious: Lab value differs from the discharge summary** (check 2, Documents agree?)  
   The discharge summary quotes platelet count as 89,000, but the lab reports show 36,000 in lab_report_1.pdf; 1,20,000 in lab_report_2.pdf.
