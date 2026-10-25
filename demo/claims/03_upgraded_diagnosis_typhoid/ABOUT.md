# 03_upgraded_diagnosis_typhoid

**What was faked:** Diagnosis changed from 'Enteric fever (Typhoid)' to 'Dengue fever with thrombocytopenia' on summary and bill.

**Which document was changed:** `discharge_summary.pdf`

**How it was faked:** the document was re-printed with the new value, so the file itself looks perfect. Only checks 2 and 3 can catch this, unless the document was sealed.

## The documents in this folder

### `discharge_summary.pdf` - discharge summary

Written by the hospital when the patient goes home. It states the diagnosis, the dates of the stay, the treating doctor and the key lab results.

- QR seal: no seal
- Patient: Luke Dhawan, 37, Male
- Issued by: Sanjeevani General Hospital
- Stay: 19 Mar 2026 to 26 Mar 2026
- Diagnosis: Dengue fever with thrombocytopenia
- Lab values it quotes: widal o 1:320

### `hospital_bill.pdf` - hospital bill

The hospital's final bill: every charge for the stay, line by line, with a grand total.

- QR seal: no seal
- Patient: Luke Dhawan, 37, Male
- Issued by: Sanjeevani General Hospital
- Stay: 19 Mar 2026 to 26 Mar 2026
- Diagnosis: Dengue fever with thrombocytopenia
- 6 line items, total Rs. 36,800.00

### `lab_report_1.pdf` - lab report

A test report from the laboratory: what was tested, the result, and the normal range.

- QR seal: no seal
- Patient: Luke Dhawan, 37, Male
- Issued by: Accucheck Diagnostic Centre
- Sample taken: 19 Mar 2026, reported 19 Mar 2026
- Results: Haemoglobin 13.9 g/dL; Total WBC Count 6,500 /cumm; Platelet Count 2,70,000 /cumm; Haematocrit (PCV) 45.7 %; Widal Test (S. Typhi O) 1:320; Widal Test (S. Typhi H) 1:320

### `pharmacy_bill.pdf` - pharmacy bill

The chemist's invoice for medicines bought for this treatment.

- QR seal: no seal
- Patient: Luke Dhawan
- Issued by: Mahalaxmi Pharmacy
- 4 line items, total Rs. 1,390.00
- Invoice date: 19 Mar 2026

## What MedCore reports in the Claim check screen

**Verdict: Hold for review**

1. **Serious: Diagnosis says low platelets, but every count is normal** (check 3, Medicine fits?)  
   Thrombocytopenia means a platelet count below 150,000/cumm. The lowest count in the file is 270,000/cumm.
2. **Check: No test in the file confirms the diagnosis** (check 3, Medicine fits?)  
   A diagnosis of dengue fever is normally backed by one of: NS1 antigen, Dengue IgM. None of the lab reports has one.
3. **Check: Only one reading where repeats are expected** (check 3, Medicine fits?)  
   A 7-day stay for dengue fever normally has repeated platelet counts; the file has 1.
