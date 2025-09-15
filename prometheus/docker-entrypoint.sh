#!/bin/sh

set -eu

cd /etc/prometheus

__config_file=/etc/prometheus/prometheus.yml
prepare_config() {
  __base_config=base-config.yml

  # Merge custom config overrides, if provided
  if [ -s custom-prom.yml ]; then
    echo "Applying custom configuration"
    # $item isn't a shell variable, single quotes OK here
    # shellcheck disable=SC2016
    yq eval-all '. as $item ireduce ({}; . *+ $item)' "${__base_config}" custom-prom.yml > "${__config_file}"
  else
    echo "No custom configuration detected"
    cp "${__base_config}" "${__config_file}"
  fi
}

# Check if --config.file was passed in the command arguments
# If it was, then display a warning and skip all our manual processing
for var in "$@"; do
  case "$var" in
    --config.file* )
      echo "WARNING - Manual setting of --config.file found, bypassing automated config preparation in favour of supplied argument"
      /bin/prometheus "$@"
  esac
done

prepare_config
exec /bin/prometheus "$@" --config.file="${__config_file}"
