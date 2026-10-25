# 04_painted_over_total_appendicitis

**What was faked:** Grand total painted over: 79,350.00 -> 94,350.00.

**Which document was changed:** `hospital_bill.pdf`

**How it was faked:** a white box was painted over the real value inside the PDF and a new value typed on top, then the file was saved again. The original value is still hidden in the file.

## The documents in this folder

### `discharge_summary.pdf` - discharge summary

Written by the hospital when the patient goes home. It states the diagnosis, the dates of the stay, the treating doctor and the key lab results.

- QR seal: no seal
- Patient: Yoshita Dada, 52, Female
- Issued by: Navjeevan Nursing Home
- Stay: 05 Mar 2026 to 07 Mar 2026
- Diagnosis: Acute appendicitis
- Procedure: Laparoscopic appendicectomy
- Lab values it quotes: total wbc count 16,000

### `hospital_bill.pdf` - hospital bill

The hospital's final bill: every charge for the stay, line by line, with a grand total.

- QR seal: no seal
- Patient: Yoshita Dada, 52, Female
- Issued by: Navjeevan Nursing Home
- Stay: 05 Mar 2026 to 07 Mar 2026
- Diagnosis: Acute appendicitis
- 10 line items, total Rs. 94,350.00

### `lab_report_1.pdf` - lab report

A test report from the laboratory: what was tested, the result, and the normal range.

- QR seal: no seal
- Patient: Yoshita Dada, 52, Female
- Issued by: Accucheck Diagnostic Centre
- Sample taken: 05 Mar 2026, reported 05 Mar 2026
- Results: Haemoglobin 15.0 g/dL; Total WBC Count 16,000 /cumm; Platelet Count 2,30,000 /cumm; Haematocrit (PCV) 45.1 %

### `lab_report_2.pdf` - lab report

A test report from the laboratory: what was tested, the result, and the normal range.

- QR seal: no seal
- Patient: Yoshita Dada, 52, Female
- Issued by: Accucheck Diagnostic Centre
- Sample taken: 05 Mar 2026, reported 05 Mar 2026
- Results: USG Abdomen Findings suggestive of acute appendicitis

### `pharmacy_bill.pdf` - pharmacy bill

The chemist's invoice for medicines bought for this treatment.

- QR seal: no seal
- Patient: Yoshita Dada
- Issued by: Shree Ganesh Medical & General Stores
- 4 line items, total Rs. 1,376.00
- Invoice date: 07 Mar 2026

## What MedCore reports in the Claim check screen

**Verdict: Hold for review**

1. **Serious: Text painted over inside the PDF** (check 1, Editing signs)  
   A value was covered and new text typed on top. The original text is still in the file.
2. **Serious: Hospital bill total does not add up** (check 2, Documents agree?)  
   The lines add up to Rs. 79,350.00, but the total says Rs. 94,350.00 (difference Rs. 15,000.00).
3. **Check: PDF was saved again after it was made** (check 1, Editing signs)  
   The file has 1 extra save layer(s) added on top of the original.
4. **Check: PDF last written by an editing tool** (check 1, Editing signs)  
   Hospital and lab systems do not normally produce files with this tool.
