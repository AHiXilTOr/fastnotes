import pytest
from fastapi.testclient import TestClient
from main import app
from database import Base, engine

@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)

def test_register_user(client):
    response = client.post("/register", json={"username": "testuser", "password": "testpassword"})
    if response.status_code == 400:
        assert response.json().get("detail") == "Имя пользователя уже зарегистрировано"
    else:
        assert response.status_code == 200
        assert response.json().get("username") == "testuser"

def test_login_for_access_token(client):
    client.post("/register", json={"username": "testuser", "password": "testpassword"})
    response = client.post("/token", data={"username": "testuser", "password": "testpassword"})
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json().get("token_type") == "bearer"

def test_create_note_for_user(client):
    client.post("/register", json={"username": "testuser", "password": "testpassword"})
    response = client.post("/token", data={"username": "testuser", "password": "testpassword"})
    access_token = response.json().get("access_token")
    response = client.post("/notes/", json={"title": "Test Note", "content": "This is a test note"}, headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json().get("title") == "Test Note"

def test_read_note_for_user(client):
    client.post("/register", json={"username": "testuser", "password": "testpassword"})
    response = client.post("/token", data={"username": "testuser", "password": "testpassword"})
    access_token = response.json().get("access_token")
    create_response = client.post("/notes/", json={"title": "Test Note", "content": "This is a test note"}, headers={"Authorization": f"Bearer {access_token}"})
    note_id = create_response.json().get("id")
    response = client.get(f"/notes/{note_id}", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json().get("title") == "Test Note"

def test_update_note_for_user(client):
    client.post("/register", json={"username": "testuser", "password": "testpassword"})
    response = client.post("/token", data={"username": "testuser", "password": "testpassword"})
    access_token = response.json().get("access_token")
    create_response = client.post("/notes/", json={"title": "Test Note", "content": "This is a test note"}, headers={"Authorization": f"Bearer {access_token}"})
    note_id = create_response.json().get("id")
    response = client.put(f"/notes/{note_id}", json={"title": "Updated Note", "content": "This is an updated test note"}, headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json().get("title") == "Updated Note"

def test_delete_note_for_user(client):
    client.post("/register", json={"username": "testuser", "password": "testpassword"})
    response = client.post("/token", data={"username": "testuser", "password": "testpassword"})
    access_token = response.json().get("access_token")
    create_response = client.post("/notes/", json={"title": "Test Note", "content": "This is a test note"}, headers={"Authorization": f"Bearer {access_token}"})
    note_id = create_response.json().get("id")
    response = client.delete(f"/notes/{note_id}", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json().get("detail") == "Заметка удалена"
