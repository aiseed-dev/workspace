import threading

from kura.core.atomic import atomic_write, locked


def test_atomic_write_replaces(tmp_path):
    p = tmp_path / "f"
    atomic_write(p, b"one")
    atomic_write(p, b"two")
    assert p.read_bytes() == b"two"
    # 一時ファイルが残っていない
    assert [f.name for f in tmp_path.iterdir()] == ["f"]


def test_locked_mutual_exclusion(tmp_path):
    lock = tmp_path / "l"
    counter = {"n": 0}

    def bump():
        for _ in range(200):
            with locked(lock):
                n = counter["n"]
                counter["n"] = n + 1

    threads = [threading.Thread(target=bump) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert counter["n"] == 800
