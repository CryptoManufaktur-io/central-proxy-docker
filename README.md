# Overview

Repo containing traefik and a prometheus for remote write, intended for integration with eth-docker patterned repos

Prometheus looks for labels to know what to scrape. For example, to have prometheus scrape metrics on port 6060 with
path /metrics:

```
labels:
  - metrics.scrape=true
  - metrics.path=/metrics
  - metrics.port=6060
```

To work well with eth-docker patterned repos, clone this repo into a directory named `traefik` and
use `ext-network.yml` in the repos that are to interface with it. `git clone https://github.com/CryptoManufaktur-io/base-docker-environment.git traefik`

For a quick start, install docker-ce with `./ethd install`, then `cp default.env .env`, adjust Traefik variables
inside `.env`, and `./ethd up`

To update Traefik and Prometheus, run `./ethd update` and `./ethd up`

# License

Apache v2 license

This is base-docker-environment v1.0
