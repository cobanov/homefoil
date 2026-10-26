"""Login, session and admin-endpoint hardening: who a cookie or a request can claim to be."""
import base64
import io
import sys
import time

import pytest
from flask import request

import auth
from auth import create_or_update_user
from capture.fixture import PASSWORDS, UNKNOWN_USER, WRONG_PASSWORD
from db import User


def logged_in(shop, user, password=None, **form):
    client = shop.app.test_client()
    response = client.post("/login", data={"user": user, "password": password or PASSWORDS[user],
                                           **form})
    return client, response


def user_named(shop, name):
    with shop.app.app_context():
        return User.query.filter_by(user=name).first()


def test_a_deleted_users_cookie_does_not_log_in_as_the_next_user_with_its_id(shop_app):
    with shop_app.app.app_context():
        create_or_update_user("temp", "temppass1", shop_access=True)
    temp_id = user_named(shop_app, "temp").id
    stale, _ = logged_in(shop_app, "temp", "temppass1")
    admin, _ = logged_in(shop_app, "admin")

    assert admin.delete("/api/user", json={"user_id": temp_id}).json["success"]
    with shop_app.app.app_context():
        create_or_update_user("boss", "bosspass1", admin_access=True)
    assert user_named(shop_app, "boss").id == temp_id  # SQLite handed the id out again

    assert stale.get("/api/users").status_code != 200


def test_a_session_needs_the_password_it_was_made_with(shop_app):
    from app import load_user

    with shop_app.app.app_context():
        user = User.query.filter_by(user="shopper").first()
        old_id = user.get_id()
        assert load_user(old_id) == user
        assert load_user(str(user.id)) is None  # a cookie from before the hash fragment
        create_or_update_user("shopper", "newpass1", shop_access=True)
        assert load_user(old_id) is None


def test_the_last_admin_cannot_be_deleted(shop_app):
    admin, _ = logged_in(shop_app, "admin")
    admin_id = user_named(shop_app, "admin").id

    response = admin.delete("/api/user", json={"user_id": admin_id}).json
    assert not response["success"] and response["error"]
    assert user_named(shop_app, "admin") is not None

    with shop_app.app.app_context():
        create_or_update_user("second", "secondpass1", admin_access=True)
    assert admin.delete("/api/user", json={"user_id": admin_id}).json["success"]


@pytest.mark.parametrize("next_url, location", [
    ("/settings", "/settings"),
    ("", "/"),
    ("https://evil.example/", "/"),
    ("//evil.example/", "/"),
    ("/\\evil.example/", "/"),
    ("/\t/evil.example/", "/"),
])
def test_login_only_follows_next_to_a_local_path(shop_app, next_url, location):
    _, response = logged_in(shop_app, "shopper", next=next_url, remember="on")

    assert response.status_code == 302
    assert response.headers["Location"] == location
    cookies = response.headers.getlist("Set-Cookie")
    assert len(cookies) == 2 and all("SameSite=Lax" in c for c in cookies)


def basic(user, password):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}


def test_an_unknown_user_and_a_wrong_password_fail_alike_and_slowly(shop_app, monkeypatch):
    monkeypatch.setattr(auth, "LOGIN_FAILURE_DELAY", 0.2)
    results = []
    for user in (UNKNOWN_USER, "shopper"):
        with shop_app.app.test_request_context(headers=basic(user, WRONG_PASSWORD)):
            start = time.monotonic()
            results.append(auth.basic_auth(request))
            assert time.monotonic() - start >= 0.2

    assert results[0] == results[1] == (False, "Invalid username or password.", None)


def test_an_invalid_keys_upload_keeps_the_current_keys(shop_app, tmp_path, monkeypatch):
    keys_file = tmp_path / "keys.txt"
    keys_file.write_text("current keys\n")
    monkeypatch.setattr(sys.modules["app"], "KEYS_FILE", str(keys_file))
    admin, _ = logged_in(shop_app, "admin")

    response = admin.post("/api/upload", content_type="multipart/form-data",
                          data={"file": (io.BytesIO(b"not keys\n"), "prod.keys")})

    assert not response.json["success"]
    assert keys_file.read_text() == "current keys\n"
    assert sorted(p.name for p in tmp_path.iterdir() if p.name.startswith("keys")) == ["keys.txt"]


@pytest.mark.parametrize("origin, served", [
    (None, True),
    ("http://shop.local", True),
    ("http://evil.example", False),
])
def test_the_realtime_socket_refuses_a_foreign_origin(shop_app, monkeypatch, origin, served):
    import realtime

    calls = []
    monkeypatch.setattr(realtime, "serve", lambda ws, topics: calls.append(topics))
    view = shop_app.app.view_functions["realtime_ws"].__wrapped__  # past the handshake
    headers = {"Origin": origin} if origin else {}
    with shop_app.app.test_request_context("/api/ws", base_url="http://shop.local",
                                           headers=headers):
        view(None)

    assert bool(calls) == served
