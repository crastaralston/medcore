"""Builds realistic, internally consistent claims for three diagnoses.

A Claim holds every fact once. The renderer prints those facts onto the documents,
so a genuine claim is consistent by construction, and a forgery is a deliberate change.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from faker import Faker

DIAGNOSES = ("dengue", "typhoid", "appendicitis")

# Fictional names only. Any match with a real facility is a coincidence.
HOSPITALS = [
    ("Shree Sai Multispeciality Hospital", "Ghodbunder Road, Thane West, Maharashtra 400615"),
    ("Navjeevan Nursing Home", "Sector 17, Vashi, Navi Mumbai, Maharashtra 400703"),
    ("Aarogya Care Hospital", "LBS Marg, Ghatkopar West, Mumbai, Maharashtra 400086"),
    ("Sanjeevani General Hospital", "Old Panvel, Raigad, Maharashtra 410206"),
    ("Kalpataru Surgical Hospital", "SV Road, Borivali West, Mumbai, Maharashtra 400092"),
]
LABS = [
    ("Precision Pathology Laboratory", "Naupada, Thane West, Maharashtra 400602"),
    ("Accucheck Diagnostic Centre", "Sector 9, Vashi, Navi Mumbai, Maharashtra 400703"),
    ("Lifecare Path Lab", "Andheri East, Mumbai, Maharashtra 400069"),
]
PHARMACIES = [
    ("Shree Ganesh Medical & General Stores", "Thane West, Maharashtra 400615"),
    ("Om Sai Chemist", "Vashi, Navi Mumbai, Maharashtra 400703"),
    ("Mahalaxmi Pharmacy", "Ghatkopar West, Mumbai, Maharashtra 400086"),
]
QUALIFICATIONS = ["MBBS, MD (Medicine)", "MBBS, DNB (General Medicine)", "MBBS, MS (General Surgery)"]


@dataclass
class Test:
    name: str  # printed name, matched by the reader against the knowledge table
    value: str
    unit: str = ""
    ref: str = ""


@dataclass
class LabReport:
    report_no: str
    collected: date
    reported: date
    tests: list[Test]
    title: str = "HAEMATOLOGY / SEROLOGY REPORT"


@dataclass
class Item:
    description: str
    qty: int
    rate: float
    amount_override: float | None = None  # set only by forgeries that break arithmetic

    @property
    def amount(self) -> float:
        return self.amount_override if self.amount_override is not None else round(self.qty * self.rate, 2)


@dataclass
class Claim:
    claim_id: str
    diagnosis_key: str
    patient_name: str
    age: int
    sex: str
    hospital: tuple[str, str]
    lab: tuple[str, str]
    pharmacy: tuple[str, str]
    doctor: str
    doctor_qual: str
    doctor_reg: str
    pathologist: str
    admission: date
    discharge: date
    diagnosis_text: str
    procedure: str | None
    complaints: str
    course: str
    investigations_summary: str  # printed in the discharge summary, quotes lab values
    treatment: list[str]
    lab_reports: list[LabReport]
    bill_no: str
    bill_items: list[Item]
    bill_total_override: float | None = None
    bill_diagnosis: str | None = None
    bill_admission: date | None = None  # forgeries can make the bill disagree with the summary
    pharmacy_invoice: str = ""
    pharmacy_date: date | None = None
    pharmacy_items: list[Item] = field(default_factory=list)
    style: int = 0  # layout variant, 0 or 1
    # Per-document overrides used by forgeries: {"lab_report_1": {"patient_name": "..."}}
    overrides: dict[str, dict[str, object]] = field(default_factory=dict)

    @property
    def stay_days(self) -> int:
        return (self.discharge - self.admission).days

    @property
    def bill_total(self) -> float:
        if self.bill_total_override is not None:
            return self.bill_total_override
        return round(sum(i.amount for i in self.bill_items), 2)

    @property
    def pharmacy_total(self) -> float:
        return round(sum(i.amount for i in self.pharmacy_items), 2)

    def clone(self, claim_id: str) -> Claim:
        c = copy.deepcopy(self)
        c.claim_id = claim_id
        return c


def indian(n: float, decimals: int = 0) -> str:
    """Format a number the Indian way: 1,32,000 or 12,500.00."""
    whole, _, frac = f"{abs(n):.{decimals}f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return ("-" if n < 0 else "") + whole + (f".{frac}" if frac else "")


def _reg_no(rng: random.Random) -> str:
    return f"MMC/{rng.randint(2004, 2019)}/{rng.randint(1, 12):02d}/{rng.randint(1000, 9999)}"


def _cbc(rng: random.Random, platelets: int, wbc: int, hb: float, hct: float) -> list[Test]:
    return [
        Test("Haemoglobin", f"{hb:.1f}", "g/dL", "13.0 - 17.0"),
        Test("Total WBC Count", indian(wbc), "/cumm", "4,000 - 11,000"),
        Test("Platelet Count", indian(platelets), "/cumm", "1,50,000 - 4,50,000"),
        Test("Haematocrit (PCV)", f"{hct:.1f}", "%", "40.0 - 50.0"),
    ]


def make_claim(claim_id: str, diagnosis_key: str, seed: int) -> Claim:
    rng = random.Random(seed)
    fake = Faker("en_IN")
    fake.seed_instance(seed)

    sex = rng.choice(["Male", "Female"])
    name = fake.name_male() if sex == "Male" else fake.name_female()
    age = rng.randint(19, 68)
    admission = date(2026, 1, 5) + timedelta(days=rng.randint(0, 260))
    hospital = rng.choice(HOSPITALS)
    lab = rng.choice(LABS)
    pharmacy = rng.choice(PHARMACIES)
    doctor = f"Dr. {fake.name_male() if rng.random() < 0.6 else fake.name_female()}"
    style = rng.randint(0, 1)

    def report_no() -> str:
        return f"{rng.choice(['PPL', 'ADC', 'LPL'])}{rng.randint(100000, 999999)}"

    if diagnosis_key == "dengue":
        stay = rng.randint(3, 5)
        discharge = admission + timedelta(days=stay)
        p1 = rng.randrange(62_000, 118_000, 1000)
        p2 = rng.randrange(118_000, 165_000, 1000)
        hb = rng.uniform(12.6, 15.4)
        reports = [
            LabReport(report_no(), admission, admission,
                      _cbc(rng, p1, rng.randrange(2600, 4400, 100), hb, rng.uniform(42, 47))
                      + [Test("NS1 Antigen (Dengue)", "Positive", "", "Negative")]),
            LabReport(report_no(), discharge - timedelta(days=1), discharge - timedelta(days=1),
                      [Test("Platelet Count", indian(p2), "/cumm", "1,50,000 - 4,50,000"),
                       Test("Haematocrit (PCV)", f"{rng.uniform(39, 44):.1f}", "%", "40.0 - 50.0")],
                      title="HAEMATOLOGY REPORT"),
        ]
        diagnosis_text = "Dengue fever with thrombocytopenia"
        procedure = None
        complaints = f"Fever with chills for {rng.randint(2, 4)} days, body ache, headache and vomiting."
        course = ("Patient was managed conservatively with IV fluids and antipyretics. Platelet counts "
                  "were monitored. Patient became afebrile and is being discharged in stable condition.")
        inv = (f"Platelet count {indian(p1)}/cumm on {admission:%d/%m/%Y}; {indian(p2)}/cumm on "
               f"{discharge - timedelta(days=1):%d/%m/%Y}. NS1 antigen positive.")
        treatment = ["Inj. Ringer Lactate 500 ml IV", "Tab. Paracetamol 650 mg SOS",
                     "Inj. Pantoprazole 40 mg IV OD", "ORS sachets"]
        pharm = [Item("Paracetamol 650 mg Tab", 15, 2.1), Item("Ringer Lactate 500 ml", stay * 2, 68.0),
                 Item("Pantoprazole 40 mg Inj", stay, 54.0), Item("ORS Sachet 21.8 g", 10, 21.0)]
        extra_items: list[Item] = []
    elif diagnosis_key == "typhoid":
        stay = rng.randint(4, 7)
        discharge = admission + timedelta(days=stay)
        titre = rng.choice(["1:160", "1:320"])
        reports = [
            LabReport(report_no(), admission, admission,
                      _cbc(rng, rng.randrange(160_000, 290_000, 1000), rng.randrange(4200, 7800, 100),
                           rng.uniform(12.2, 15.0), rng.uniform(40, 46))
                      + [Test("Widal Test (S. Typhi O)", titre, "", "Below 1:80"),
                         Test("Widal Test (S. Typhi H)", titre, "", "Below 1:80")]),
        ]
        if rng.random() < 0.5:
            reports.append(LabReport(report_no(), admission, admission + timedelta(days=2),
                                     [Test("Blood Culture", "Salmonella Typhi isolated", "", "No growth")],
                                     title="MICROBIOLOGY REPORT"))
        diagnosis_text = "Enteric fever (Typhoid)"
        procedure = None
        complaints = f"Fever for {rng.randint(5, 9)} days with abdominal pain and loss of appetite."
        course = ("Patient was started on IV antibiotics and supportive care. Fever settled gradually. "
                  "Patient is tolerating orally and is discharged with oral antibiotics.")
        inv = f"Widal test positive (S. Typhi O {titre}, H {titre})."
        treatment = ["Inj. Ceftriaxone 1 g IV BD", "Tab. Paracetamol 650 mg SOS",
                     "Inj. Pantoprazole 40 mg IV OD", "Tab. Azithromycin 500 mg OD on discharge"]
        pharm = [Item("Ceftriaxone 1 g Inj", stay * 2, 62.0), Item("Paracetamol 650 mg Tab", 15, 2.1),
                 Item("Pantoprazole 40 mg Inj", stay, 54.0), Item("Azithromycin 500 mg Tab", 5, 22.5)]
        extra_items = []
    elif diagnosis_key == "appendicitis":
        stay = rng.randint(2, 4)
        discharge = admission + timedelta(days=stay)
        wbc = rng.randrange(12_400, 17_800, 100)
        reports = [
            LabReport(report_no(), admission, admission,
                      _cbc(rng, rng.randrange(190_000, 340_000, 1000), wbc, rng.uniform(12.8, 15.6),
                           rng.uniform(41, 47))),
            LabReport(report_no(), admission, admission,
                      [Test("USG Abdomen", "Findings suggestive of acute appendicitis", "", "")],
                      title="RADIOLOGY REPORT"),
        ]
        diagnosis_text = "Acute appendicitis"
        procedure = "Laparoscopic appendicectomy"
        complaints = "Pain in right lower abdomen for 1 day with nausea and low-grade fever."
        course = (f"Patient underwent laparoscopic appendicectomy on {admission:%d/%m/%Y} under general "
                  "anaesthesia. Post-operative period was uneventful. Discharged in stable condition.")
        inv = f"Total WBC count {indian(wbc)}/cumm. USG abdomen suggestive of acute appendicitis."
        treatment = ["Inj. Ceftriaxone 1 g IV BD", "Inj. Metronidazole 500 mg IV TDS",
                     "Inj. Paracetamol 1 g IV SOS", "Tab. Cefuroxime 500 mg BD on discharge"]
        pharm = [Item("Ceftriaxone 1 g Inj", stay * 2, 62.0), Item("Metronidazole 500 mg Infusion", stay * 3, 28.0),
                 Item("Paracetamol 1 g Infusion", 4, 145.0), Item("Cefuroxime 500 mg Tab", 10, 38.0)]
        extra_items = [Item("Operation Theatre Charges", 1, float(rng.randrange(15000, 25001, 500))),
                       Item("Surgeon Fees", 1, float(rng.randrange(20000, 30001, 1000))),
                       Item("Anaesthetist Fees", 1, float(rng.randrange(6000, 10001, 500))),
                       Item("Surgical Consumables", 1, float(rng.randrange(4000, 9001, 250)))]
    else:
        raise ValueError(f"unknown diagnosis {diagnosis_key!r}")

    room_rate = float(rng.choice([1800, 2200, 2500, 3000]))
    bill_items = [
        Item("Registration Charges", 1, 200.0),
        Item("Room Rent (General Ward)", stay, room_rate),
        Item("Nursing Charges", stay, 500.0),
        Item("Consultant Visit Charges", stay * 2, 600.0),
        *extra_items,
        Item("Laboratory Investigations", 1, float(rng.randrange(1800, 4501, 50))),
        Item("IV Fluids & Consumables", 1, float(rng.randrange(1200, 3001, 50))),
    ]

    return Claim(
        claim_id=claim_id, diagnosis_key=diagnosis_key, patient_name=name, age=age, sex=sex,
        hospital=hospital, lab=lab, pharmacy=pharmacy, doctor=doctor,
        doctor_qual=rng.choice(QUALIFICATIONS[2:] if procedure else QUALIFICATIONS[:2]),
        doctor_reg=_reg_no(rng), pathologist=f"Dr. {fake.last_name()}",
        admission=admission, discharge=discharge,
        diagnosis_text=diagnosis_text, procedure=procedure, complaints=complaints, course=course,
        investigations_summary=inv, treatment=treatment, lab_reports=reports,
        bill_no=f"IPD/{admission:%y}/{rng.randint(10000, 99999)}", bill_items=bill_items,
        pharmacy_invoice=f"INV-{rng.randint(100000, 999999)}",
        pharmacy_date=discharge if rng.random() < 0.5 else admission,
        pharmacy_items=pharm, style=style,
    )
