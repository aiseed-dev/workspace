#!/bin/sh
# 蔵のバックアップ。xattr（権限の正）を落とさないことが要点（spec 4.2 運用の要点）。
# PocketBase の SQLite は、PB を停めて取るか、PB 管理画面のバックアップ機能を使うのが確実。
set -eu

DATA_ROOT="${1:?使い方: backup.sh データルート PBデータディレクトリ 保存先}"
PB_DATA="${2:?使い方: backup.sh データルート PBデータディレクトリ 保存先}"
DEST="${3:?使い方: backup.sh データルート PBデータディレクトリ 保存先}"

STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$DEST"

# --xattrs-include='user.*' がないと user.* は保存されない（tar の既定は trusted/security 向け）
tar --xattrs --xattrs-include='user.*' -czf "$DEST/workspace-$STAMP.tar.gz" \
    -C "$(dirname "$DATA_ROOT")" "$(basename "$DATA_ROOT")"
tar -czf "$DEST/pocketbase-$STAMP.tar.gz" \
    -C "$(dirname "$PB_DATA")" "$(basename "$PB_DATA")"

echo "保存した:"
echo "  $DEST/workspace-$STAMP.tar.gz"
echo "  $DEST/pocketbase-$STAMP.tar.gz"
echo "復元（xattr ごと）: tar --xattrs --xattrs-include='user.*' -xzf workspace-$STAMP.tar.gz"
