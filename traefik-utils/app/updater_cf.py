from __future__ import annotations
import os
import sys
import time
import signal
import logging
import ipaddress
import requests
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)
from types import FrameType
from typing import NoReturn

CF_API_BASE = "https://api.cloudflare.com/client/v4"


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("cf-ddns-updater")
    if not logger.handlers:
        _handler = logging.StreamHandler(sys.stdout)
        _handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(_handler)
        _level = os.getenv("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, _level, logging.INFO))
        logger.propagate = False  # Prevent propagation to root logger
    return logger


def validate_ipv4(ip: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(ip), ipaddress.IPv4Address)
    except ValueError:
        return False


def validate_ipv6(ip: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(ip), ipaddress.IPv6Address)
    except ValueError:
        return False


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(requests.RequestException),
)
def get_external_ip() -> str:
    ip_services = [
        "https://ipv4.icanhazip.com",
        "https://checkip.amazonaws.com",
        "http://whatismyip.akamai.com",
        "http://ip.42.pl/raw",
        "https://api64.ipify.org",
        "https://ipinfo.io/ip",
        "https://ifconfig.me",
        "https://ident.me",
        "https://ipecho.net/plain",
        "https://wtfismyip.com/text",
        "https://bot.whatismyipaddress.com",
        "https://myexternalip.com/raw",
        "https://ip.seeip.org",
        "https://ip.tyk.nu",
        "https://api.my-ip.io/ip",
        "https://ipwho.is/?format=text",
    ]

    for url in ip_services:
        try:
            resp = requests.get(url, timeout=3)
            if resp.ok:
                text = resp.text.strip()
                ip = text.split()[0]
                if validate_ipv4(ip):
                    logger.info(f"Got external IP from {url}: {ip}")
                    return ip
                else:
                    logger.warning(f"Invalid IP format from {url}: {ip}")
        except Exception as e:
            logger.debug(f"Failed to get IP from {url}: {e}")

    raise requests.RequestException("Unable to fetch external IP from any source")


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(requests.RequestException),
)
def get_external_ip6() -> str | None:
    ip6_services = [
        "https://api6.ipify.org",
        "https://ipv6.icanhazip.com",
        "https://ifconfig.co/ip",
        "https://ident.me",  # works on v6 if reachable via v6
        "https://myexternalip.com/raw",
    ]
    for url in ip6_services:
        try:
            resp = requests.get(url, timeout=3)
            if resp.ok:
                ip = resp.text.strip().split()[0]
                if validate_ipv6(ip):
                    logger.info(f"Got external IPv6 from {url}: {ip}")
                    return ip
                else:
                    logger.debug(f"Invalid IPv6 format from {url}: {ip}")
        except Exception as e:
            logger.debug(f"Failed to get IPv6 from {url}: {e}")
    logger.info("No external IPv6 detected; skipping AAAA update")
    return None


def normalize_fqdn(s: str) -> str:
    return s.strip().rstrip(".").lower()


def build_cname_fqdn(label_or_name: str, domain: str) -> str:
    """
    - 'api' -> 'api.<domain>'
    - 'api.example.com' -> 'api.example.com'
    - '<domain>' -> '<domain>'
    """
    n = label_or_name.strip().rstrip(".")
    d = domain.strip().rstrip(".")
    if not n:
        raise ValueError("Empty CNAME entry")

    if n == d or n.endswith("." + d):
        return n

    if "." in n:
        return n

    return f"{n}.{d}"


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(requests.RequestException),
)
def cf_request(method: str, path: str, token: str, **kwargs) -> dict:
    resp = requests.request(
        method,
        f"{CF_API_BASE}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=10,
        **kwargs,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success", False):
        raise RuntimeError(f"Cloudflare API error: {data.get('errors')}")
    return data


def get_dns_record(zone_id: str, rtype: str, name: str, token: str) -> dict | None:
    data = cf_request(
        "GET",
        f"/zones/{zone_id}/dns_records",
        token,
        params={"type": rtype, "name": name},
    )
    results = data.get("result", [])
    return results[0] if results else None


def upsert_dns_record(
    zone_id: str,
    rtype: str,
    name: str,
    content: str,
    ttl: int,
    proxied: bool,
    token: str,
) -> None:
    existing = get_dns_record(zone_id, rtype, name, token)
    payload = {
        "type": rtype,
        "name": name,
        "content": content,
        "ttl": ttl,
        "proxied": proxied,
    }

    if existing is None:
        cf_request("POST", f"/zones/{zone_id}/dns_records", token, json=payload)
        logger.info(f"Created {rtype} record: {name} -> {content}")
        return

    if (
        normalize_fqdn(existing.get("content", "")) == normalize_fqdn(content)
        and existing.get("proxied") == proxied
    ):
        logger.info(f"{rtype} {name} already up-to-date -> {content}")
        return

    cf_request(
        "PUT",
        f"/zones/{zone_id}/dns_records/{existing['id']}",
        token,
        json=payload,
    )
    logger.info(f"Updated {rtype} record: {name} -> {content}")


# graceful shutdown
def _shutdown(signum: int, frame: FrameType | None) -> NoReturn:
    logger.info("Received shutdown signal, exiting.")
    raise SystemExit(0)


def main() -> None:
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    token = os.environ["CF_DNS_API_TOKEN"]
    zone_id = os.environ["CF_ZONE_ID"]
    domain = os.environ["DOMAIN"]
    a_record_name = os.environ["A_RECORD_NAME"]
    cname_list = os.getenv("CNAME_LIST", "")
    proxied = os.getenv("DDNS_PROXY", "false").strip().lower() == "true"
    ttl = int(os.getenv("TTL", 300))
    sleep_seconds = int(os.getenv("SLEEP", 300))

    fqdn = normalize_fqdn(a_record_name)
    cnames = [c.strip() for c in cname_list.split(",") if c.strip()]

    while True:
        try:
            ip4 = get_external_ip()
            ip6 = get_external_ip6()

            upsert_dns_record(zone_id, "A", fqdn, ip4, ttl, proxied, token)

            if ip6:
                upsert_dns_record(zone_id, "AAAA", fqdn, ip6, ttl, proxied, token)
            else:
                logger.debug("Skipping AAAA update: no external IPv6 detected")

            for cname in cnames:
                try:
                    cname_fqdn = build_cname_fqdn(cname, domain)
                    if normalize_fqdn(cname_fqdn) == normalize_fqdn(domain):
                        logger.warning(f"Skipping apex CNAME for {cname_fqdn}")
                        continue
                    if normalize_fqdn(cname_fqdn) == fqdn:
                        logger.warning(
                            f"Skipping {cname_fqdn}: CNAME cannot point to itself"
                        )
                        continue
                    upsert_dns_record(
                        zone_id, "CNAME", cname_fqdn, fqdn, ttl, proxied, token
                    )
                except Exception as e:
                    logger.error(f"Error updating CNAME {cname}: {e}")

        except Exception as e:
            logger.error(f"Error during update cycle: {e}")

        logger.info(f"Sleeping {sleep_seconds} seconds")
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    logger = setup_logger()
    try:
        main()
    except Exception as e:
        logger.error(f"Fatal: {e}")
        sys.exit(1)
