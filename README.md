<p align="center">
  <img src="app/static/logo/logo-256.png" width="112" alt="Ownfoil">
</p>

<h1 align="center">Ownfoil</h1>

<p align="center">
  <b>Your Switch library, as a store you run at home.</b><br>
  A fork of Ownfoil with a store-style web interface and fixes for data loss and security.
</p>

<p align="center">
  <b><a href="#try-it">Get started</a></b> ·
  <a href="Usage.md">Usage</a> ·
  <a href="https://github.com/a1ex4/ownfoil">Upstream</a> ·
  <a href="https://github.com/cobanov/ownfoil/issues">Issues</a>
</p>

> **This is a fork, and it goes its own way.** It started from
> [a1ex4/ownfoil](https://github.com/a1ex4/ownfoil) 2.5.0 and adds a new library and game page in
> the browser, plus the fixes listed below. The shop your Switch talks to, the settings file and the
> database are unchanged, so you can move between this fork and upstream in either direction.

Ownfoil reads the Switch games, updates and DLC in your folders, works out what each file is and
what is missing, and serves them to Tinfoil, Sphaira and CyberFoil on your network. This fork keeps
all of that and makes the browser side feel like a store.

<p align="center">
  <a href="docs/screenshots/library.jpg"><img src="docs/screenshots/library.jpg" width="49%" alt="The library: the game under the mouse fills the top of the page, the covers sit below with search, filters and sorting"></a>
  <a href="docs/screenshots/title.jpg"><img src="docs/screenshots/title.jpg" width="49%" alt="A game page: artwork, facts, description, what you own and the screenshots, on one screen"></a>
  <br><sub>The library and a game page on a 16-inch laptop. Click to zoom.</sub>
</p>

<p align="center">
  <a href="docs/screenshots/library-phone.jpg"><img src="docs/screenshots/library-phone.jpg" width="24%" alt="The library on a phone"></a>
  <a href="docs/screenshots/title-phone.jpg"><img src="docs/screenshots/title-phone.jpg" width="24%" alt="A game page on a phone"></a>
  <br><sub>And on a phone.</sub>
</p>

## A store for the games you own

- **The library is a storefront.** The game under your mouse fills the top of the page with its
  artwork and a short description, and a click opens it. The first row of covers still shows
  without scrolling. Below sit the covers, with search, genre
  filters, **Update available** and **Missing DLC**, and sorting by name, release date or size.
- **One screen per game.** A game page fits a 16-inch laptop screen without scrolling: artwork,
  genres, players, release date, the description, the screenshots and what you own. A long
  description opens in full on request, and screenshots open full size and step with the arrow keys.
- **It tells you what is missing.** Every game says whether you have the base game, whether your
  update is the newest one and how many of its DLC you own, with the full list one click away.
- **It works on a phone.** Both pages fit a narrow screen; there the filters become one row you
  swipe.
- **It stays on your network.** The typeface, Archivo, is served by Ownfoil itself, not by a font
  service.
- **Everything else is Ownfoil.** Files are identified by decrypting them or by their names, the
  library can be organized, verified and compressed, several users can sign in, and Tinfoil, Sphaira
  and CyberFoil get a shop.

## What this fork fixes

Found in a review of the whole code base. Every fix comes with a test.

**So you do not lose data**

- A disk that is not mounted at startup stays in the settings, and an empty mount point no longer
  deletes every file record (verification results, download counts, dates added).
- Removing empty folders never removes the library folder itself.
- **Delete older updates** keeps an old update until a sound copy of the newest one is on disk:
  identified from the file itself (this needs console keys), not found broken, and done processing.
- One folder Ownfoil cannot read, such as `lost+found`, no longer stops the whole scan.
- A scan no longer stops halfway when a file is copied in while it runs.
- A worker that dies, for example out of memory while compressing, is replaced, and its task no
  longer blocks the queue forever.
- Two workers no longer write the same artwork file at once and leave a broken image behind.

**So nobody gets in who should not**

- Deleting a user ends their sessions. Before, the next user created could take over a deleted
  user's old sign-in, even as an admin. Changing a password signs out old sessions too.
- The last admin cannot be deleted. Deleting it used to turn sign-in off for everyone.
- A file name can no longer run code on the Tasks page.
- After sign-in, Ownfoil only sends you to pages on this server.
- Sign-in no longer tells which user names exist, and every wrong password costs a second.
- Cookies are `SameSite=Lax`, an uploaded keys file is checked before it replaces the old one, and
  live updates only answer pages from this server.
- Tinfoil's encryption key comes from a secure random source.

Moving to this fork signs everyone out once, because sessions now carry part of the password hash.

**So the page shows what is true**

- Homebrew games and ports whose IDs look like a DLC's, such as the Call of Duty 4 port, appear in
  the library.
- The browser no longer shows old data after a settings change or new artwork.
- A DLC you own in an older version counts as owned.
- Release dates show the right day in time zones west of UTC.
- **Read full description** appears whenever the text is cut, also when the font arrives late.
- On a desktop, every genre filter can be reached with a mouse.

## Try it

You need Docker and a folder of Switch games.

1. Get the code, and put your games folder in `docker-compose.yml` in place of `/your/game/directory`.
   ```sh
   git clone https://github.com/cobanov/ownfoil
   cd ownfoil
   docker compose up -d --build
   ```
2. Open `http://<server>:8465` and create an admin user under **Settings**. Until you do, sign-in is
   off and anyone who can reach the page can change your shop.
3. Upload your console keys (`prod.keys`) under **Settings → Titles**, then add your games folder
   under **Settings → Library → Paths**. Ownfoil scans it right away.
4. Open the **Setup** page and enter what it shows in Sphaira, Tinfoil or CyberFoil on your Switch.

To update, run `git pull && docker compose up -d --build`. Settings and the database stay in
`config/` and `data/`.

The organizer and compression are off until you turn them on, so Ownfoil does not change your
files. If you keep them off, mount the games read-only (`/your/game/directory:/games:ro`) to be
sure.

[Usage.md](Usage.md) describes every setting and client. [Install.md](Install.md) is upstream's
install guide: its Docker Hub, uv, Unraid, Proxmox and Helm routes install upstream, not this fork.

## Want to tinker?

Python, Flask and a GraphQL API (Strawberry) over SQLite, with plain HTML, CSS and JavaScript in the
browser. The store pages are `app/templates/index.html` and `app/templates/title.html`, with
`app/static/store.css` and `app/static/js/store.js`.

```sh
uv run --no-project --python 3.14 --with-requirements requirements.txt --with pytest pytest tests -q
```

To bring in upstream's changes:

```sh
git remote add upstream https://github.com/a1ex4/ownfoil
git fetch upstream && git merge upstream/develop
```

## Thanks

- [a1ex4](https://github.com/a1ex4) and the Ownfoil contributors, who wrote everything this fork
  stands on.
- [blawar](https://github.com/blawar) for Tinfoil, Fs, the nsz format and TitleDB,
  [nicoboss](https://github.com/nicoboss) for [nsz](https://github.com/nicoboss/nsz) and
  [seiya-dev](https://github.com/seiya-dev) for [NSTools](https://github.com/seiya-dev/NSTools).
- [Archivo](https://github.com/Omnibus-Type/Archivo) by Omnibus-Type (OFL) for the type.

---

AGPL-3.0, like upstream, see [LICENSE.md](LICENSE.md). Archivo keeps its OFL. No keys, firmware or
games are in this repository.

This project has no website and no downloads outside this repository. It is not affiliated with
Nintendo. "Nintendo Switch" is a trademark of Nintendo.
