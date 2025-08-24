from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)

resp = client.post(
    "/api/v1/message",
    json={"message": "What are the fees of the Maquininha Smart?", "user_id": "u1"},
)
print("fees status:", resp.status_code)
print("fees body:", resp.text)

resp2 = client.post(
    "/api/v1/message",
    json={"message": "I can't sign in to my account.", "user_id": "u2"},
)
print("support status:", resp2.status_code)
print("support body:", resp2.text)
