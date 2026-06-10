"""Workspace 層のエラー。API 層が HTTP ステータスに写す。"""


class KuraError(Exception):
    status = 500


class InvalidPath(KuraError):
    status = 400


class PermissionDenied(KuraError):
    status = 403


class NotFound(KuraError):
    status = 404


class Conflict(KuraError):
    status = 409


class GroupLimitExceeded(KuraError):
    """xattr の容量上限（ext4 既定 ≒ 4KB）。
    「このフォルダに設定できるグループ数の上限」という明確なエラーで断る（spec 7 章）。"""

    status = 507
