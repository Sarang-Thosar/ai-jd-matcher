from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_match_success(monkeypatch):
    # Mock Mistral calls
    monkeypatch.setattr(
        "api.main.generate_explanation",
        lambda *args, **kwargs: "mock explanation"
    )

    monkeypatch.setattr(
        "api.main.generate_interview_questions",
        lambda *args, **kwargs: "mock questions"
    )

    payload = {
        "resume_text": "Python developer with ML experience " * 5,
        "jd_text": "Looking for Python ML engineer " * 5
    }

    response = client.post("/match", json=payload)

    assert response.status_code == 200

    data = response.json()
    assert "match_percentage" in data
    assert data["explanation"] == "mock explanation"
    assert data["interview_questions"] == "mock questions"

def test_match_validation_error():
    payload = {
        "resume_text": "too short",
        "jd_text": "too short"
    }

    response = client.post("/match", json=payload)

    assert response.status_code == 422
