import pytest
from fastapi.testclient import TestClient

from medcore_verify.api import create_app
from medcore_verify.datagen.demo import build_demo
from medcore_verify.datagen.forge import forge
from medcore_verify.datagen.scenarios import make_claim


@pytest.fixture(scope="module")
def demo_dir(tmp_path_factory):
    demo = tmp_path_factory.mktemp("demo")
    build_demo(demo)
    return demo


@pytest.fixture
def client(tmp_path, demo_dir):
    app = create_app(data_dir=tmp_path, database_url=f"sqlite:///{tmp_path / 'test.db'}", demo_dir=demo_dir)
    return TestClient(app)


def upload(client, files: dict[str, bytes], label: str = "test claim"):
    return client.post("/api/checks", data={"label": label},
                       files=[("files", (name, data, "application/pdf")) for name, data in files.items()])


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and isinstance(body["image_ocr"], bool)


def test_upload_check_and_fetch_back(client):
    files, _ = forge(make_claim("A", "appendicitis", 8), "F5", "overlay_total", seed=2)
    res = upload(client, files)
    assert res.status_code == 201
    body = res.json()
    assert body["verdict"] == "hold"
    assert any(f["code"] == "pdf_overprint" for f in body["report"]["flags"])
    check_id = body["id"]
    assert client.get(f"/api/checks/{check_id}").json()["id"] == check_id
    assert client.get("/api/checks").json()[0]["id"] == check_id
    pdf = client.get(f"/api/checks/{check_id}/files/hospital_bill.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    png = client.get(f"/api/checks/{check_id}/previews/hospital_bill.pdf")
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"


def test_samples_list_and_check(client):
    samples = client.get("/api/samples").json()
    assert len(samples) == 9 and samples[0]["name"] == "01_genuine_dengue"
    assert [s["sealed"] for s in samples].count(True) == 3
    genuine = client.post("/api/samples/01_genuine_dengue/check").json()
    assert genuine["verdict"] == "pass" and genuine["truth"]["genuine"] is True
    sealed = client.post("/api/samples/07_sealed_genuine_dengue/check").json()
    assert sealed["verdict"] == "pass"
    assert all(d["seal"]["status"] == "genuine" for d in sealed["report"]["documents"])
    edited = client.post("/api/samples/08_sealed_then_edited_dengue/check").json()
    assert edited["verdict"] == "hold" and any(f["code"] == "seal_altered" for f in edited["report"]["flags"])


def test_issue_verify_and_revoke(client):
    issuers = client.get("/api/issuers").json()
    lab = next(i for i in issuers if i["kind"] == "lab" and i["can_seal_here"])
    res = client.post("/api/seal", data={"issuer_id": lab["id"], "stay_id": "IPD/26/00001",
                                         "sample_file": "01_genuine_dengue/lab_report_1.pdf"})
    assert res.status_code == 201, res.text
    sealed = res.json()
    doc_id = sealed["doc_id"]
    assert sealed["payload"]["stay"] == "IPD/26/00001" and sealed["payload"]["iss"] == lab["id"]

    pdf = client.get(f"/api/sealed/{doc_id}.pdf", params={"name": sealed["file_name"]})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get(f"/api/sealed/{doc_id}/qr.png").headers["content-type"] == "image/png"

    def verify(data):
        return client.post("/api/verify", files={"file": ("doc.pdf", data, "application/pdf")}).json()["seal"]

    assert verify(pdf.content)["status"] == "genuine"
    log = client.get("/api/log").json()
    assert log["intact"] and log["entries"][0]["doc_id"] == doc_id

    assert client.post(f"/api/log/{sealed['display_id']}/revoke", json={"reason": "Wrong patient"}).status_code == 201
    assert verify(pdf.content)["status"] == "revoked"
    assert client.post(f"/api/log/{doc_id}/revoke", json={"reason": "again"}).status_code == 422


def test_verify_demo_files(client, demo_dir):
    expected = {"1_genuine_sealed_lab_report.pdf": "genuine", "2_edited_after_sealing.pdf": "altered",
                "3_fake_qr_unregistered_lab.pdf": "unknown_issuer", "4_stolen_key_never_logged.pdf": "unlogged",
                "5_unsealed_lab_report.pdf": "no_seal"}
    for name, want in expected.items():
        data = (demo_dir / "verify" / name).read_bytes()
        got = client.post("/api/verify", files={"file": (name, data, "application/pdf")}).json()["seal"]["status"]
        assert got == want, name


def test_register_and_suspend_issuer(client):
    res = client.post("/api/issuers", json={"name": "New City Clinic", "kind": "hospital", "address": "Vashi"})
    assert res.status_code == 201 and res.json()["can_seal_here"]
    assert client.post("/api/issuers", json={"name": "New City Clinic", "kind": "hospital"}).status_code == 422
    assert client.post("/api/issuers", json={"name": "X", "kind": "bank"}).status_code == 422
    assert client.post("/api/issuers/new-city-clinic/status", json={"status": "suspended"}).json()["status"] == "suspended"
    res = client.post("/api/seal", data={"issuer_id": "new-city-clinic",
                                         "sample_file": "01_genuine_dengue/hospital_bill.pdf"})
    assert res.status_code == 422 and "suspended" in res.json()["detail"]


def test_bad_requests(client):
    assert upload(client, {"notes.txt": b"hello"}).status_code == 422
    assert client.post("/api/checks", data={"label": "x"}).status_code == 422
    assert client.get("/api/checks/not-an-id").status_code == 404
    assert client.get("/api/checks/" + "0" * 32).status_code == 404
    assert client.post("/api/samples/..%2F..%2Fetc/check").status_code == 404
    assert client.post("/api/seal", data={"issuer_id": "x", "sample_file": "../../etc/passwd"}).status_code == 404
    assert client.post("/api/seal", data={"issuer_id": "x"}).status_code == 422
    assert client.get("/api/sealed/NOTREAL.pdf").status_code == 404
    assert client.get("/api/nope").status_code == 404


def test_path_traversal_is_blocked(client):
    files, _ = forge(make_claim("A", "dengue", 8), "F2", "total_only", seed=2)
    check_id = upload(client, files).json()["id"]
    for name in ("..%2Fmedcore.db", ".hidden", "missing.pdf"):
        assert client.get(f"/api/checks/{check_id}/files/{name}").status_code == 404


def test_delete(client):
    files, _ = forge(make_claim("A", "typhoid", 8), "F2", "room_days", seed=2)
    check_id = upload(client, files).json()["id"]
    assert client.delete(f"/api/checks/{check_id}").status_code == 204
    assert client.get(f"/api/checks/{check_id}").status_code == 404


def test_verify_samples_and_sealed_preview(client):
    names = client.get("/api/verify-samples").json()
    assert names[0] == "1_genuine_sealed_lab_report.pdf" and len(names) == 5
    assert client.post(f"/api/verify-samples/{names[1]}").json()["seal"]["status"] == "altered"
    assert client.post("/api/verify-samples/..%2Fkeys%2Flog.json").status_code == 404
    lab = next(i for i in client.get("/api/issuers").json() if i["kind"] == "lab")
    doc_id = client.post("/api/seal", data={"issuer_id": lab["id"],
                                            "sample_file": "01_genuine_dengue/lab_report_2.pdf"}).json()["doc_id"]
    assert client.get(f"/api/sealed/{doc_id}/preview.png").headers["content-type"] == "image/png"


def test_admin_token_protects_registry_changes(tmp_path, demo_dir):
    client = TestClient(create_app(data_dir=tmp_path, database_url=f"sqlite:///{tmp_path / 'a.db'}",
                                   demo_dir=demo_dir, admin_token="s3cret"))
    assert client.get("/api/health").json()["admin_locked"] is True
    body = {"name": "Locked Clinic", "kind": "hospital", "address": "Vashi"}
    assert client.post("/api/issuers", json=body).status_code == 403
    assert client.post("/api/issuers", json=body, headers={"X-Admin-Token": "wrong"}).status_code == 403
    assert client.post("/api/issuers", json=body, headers={"X-Admin-Token": "s3cret"}).status_code == 201
    assert client.post("/api/issuers/locked-clinic/status", json={"status": "suspended"}).status_code == 403
    doc_id = client.get("/api/log").json()["entries"][0]["doc_id"]
    assert client.post(f"/api/log/{doc_id}/revoke", json={"reason": "x"}).status_code == 403
    # Sealing, verifying and claim checks stay open for the demo.
    assert client.post("/api/verify-samples/1_genuine_sealed_lab_report.pdf").status_code == 200
