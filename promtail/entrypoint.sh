#!/bin/bash

# Start fresh every time
cp /etc/promtail/global.yml /promtail-config.yml

# Add custom loki urls to config with indentation to make sure its valid yml
if [ -s "/etc/promtail/custom-lokiurl.yml" ]; then
  echo "/etc/promtail/custom-lokiurl.yml" | xargs sed 's/^/  /' >> /promtail-config.yml
else
cat >> /promtail-config.yml << EOF
  - url: http://loki:3100/loki/api/v1/push
EOF
fi

# Add extra log jobs if present and not empty
if [ -s "/etc/promtail/extra-log-jobs.yml" ]; then
  sed -i '/#MORE_JOBS_HERE/r /etc/promtail/extra-log-jobs.yml' /promtail-config.yml
fi

# Replace SERVER_LABEL_HOSTNAME in config file
sed -i "s/SERVER_LABEL_HOSTNAME/$SERVER_LABEL_HOSTNAME/" "/promtail-config.yml"
exec "$@" --config.file=/promtail-config.yml
