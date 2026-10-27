# Overview

Repo containing Traefik and a Prometheus/promtail for remote write, intended for integration with Eth Docker patterned repos

Prometheus looks for labels to know what to scrape. For example, to have Prometheus scrape metrics on port 6060 with
path /metrics:

```
labels:
  - metrics.scrape=true
  - metrics.path=/metrics
  - metrics.port=6060
```

Promtail can be used on its own with servers with their own prometheus, that's why it is in a separate file.
To use promtail, add `promtail.yml` to `COMPOSE_FILE` in `.env`


To work well with Eth Docker patterned repos, clone this repo into a directory named `traefik` and
use `ext-network.yml` in the repos that are to interface with it.
`git clone https://github.com/CryptoManufaktur-io/central-proxy-docker.git traefik`

For a quick start, install docker-ce with `./ethd install`, then `cp default.env .env`, adjust Traefik variables
inside `.env`, and `./ethd up`

## Access log

Traefik writes a JSON access log to `/var/log/traefik/access.log` in the `accesslog` Docker volume. It is not
written to stdout, so promtail (which reads container logs) does not collect it and nothing is shipped to Loki.
The `accesslog-rotate` service rotates it daily and keeps `ACCESSLOG_RETENTION_DAYS` rotations (default 30,
compressed). Headers are dropped except `User-Agent` and `X-Forwarded-For`. The request body is not logged, so
the JSON-RPC method is not visible. Set `TRAEFIK_ACCESSLOG=false` to disable.

Read it with `docker run --rm -v <project>_accesslog:/l alpine sh -c 'tail -n 50 /l/access.log'`, or from the
volume path under `/var/lib/docker/volumes/`.

To update Traefik and Prometheus, run `./ethd update` and `./ethd up`

# License

Apache v2 license

This is central-proxy-docker v2.0.0
