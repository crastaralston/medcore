# 06_tripled_pharmacy_qty_dengue

**What was faked:** Every pharmacy quantity tripled, with a matching total (not expected to be caught yet).

**Which document was changed:** `pharmacy_bill.pdf`

**How it was faked:** the document was re-printed with the new value, so the file itself looks perfect. Only checks 2 and 3 can catch this, unless the document was sealed.

## The documents in this folder

### `discharge_summary.pdf` - discharge summary

Written by the hospital when the patient goes home. It states the diagnosis, the dates of the stay, the treating doctor and the key lab results.

- QR seal: no seal
- Patient: Ryan Baral, 44, Male
- Issued by: Kalpataru Surgical Hospital
- Stay: 25 Jan 2026 to 30 Jan 2026
- Diagnosis: Dengue fever with thrombocytopenia
- Lab values it quotes: platelet count 96,000, 1,20,000

### `hospital_bill.pdf` - hospital bill

The hospital's final bill: every charge for the stay, line by line, with a grand total.

- QR seal: no seal
- Patient: Ryan Baral, 44, Male
- Issued by: Kalpataru Surgical Hospital
- Stay: 25 Jan 2026 to 30 Jan 2026
- Diagnosis: Dengue fever with thrombocytopenia
- 6 line items, total Rs. 26,700.00

### `lab_report_1.pdf` - lab report

A test report from the laboratory: what was tested, the result, and the normal range.

- QR seal: no seal
- Patient: Ryan Baral, 44, Male
- Issued by: Lifecare Path Lab
- Sample taken: 25 Jan 2026, reported 25 Jan 2026
- Results: Haemoglobin 12.7 g/dL; Total WBC Count 2,700 /cumm; Platelet Count 96,000 /cumm; Haematocrit (PCV) 46.2 %; NS1 Antigen (Dengue) Positive

### `lab_report_2.pdf` - lab report

A test report from the laboratory: what was tested, the result, and the normal range.

- QR seal: no seal
- Patient: Ryan Baral, 44, Male
- Issued by: Lifecare Path Lab
- Sample taken: 29 Jan 2026, reported 29 Jan 2026
- Results: Platelet Count 1,20,000 /cumm; Haematocrit (PCV) 43.6 %

### `pharmacy_bill.pdf` - pharmacy bill

The chemist's invoice for medicines bought for this treatment.

- QR seal: no seal
- Patient: Ryan Baral
- Issued by: Shree Ganesh Medical & General Stores
- 4 line items, total Rs. 3,574.50
- Invoice date: 25 Jan 2026

## What MedCore reports in the Claim check screen

**Verdict: Pass**

No problems. Every document agrees with the others and with the diagnosis.

This forgery is **not caught** by the current version. That is expected: it is listed as future scope. Say so openly in the demo; it shows you know the limits.
