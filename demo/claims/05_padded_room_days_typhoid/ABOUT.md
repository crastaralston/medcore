# 05_padded_room_days_typhoid

**What was faked:** Room rent and nursing billed for 3 extra days; total updated to match.

**Which document was changed:** `hospital_bill.pdf`

**How it was faked:** the document was re-printed with the new value, so the file itself looks perfect. Only checks 2 and 3 can catch this, unless the document was sealed.

## The documents in this folder

### `discharge_summary.pdf` - discharge summary

Written by the hospital when the patient goes home. It states the diagnosis, the dates of the stay, the treating doctor and the key lab results.

- QR seal: no seal
- Patient: Turvi Sura, 45, Female
- Issued by: Aarogya Care Hospital
- Stay: 11 Sep 2026 to 18 Sep 2026
- Diagnosis: Enteric fever (Typhoid)
- Lab values it quotes: widal o 1:160

### `hospital_bill.pdf` - hospital bill

The hospital's final bill: every charge for the stay, line by line, with a grand total.

- QR seal: no seal
- Patient: Turvi Sura, 45, Female
- Issued by: Aarogya Care Hospital
- Stay: 11 Sep 2026 to 18 Sep 2026
- Diagnosis: Enteric fever (Typhoid)
- 6 line items, total Rs. 39,900.00

### `lab_report_1.pdf` - lab report

A test report from the laboratory: what was tested, the result, and the normal range.

- QR seal: no seal
- Patient: Turvi Sura, 45, Female
- Issued by: Precision Pathology Laboratory
- Sample taken: 11 Sep 2026, reported 11 Sep 2026
- Results: Haemoglobin 14.6 g/dL; Total WBC Count 6,100 /cumm; Platelet Count 1,90,000 /cumm; Haematocrit (PCV) 43.9 %; Widal Test (S. Typhi O) 1:160; Widal Test (S. Typhi H) 1:160

### `pharmacy_bill.pdf` - pharmacy bill

The chemist's invoice for medicines bought for this treatment.

- QR seal: no seal
- Patient: Turvi Sura
- Issued by: Om Sai Chemist
- 4 line items, total Rs. 1,390.00
- Invoice date: 18 Sep 2026

## What MedCore reports in the Claim check screen

**Verdict: Hold for review**

1. **Serious: More days billed than the patient stayed** (check 2, Documents agree?)  
   Room Rent (General Ward) billed for 10 days; the stay was 7 days (11 Sep to 18 Sep 2026).
2. **Serious: More days billed than the patient stayed** (check 2, Documents agree?)  
   Nursing Charges billed for 10 days; the stay was 7 days (11 Sep to 18 Sep 2026).
