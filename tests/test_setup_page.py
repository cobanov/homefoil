"""The Setup page shows one tab per enabled client, and local or remote details by where it is opened from."""

import pytest

from settings import set_shop_settings

ALL_CLIENTS = {name: {"enabled": True} for name in ("tinfoil", "sphaira", "cyberfoil")}
NO_CLIENTS = {name: {"enabled": False} for name in ("tinfoil", "sphaira", "cyberfoil")}


@pytest.fixture
def client(shop_app):
    return shop_app.client


def page(client, host="localhost"):
    response = client.get("/setup", base_url=f"http://{host}")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_every_enabled_client_gets_a_tab(client):
    set_shop_settings({"public": True, "host": "shop.example.com", "clients": ALL_CLIENTS})
    html = page(client)
    for tab in ("sphaira", "tinfoil", "cyberfoil", "browser"):
        assert f'id="su-tab-{tab}"' in html
    # Opened from the LAN: each address-based client offers local and remote.
    assert 'id="net-tinfoil-local"' in html
    assert 'data-copy="https://shop.example.com"' in html
    # A public shop asks the file-list clients for no login.
    assert html.count("Your password") == 1  # only Sphaira's own menu, since an admin exists


def test_sphaira_alone_needs_no_picker(client):
    set_shop_settings({"public": True, "clients": NO_CLIENTS})
    html = page(client)
    assert 'role="tablist"' not in html
    assert 'id="su-sphaira"' in html
    assert "su-tab-tinfoil" not in html


def test_opened_from_the_remote_host_shows_only_remote(client):
    set_shop_settings({"public": True, "host": "shop.example.com", "clients": ALL_CLIENTS})
    html = page(client, host="shop.example.com")
    assert 'id="net-tinfoil-local"' not in html
    assert " - Local" not in html
    assert 'data-copy="shop.example.com"' in html
