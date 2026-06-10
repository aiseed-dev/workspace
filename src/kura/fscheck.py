"""実機検証（spec 7 章）：xattr の実効上限と、バックアップでの xattr 保全。

配る先のファイルシステムは様々なので、検証は配布物に同梱して現場で実行できる形にする。
- ext4 既定では全 xattr 合計 ≒ 4KB。perm + creator 同居で何グループまで入るかを実測する
- 超過（ENOSPC）は setxattr が失敗するだけで中途半端な状態は生まれないことを確かめる
- tar --xattrs / rsync -X で user.* xattr が落ちないことを確かめる
"""

import errno
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .core.perms import CREATOR_XATTR, PERM_XATTR


def _perm_json(n_groups: int) -> bytes:
    perm = {f"g_{i:08x}": "rwa" for i in range(n_groups)}
    return json.dumps(perm, separators=(",", ":")).encode()


def measure_group_capacity(base: Path) -> dict:
    """perm + creator 同居で、一ディレクトリに何グループまで持てるかを二分探索で実測。"""
    with tempfile.TemporaryDirectory(dir=base) as tmp:
        d = Path(tmp) / "probe"
        d.mkdir()
        os.setxattr(d, CREATOR_XATTR, b"u_0123456789abcde")

        def fits(n: int) -> bool:
            try:
                os.setxattr(d, PERM_XATTR, _perm_json(n))
                return True
            except OSError as e:
                if e.errno == errno.ENOSPC:
                    return False
                raise

        if not fits(1):
            return {"capacity": 0, "atomic_on_overflow": None}

        lo, hi = 1, 2
        while fits(hi):
            lo, hi = hi, hi * 2
            if hi > 1_000_000:
                return {"capacity": None, "atomic_on_overflow": None,
                        "note": "上限に当たらない（ea_inode 等で実質無制限）"}
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if fits(mid):
                lo = mid
            else:
                hi = mid

        # 超過失敗の後も、最後に成功した値が無傷で読めること（中途半端な状態がない）
        os.setxattr(d, PERM_XATTR, _perm_json(lo))
        overflow_failed = not fits(hi)
        intact = json.loads(os.getxattr(d, PERM_XATTR)) == json.loads(_perm_json(lo))
        return {"capacity": lo, "atomic_on_overflow": overflow_failed and intact}


def _make_sample(src: Path) -> None:
    d = src / "サンプル"
    d.mkdir(parents=True)
    os.setxattr(d, PERM_XATTR, b'{"g_abc":"rwa","g_def":"r"}')
    f = d / "f.txt"
    f.write_bytes(b"x")
    os.setxattr(f, CREATOR_XATTR, b"u_1")


def _xattrs_survive(dst: Path) -> bool:
    d = dst / "サンプル"
    try:
        return (
            os.getxattr(d, PERM_XATTR) == b'{"g_abc":"rwa","g_def":"r"}'
            and os.getxattr(d / "f.txt", CREATOR_XATTR) == b"u_1"
        )
    except OSError:
        return False


def check_tar(base: Path) -> bool | None:
    """tar --xattrs での往復で user.* xattr が保全されるか。tar がなければ None。"""
    if shutil.which("tar") is None:
        return None
    with tempfile.TemporaryDirectory(dir=base) as tmp:
        src, dst = Path(tmp) / "src", Path(tmp) / "dst"
        _make_sample(src)
        dst.mkdir()
        archive = Path(tmp) / "a.tar"
        subprocess.run(
            ["tar", "--xattrs", "--xattrs-include=user.*", "-cf", archive,
             "-C", src, "."],
            check=True, capture_output=True)
        subprocess.run(
            ["tar", "--xattrs", "--xattrs-include=user.*", "-xf", archive,
             "-C", dst],
            check=True, capture_output=True)
        return _xattrs_survive(dst)


def check_rsync(base: Path) -> bool | None:
    """rsync -X で user.* xattr が保全されるか。rsync がなければ None。"""
    if shutil.which("rsync") is None:
        return None
    with tempfile.TemporaryDirectory(dir=base) as tmp:
        src, dst = Path(tmp) / "src", Path(tmp) / "dst"
        _make_sample(src)
        subprocess.run(["rsync", "-aX", f"{src}/", f"{dst}/"],
                       check=True, capture_output=True)
        return _xattrs_survive(dst)


def run(base: Path) -> dict:
    cap = measure_group_capacity(base)
    return {
        "path": str(base),
        "group_capacity_per_dir": cap["capacity"],
        "atomic_on_overflow": cap["atomic_on_overflow"],
        "tar_xattrs_ok": check_tar(base),
        "rsync_X_ok": check_rsync(base),
    }


def report(base: Path) -> int:
    r = run(base)
    label = {True: "OK", False: "NG", None: "確認できず（コマンドなし or 上限なし）"}
    print(f"検査対象: {r['path']}")
    cap = r["group_capacity_per_dir"]
    print(f"一ディレクトリのグループ上限（perm + creator 同居）: "
          f"{cap if cap is not None else '実質無制限'}")
    print(f"上限超過時の原子性（失敗しても無傷）: {label[r['atomic_on_overflow']]}")
    print(f"tar --xattrs の保全: {label[r['tar_xattrs_ok']]}")
    print(f"rsync -X の保全: {label[r['rsync_X_ok']]}")
    ok = (r["atomic_on_overflow"] is not False
          and r["tar_xattrs_ok"] is not False
          and r["rsync_X_ok"] is not False)
    if isinstance(cap, int) and cap < 30:
        print("警告: 上限が小さい。tune2fs -O ea_inode を検討（spec 7 章）")
    return 0 if ok else 1
