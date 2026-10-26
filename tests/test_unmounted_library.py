"""A library whose disk is missing, empty or racing the watcher never loses its rows or its root."""
import os
import types

import pytest

import library
import tasks
from db import db, Files, Libraries, create_file, remove_missing_files_from_db
from utils import delete_empty_folders

from app import create_app


@pytest.fixture
def env(tmp_path, monkeypatch):
    app = create_app(f"sqlite:///{tmp_path/'test.db'}")
    ctx = app.app_context()
    ctx.push()
    db.create_all()
    enqueued = []
    monkeypatch.setattr(tasks, "enqueue_task", lambda name, data=None, **kw: enqueued.append(name))

    def add_library(name, files=(), on_disk=True):
        root = tmp_path / name
        if on_disk:
            root.mkdir()
        lib = Libraries(path=str(root))
        db.session.add(lib)
        db.session.commit()
        for f in files:
            db.session.add(Files(library_id=lib.id, filepath=str(root / f), filename=f))
        db.session.commit()
        return root

    yield types.SimpleNamespace(app=app, add_library=add_library, enqueued=enqueued)
    ctx.pop()


def test_boot_keeps_a_library_whose_disk_is_not_mounted(env):
    root = env.add_library("unmounted", ["Game.nsp"], on_disk=False)
    watched = []
    watcher = types.SimpleNamespace(add_directory=watched.append, remove_directory=watched.remove)

    library.init_libraries(env.app, watcher, [str(root)])

    assert [lib.path for lib in Libraries.query.all()] == [str(root)]
    assert Files.query.count() == 1
    assert "remove_library" not in env.enqueued


@pytest.mark.parametrize("on_disk", [False, True], ids=["root missing", "root empty"])
def test_missing_files_cleanup_skips_an_unmounted_library(env, on_disk):
    env.add_library("unmounted", ["Game.nsp"], on_disk=on_disk)
    mounted = env.add_library("mounted", ["Gone.nsp"])
    (mounted / "Kept.nsp").write_bytes(b"x")

    remove_missing_files_from_db()

    assert [f.filename for f in Files.query.all()] == ["Game.nsp"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads every folder")
def test_missing_files_cleanup_keeps_files_in_an_unreadable_folder(env):
    root = env.add_library("games", ["Title/Game.nsp"])
    (root / "Title").mkdir()
    (root / "Title" / "Game.nsp").write_bytes(b"x")
    (root / "Title").chmod(0)
    try:
        remove_missing_files_from_db()
    finally:
        (root / "Title").chmod(0o755)

    assert Files.query.count() == 1


def test_delete_empty_folders_keeps_the_root(tmp_path):
    (tmp_path / "Title" / "Empty").mkdir(parents=True)

    delete_empty_folders(str(tmp_path))

    assert tmp_path.is_dir() and os.listdir(tmp_path) == []


def test_scan_survives_a_file_the_watcher_inserted_meanwhile(env, monkeypatch):
    root = env.add_library("games", ["Game.nsp"])
    (root / "Game.nsp").write_bytes(b"x")
    # The scan's snapshot of known paths predates the watcher's insert.
    monkeypatch.setattr(tasks, "get_library_file_paths", lambda library_id: [])

    tasks.scan_library_task(str(root))

    assert Files.query.count() == 1
    assert "remove_missing_files" in env.enqueued
    info = {"filedir": str(root), "filename": "Game.nsp", "extension": "nsp",
            "size": 1, "mtime": 0, "compressed": False}
    assert create_file(Libraries.query.one().id, str(root / "Game.nsp"), info) is None
