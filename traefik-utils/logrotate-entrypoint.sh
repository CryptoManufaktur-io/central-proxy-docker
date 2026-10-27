#!/bin/sh
# Rotate the Traefik access log daily and keep ACCESSLOG_RETENTION_DAYS rotations.
# copytruncate: Traefik keeps its file handle, so the file is copied and truncated in place
# (a few lines written during the copy may be lost, which is acceptable for an audit log).
set -eu
DAYS="${ACCESSLOG_RETENTION_DAYS:-30}"
cat > /etc/logrotate-accesslog.conf <<CONF
/var/log/traefik/access.log {
    daily
    rotate ${DAYS}
    maxage ${DAYS}
    compress
    delaycompress
    dateext
    missingok
    notifempty
    copytruncate
}
CONF
echo "accesslog-rotate: daily, keeping ${DAYS} rotations"
while true; do
  logrotate -s /var/lib/logrotate-accesslog.status /etc/logrotate-accesslog.conf || true
  sleep 3600
done
