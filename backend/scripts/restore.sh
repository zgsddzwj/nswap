#!/usr/bin/env bash
# 数据库恢复（docs/09 P0-3）——危险操作，需输入 YES 确认
# 用法：DATABASE_URL="mysql+pymysql://user:pass@host:3306/nswap" ./scripts/restore.sh backups/nswap_xxx.sql.gz
set -euo pipefail

FILE="${1:-}"
if [[ -z "$FILE" || ! -f "$FILE" ]]; then
  echo "用法：DATABASE_URL=... $0 <备份文件.sql.gz>" >&2
  exit 1
fi
if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "错误：请设置 DATABASE_URL" >&2
  exit 1
fi

DSN="${DATABASE_URL#mysql+pymysql://}"
CRED="${DSN%%@*}"; HOSTPART="${DSN#*@}"
DB="${HOSTPART##*/}"; HOSTPORT="${HOSTPART%%/*}"
DB_USER="${CRED%%:*}"; DB_PASS="${CRED#*:}"
DB_HOST="${HOSTPORT%%:*}"; DB_PORT="${HOSTPORT##*:}"

echo "警告：即将用 $FILE 覆盖数据库 $DB@$DB_HOST:$DB_PORT，现有数据将被替换！"
read -r -p "确认请输入 YES：" CONFIRM
if [[ "$CONFIRM" != "YES" ]]; then
  echo "已取消"; exit 1
fi

gunzip -c "$FILE" | mysql \
  --host="$DB_HOST" --port="$DB_PORT" --user="$DB_USER" --password="$DB_PASS" "$DB"
echo "恢复完成。建议随后执行：alembic upgrade head（确保迁移版本一致）"
