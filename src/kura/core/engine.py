"""コアエンジン：ファイル操作と権限判定（spec 4.2・5 章）。

口（API・Flet）が二つでも、認可の判定は必ずここを通る（spec 4.4 v3.1）。
判定は当該ディレクトリの xattr だけで行い、祖先は見ない（traversal 決定）。

操作と要求ビットの対応（初期解釈、ファイルは入れ物の権限を受ける）：
- 一覧・読み取り・ダウンロード: 入れ物に r
- ファイルの作成・上書き・削除・移動: 入れ物に w（移動は両側）
- 子ディレクトリの作成・削除・移動: 親に a（移動は両親）
- ディレクトリの権限の閲覧・変更: そのディレクトリ自身に a
"""

import os
import shutil
from pathlib import Path

from . import paths, perms
from .errors import Conflict, NotFound, PermissionDenied
from .groups import GroupStore
from .links import LinkStore


class Engine:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.groups = GroupStore(self.root)
        self.links = LinkStore(self.root)

    # --- 判定 ---

    def bits(self, user_id: str, d: Path) -> set[str]:
        return perms.effective_bits(perms.read_perm(d), self.groups.groups_of(user_id))

    def _require(self, user_id: str, d: Path, bit: str) -> None:
        if bit not in self.bits(user_id, d):
            raise PermissionDenied(f"権限がない: {bit} on {paths.to_rel(self.root, d)!r}")

    def _dir(self, rel: str) -> Path:
        d = paths.resolve(self.root, rel)
        if not d.is_dir():
            raise NotFound(f"ディレクトリがない: {rel!r}")
        return d

    def _file(self, rel: str) -> Path:
        p = paths.resolve(self.root, rel)
        if p == self.root or not p.parent.is_dir():
            raise NotFound(f"場所がない: {rel!r}")
        return p

    # --- 一覧・入口 ---

    def list_dir(self, user_id: str, rel: str) -> dict:
        d = self._dir(rel)
        self._require(user_id, d, "r")
        dirs, files = [], []
        for entry in sorted(d.iterdir(), key=lambda p: p.name):
            child_rel = paths.to_rel(self.root, entry)
            if entry.name in paths.RESERVED_NAMES and d == self.root:
                continue
            if entry.is_dir():
                # 子ディレクトリは自分の xattr を持つ。r がなければ名前ごと見えない（v3.1）
                child_bits = self.bits(user_id, entry)
                if "r" in child_bits:
                    dirs.append({"name": entry.name, "path": child_rel,
                                 "bits": "".join(sorted(child_bits))})
            elif entry.is_file():
                st = entry.stat()
                files.append({"name": entry.name, "path": child_rel,
                              "size": st.st_size, "mtime": st.st_mtime,
                              "creator": perms.get_creator(entry)})
        return {"path": rel, "bits": "".join(sorted(self.bits(user_id, d))),
                "dirs": dirs, "files": files}

    def entry_points(self, user_id: str) -> list[dict]:
        """自分が見える場所の一覧（共有ドライブ型の入口、v3.1 帰結 2）。
        入口 = r を持ち、親には r を持たないディレクトリ。小規模前提で全走査。"""
        user_groups = self.groups.groups_of(user_id)
        entries = []
        for dirpath, dirnames, _ in os.walk(self.root):
            d = Path(dirpath)
            if d.is_symlink():
                dirnames.clear()
                continue
            readable = "r" in perms.effective_bits(perms.read_perm(d), user_groups)
            parent_readable = d != self.root and "r" in perms.effective_bits(
                perms.read_perm(d.parent), user_groups)
            if readable and not parent_readable:
                entries.append({"path": paths.to_rel(self.root, d) if d != self.root else "",
                                "bits": "".join(sorted(
                                    perms.effective_bits(perms.read_perm(d), user_groups)))})
        return sorted(entries, key=lambda e: e["path"])

    # --- ディレクトリ ---

    def mkdir(self, user_id: str, rel: str) -> None:
        p = self._file(rel)
        self._require(user_id, p.parent, "a")
        if p.exists():
            raise Conflict(f"既にある: {rel!r}")
        parent_perm = perms.read_perm(p.parent)
        p.mkdir()
        # 継承はしない。作成時に親の権限をコピーし、以後は独立（spec 5 章）
        perms.write_perm(p, parent_perm)
        perms.set_creator(p, user_id)

    def rmdir(self, user_id: str, rel: str, recursive: bool = False) -> None:
        d = self._dir(rel)
        if d == self.root:
            raise PermissionDenied("ルートは消せない")
        self._require(user_id, d.parent, "a")
        if recursive:
            shutil.rmtree(d)
        else:
            try:
                d.rmdir()
            except OSError as e:
                raise Conflict(f"空でない: {rel!r}") from e

    def get_perm(self, user_id: str, rel: str) -> dict[str, str]:
        d = self._dir(rel)
        self._require(user_id, d, "a")
        return perms.read_perm(d)

    def set_perm(self, user_id: str, rel: str, perm: dict[str, str]) -> None:
        d = self._dir(rel)
        self._require(user_id, d, "a")
        known = self.groups.load()
        for gid in perm:
            if gid not in known:
                raise NotFound(f"グループがない: {gid}")
        perms.write_perm(d, perm)

    # --- ファイル ---

    def file_path(self, user_id: str, rel: str) -> Path:
        """読み取り用に実パスを返す（ダウンロードは API 層がストリームする）。"""
        p = self._file(rel)
        # 権限を先に判定する——r のない人にファイルの有無を漏らさない
        self._require(user_id, p.parent, "r")
        if not p.is_file():
            raise NotFound(f"ファイルがない: {rel!r}")
        return p

    def write_file(self, user_id: str, rel: str, data: bytes) -> None:
        p = self._file(rel)
        self._require(user_id, p.parent, "w")
        if p.is_dir():
            raise Conflict(f"ディレクトリがある: {rel!r}")
        # atomic rename は inode を差し替えるため、上書きでも作成者を引き継ぐ
        creator = perms.get_creator(p) if p.exists() else None
        from .atomic import atomic_write

        atomic_write(p, data)
        perms.set_creator(p, creator or user_id)

    def delete_file(self, user_id: str, rel: str) -> None:
        p = self._file(rel)
        self._require(user_id, p.parent, "w")
        if not p.is_file():
            raise NotFound(f"ファイルがない: {rel!r}")
        p.unlink()

    def move(self, user_id: str, src_rel: str, dst_rel: str) -> None:
        src = self._file(src_rel)
        dst = self._file(dst_rel)
        if not src.exists():
            raise NotFound(f"ない: {src_rel!r}")
        if dst.exists():
            raise Conflict(f"移動先が既にある: {dst_rel!r}")
        if src == self.root or src in dst.parents:
            raise Conflict("自分自身の配下へは移動できない")
        bit = "a" if src.is_dir() else "w"
        self._require(user_id, src.parent, bit)
        self._require(user_id, dst.parent, bit)
        # rename は xattr（権限・作成者）ごと移る
        os.rename(src, dst)

    # --- 共有リンク ---

    def create_link(self, user_id: str, rel: str, perm: str,
                    expires_at: float | None = None) -> tuple[str, str]:
        p = self._file(rel)
        if not p.exists():
            raise NotFound(f"ない: {rel!r}")
        container = p if p.is_dir() else p.parent
        # 共有・招待を出せるのは管理（a）（spec 5 章）
        self._require(user_id, container, "a")
        return self.links.create(paths.to_rel(self.root, p), perm, user_id, expires_at)

    def open_link(self, token: str) -> tuple[Path, dict]:
        """トークンから対象の実パスを引く。権限判定はリンク自体が担う。"""
        link = self.links.resolve(token)
        if link is None:
            raise NotFound("リンクが無効")
        p = paths.resolve(self.root, link["target"])
        if not p.exists():
            raise NotFound("対象が消えている")
        return p, link

    def ics_feed(self, token: str) -> tuple[str, str]:
        """共有リンク（対象＝カレンダーのディレクトリ）から ICS 購読フィードを生成する。
        購読クライアントはヘッダ認証ができないため、認可は URL 内トークン＝リンクが担う。"""
        from .ics import merge_feed

        p, _link = self.open_link(token)
        if not p.is_dir():
            raise NotFound("カレンダーはディレクトリ")
        texts = [f.read_text(encoding="utf-8")
                 for f in sorted(p.iterdir())
                 if f.is_file() and f.suffix == ".ics"]
        return p.name, merge_feed(p.name, texts)

    # --- 初期化（CLI から）---

    def init_root(self, admin_user_id: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.groups.init(admin_user_id)
        from .groups import ADMIN_GROUP

        perms.write_perm(self.root, {ADMIN_GROUP: "rwa"})
