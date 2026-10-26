<p align="center">
  <img src="app/static/logo/logo-256.png" width="112" alt="Homefoil">
</p>

<h1 align="center">Homefoil</h1>

<p align="center">
  <b>Your Switch library, as a store you run at home.</b>
</p>

<p align="center">
  <b><a href="#install">Install</a></b> ·
  <a href="#add-it-to-your-switch">Add to Switch</a> ·
  <a href="https://github.com/a1ex4/ownfoil">Upstream</a> ·
  <a href="https://github.com/cobanov/homefoil/issues">Issues</a>
</p>

> A fork of [a1ex4/ownfoil](https://github.com/a1ex4/ownfoil), going its own way under a new name.
> Same shop, settings and database. New web interface and many fixes.

<p align="center">
  <a href="docs/screenshots/library.jpg"><img src="docs/screenshots/library.jpg" width="49%" alt="The library page"></a>
  <a href="docs/screenshots/title.jpg"><img src="docs/screenshots/title.jpg" width="49%" alt="A game page"></a>
</p>
<p align="center">
  <a href="docs/screenshots/library-phone.jpg"><img src="docs/screenshots/library-phone.jpg" width="24%" alt="The library on a phone"></a>
  <a href="docs/screenshots/title-phone.jpg"><img src="docs/screenshots/title-phone.jpg" width="24%" alt="A game page on a phone"></a>
</p>
<p align="center">
  <a href="docs/screenshots/setup.jpg"><img src="docs/screenshots/setup.jpg" width="49%" alt="The Setup page"></a>
  <a href="docs/screenshots/admin.jpg"><img src="docs/screenshots/admin.jpg" width="49%" alt="The admin settings"></a>
</p>

## What's new

- Store-style library. The top card cycles through your games; hover one to show it there.
- Search, genre filters, **Update available**, **Missing DLC** and sorting.
- One-screen game page: artwork, facts, screenshots, what you own.
- Setup page with copy-ready values for Sphaira, Tinfoil and CyberFoil.
- Admin pages rebuilt: one card per topic, one list of what needs attention.
- Works on phones.
- First start: log in with admin / admin, then pick a new password.
- No requests to outside services. Even the font is served locally.
- Everything else comes from Ownfoil: shop for Tinfoil, Sphaira and CyberFoil, file identification,
  organizing, verifying, compressing, several users.

## What this fork fixes

**Data**
- An unmounted disk no longer wipes the library.
- Empty-folder cleanup never deletes the library folder.
- Old updates stay until the new one is verified.
- One unreadable folder no longer stops the scan.
- A file copied in during a scan no longer stops it.
- A crashed worker is restarted.
- No more broken artwork from two workers writing at once.

**Security**
- Deleted users stay logged out.
- The last admin can't be deleted.
- File names can't run code on the Tasks page.
- Login only redirects inside Homefoil.
- Login doesn't reveal user names. Wrong passwords wait a second.
- SameSite cookies, checked key uploads, same-site live updates.
- Secure random key for Tinfoil.

**Display**
- Homebrew and ports, like Call of Duty 4, show in the library.
- No stale data after a settings or artwork change.
- An older owned DLC counts as owned.
- Release dates are right in every time zone.
- **Read full description** shows whenever text is cut.
- Every genre filter is reachable with a mouse.

Moving to this fork logs everyone out once.

## Install

You need Docker.

1. Get the code.
   ```sh
   git clone https://github.com/cobanov/homefoil
   cd homefoil
   ```
2. In `docker-compose.yml`, replace `/your/game/directory` with your games folder.
3. Add your console keys.
   ```sh
   mkdir -p config && cp /path/to/prod.keys config/keys.txt
   ```
4. Start it.
   ```sh
   docker compose up -d --build
   ```
5. Open `http://<server-ip>:8465`, log in with **admin** / **admin**.
6. Pick a new password. Your games show up after the first scan.

No keys yet? Upload them later in **Settings → Titles**.

Update with `git pull && docker compose up -d --build`.

## Add it to your Switch

The **Setup** page shows the exact values for your server.

**Sphaira** (recommended)
1. **Menu → Menus → Ownfoil**. Sphaira still calls it Ownfoil.
2. **Discover local servers**, pick your shop.

**Tinfoil**
1. **File Browser**, press **New**.
2. Fill in and save:

   | Field | Value |
   |---|---|
   | Protocol | `http` |
   | Host | your server's IP |
   | Port | `8465` |
   | Path | `/` |
   | Username, Password | your Homefoil user |
   | Title | anything |

**CyberFoil**
1. **Settings → Shop → Add new shop**.
2. Protocol `HTTP`, your server's IP, port `8465`, your Homefoil user.

More in [Usage.md](Usage.md).

## Want to tinker?

Flask, GraphQL and SQLite. Plain HTML, CSS and JS in the browser.

```sh
uv run --no-project --python 3.14 --with-requirements requirements.txt --with pytest pytest tests -q
```

Pull upstream changes with `git fetch upstream && git merge upstream/develop`.

## Thanks

- [a1ex4](https://github.com/a1ex4) and the Ownfoil contributors.
- [blawar](https://github.com/blawar) for Tinfoil, nsz and TitleDB.
- [nicoboss](https://github.com/nicoboss) for [nsz](https://github.com/nicoboss/nsz),
  [seiya-dev](https://github.com/seiya-dev) for [NSTools](https://github.com/seiya-dev/NSTools).
- [Archivo](https://github.com/Omnibus-Type/Archivo) (OFL) for the type.

---

AGPL-3.0, see [LICENSE.md](LICENSE.md). No keys, firmware or games in this repository.
Not affiliated with Nintendo.
