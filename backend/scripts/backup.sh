#!/usr/bin/env bash
# 数据库备份（docs/09 P0-3）
# 用法：DATABASE_URL="mysql+pymysql://user:pass@host:3306/nswap" ./scripts/backup.sh [输出目录]
set -euo pipefail

OUT_DIR="${1:-./backups}"
mkdir -p "$OUT_DIR"
STAMP=$(date +%Y%m%d_%H%M%S)
FILE="$OUT_DIR/nswap_${STAMP}.sql.gz"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "错误：请设置 DATABASE_URL（mysql+pymysql://user:pass@host:port/db）" >&2
  exit 1
fi

# 解析 DSN：mysql+pymysql://user:pass@host:port/db
DSN="${DATABASE_URL#mysql+pymysql://}"
CRED="${DSN%%@*}"; HOSTPART="${DSN#*@}"
DB="${HOSTPART##*/}"; HOSTPORT="${HOSTPART%%/*}"
DB_USER="${CRED%%:*}"; DB_PASS="${CRED#*:}"
DB_HOST="${HOSTPORT%%:*}"; DB_PORT="${HOSTPORT##*:}"

echo "备份 $DB@$DB_HOST:$DB_PORT → $FILE"
mysqldump \
  --host="$DB_HOST" --port="$DB_PORT" --user="$DB_USER" --password="$DB_PASS" \
  --single-transaction --routines --triggers --default-character-set=utf8mb4 \
  "$DB" | gzip > "$FILE"

echo "完成：$FILE（$(du -h "$FILE" | cut -f1)）"
echo "提示：生产环境请将备份上传至对象存储，并保留 ≥7 天（云托管 MySQL 建议同时开启控制台自动备份）"
