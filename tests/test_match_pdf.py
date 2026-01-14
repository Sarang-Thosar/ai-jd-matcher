from fastapi.testclient import TestClient
from api.main import app
from io import BytesIO

client = TestClient(app)

def test_match_pdf_invalid_file():
    files = {
        "resume_pdf": ("resume.pdf", BytesIO(b"not a pdf"), "application/pdf"),
        "jd_pdf": ("jd.pdf", BytesIO(b"not a pdf"), "application/pdf"),
    }

    response = client.post("/match-pdf", files=files)

    assert response.status_code in [400, 500]
