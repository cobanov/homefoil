"""First run: the default admin/admin account, and a web login forced to replace its password."""
import base64

import pytest
from flask import template_rendered

import auth
from auth import create_or_update_user, init_users
from db import User, db


@pytest.fixture
def default_admin(shop_app):
    """The fixture shop with its admin still on the default password."""
    with shop_app.app.app_context():
        create_or_update_user("admin", "admin", admin_access=True, shop_access=True, backup_access=True)
    return shop_app


def logged_in(shop, password="admin", **form):
    client = shop.app.test_client()
    response = client.post("/login", data={"user": "admin", "password": password, **form})
    return client, response


def login_context(shop):
    """The context the login page was rendered with."""
    seen = []
    with template_rendered.connected_to(lambda sender, template, context, **extra: seen.append(context),
                                        shop.app):
        assert shop.client.get("/login").status_code == 200
    return seen[0]


def test_init_users_creates_the_default_admin_only_when_there_are_no_users(shop_app):
    with shop_app.app.app_context():
        before = User.query.count()
        init_users(shop_app.app)
        assert User.query.count() == before  # an install that has users is left alone

        User.query.delete()
        db.session.commit()
        init_users(shop_app.app)
        admin = User.query.one()
        assert (admin.user, admin.admin_access, admin.shop_access, admin.backup_access) == ("admin", True, True, True)
        assert auth.is_default_password(admin.password)


def test_the_login_page_hints_at_the_default_account_only_while_it_is_active(shop_app, default_admin):
    assert login_context(default_admin)["default_password_active"] is True
    with shop_app.app.app_context():
        create_or_update_user("admin", "adminpass2", admin_access=True, shop_access=True)
    assert login_context(shop_app)["default_password_active"] is False


@pytest.mark.parametrize("next_url, location", [
    ("/admin/settings", "/password?next=/admin/settings"),
    ("", "/password"),
])
def test_a_default_password_login_goes_to_the_change_page(default_admin, next_url, location):
    _, response = logged_in(default_admin, next=next_url)
    assert response.status_code == 302
    assert response.headers["Location"].replace("%2F", "/") == location


@pytest.mark.parametrize("next_url, location", [
    ("/admin", "/login?failed=1&next=/admin"),
    ("", "/login?failed=1"),
])
def test_a_failed_login_says_so_and_keeps_next(shop_app, next_url, location):
    _, response = logged_in(shop_app, password="wrongpass1", next=next_url)
    assert response.headers["Location"].replace("%2F", "/") == location


def test_a_default_password_session_reaches_only_the_change_page(default_admin):
    client, _ = logged_in(default_admin)

    page = client.get("/admin/settings")
    assert page.status_code == 302
    assert page.headers["Location"].replace("%2F", "/") == "/password?next=/admin/settings"
    assert client.get("/").headers["Location"] == "/password?next=/"

    api = client.get("/api/settings")
    assert api.status_code == 403 and api.get_json()["error"]

    assert client.get("/password").status_code == 200
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/logout").headers["Location"] == "/"


def test_shop_clients_on_the_default_account_are_not_redirected(default_admin):
    """Basic Auth, not the session: the Switch keeps working before the password is changed."""
    token = base64.b64encode(b"admin:admin").decode()
    response = default_admin.client.get("/", headers={"User-Agent": "Sphaira/1.0",
                                                      "Authorization": f"Basic {token}"})
    assert response.status_code == 200
    assert "Location" not in response.headers


@pytest.mark.parametrize("password, confirm, error", [
    ("newpass1", "newpass2", "The passwords do not match."),
    ("admin", "admin", "Choose a password other than the default one."),
    ("bad/pass", "bad/pass", "Password contains invalid characters"),
    ("", "", "Password cannot be empty"),
])
def test_the_new_password_is_checked(default_admin, password, confirm, error):
    client, _ = logged_in(default_admin)
    response = client.post("/password", data={"password": password, "confirm": confirm})
    assert response.status_code == 200
    assert error in response.get_data(as_text=True)
    assert client.get("/admin/settings").status_code == 302  # still forced


def test_changing_the_password_keeps_the_session_and_lifts_the_guard(default_admin):
    client, _ = logged_in(default_admin)
    response = client.post("/password", data={"password": "newpass1", "confirm": "newpass1",
                                              "next": "/admin/settings"})
    assert response.status_code == 302 and response.headers["Location"] == "/admin/settings"

    assert client.get("/admin").headers["Location"] == "/admin/settings"  # no longer sent to /password
    assert client.get("/api/users").status_code == 200
    assert logged_in(default_admin)[1].headers["Location"].startswith("/login?failed=1")
    assert logged_in(default_admin, password="newpass1")[1].headers["Location"] == "/"


def test_any_logged_in_user_can_change_their_password(shop_app):
    client = shop_app.app.test_client()
    client.post("/login", data={"user": "shopper", "password": "shoppass1"})
    assert "default password" not in client.get("/password").get_data(as_text=True)
    wrong = client.post("/password", data={"current": "nope", "password": "shoppass2", "confirm": "shoppass2"})
    assert wrong.status_code == 200 and "current password is wrong" in wrong.get_data(as_text=True)
    response = client.post("/password", data={"current": "shoppass1", "password": "shoppass2",
                                              "confirm": "shoppass2", "next": "https://evil.example/"})
    assert response.headers["Location"] == "/"
    with shop_app.app.app_context():
        assert auth.verify_password(User.query.filter_by(user="shopper").one().password, "shoppass2")
