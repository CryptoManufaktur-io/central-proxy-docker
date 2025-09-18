#!/usr/bin/env python3

import time
import subprocess
import re
import argparse
import logging

from prometheus_client import start_http_server, Gauge

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s"
)

# Define Prometheus metrics with 'device' label
latency_min = Gauge(
    "ioping_latency_min_us", "Minimum latency in microseconds", ["device"]
)
latency_avg = Gauge(
    "ioping_latency_avg_us", "Average latency in microseconds", ["device"]
)
latency_max = Gauge(
    "ioping_latency_max_us", "Maximum latency in microseconds", ["device"]
)
latency_mdev = Gauge(
    "ioping_latency_mdev_us", "Latency standard deviation in microseconds", ["device"]
)

iops_active = Gauge("ioping_iops_active", "Active IOPS during measurement", ["device"])
iops_sustained = Gauge(
    "ioping_iops_sustained", "Sustained IOPS over full run", ["device"]
)

exporter_status = Gauge(
    "ioping_exporter_status", "Status of the ioping exporter", ["device"]
)


def get_largest_devices(num_devices=2, use_raw_devices=False):
    try:
        # Run df -h and get the devices with the largest sizes
        output = subprocess.check_output(["df", "-h"], stderr=subprocess.STDOUT).decode(
            "utf-8"
        )
        lines = output.strip().split("\n")[1:]  # skip header

        devices = []

        for line in lines:
            parts = re.split(r"\s+", line)
            if len(parts) < 6:
                continue
            device, size = parts[0], parts[1]
            mount_point = parts[5]
            if not device.startswith("/dev/") or mount_point in ['/boot', '/boot/efi']:
                continue
            # Remove 'G', 'T', etc., and convert to GiB
            size_gib = convert_to_gib(size)
            devices.append((size_gib, mount_point, device))

        # Sort by size (largest first) and take top num_devices
        devices.sort(reverse=True, key=lambda x: x[0])

        if not devices:
            fallback_target = "/dev/vda" if use_raw_devices else "/tmp"
            return [(fallback_target, "/dev/vda")]  # fallback

        # Return list of (target, device) tuples
        # target is either mount_point or device depending on use_raw_devices flag
        if use_raw_devices:
            result = [(device, device) for _, mount_point, device in devices[:num_devices]]
        else:
            result = [(mount_point, device) for _, mount_point, device in devices[:num_devices]]
        return result

    except subprocess.CalledProcessError as e:
        print("Failed to run df -h:", e.output.decode())
        fallback_target = "/dev/vda" if use_raw_devices else "/tmp"
        return [(fallback_target, "/dev/vda")]  # fallback
def convert_to_gib(size_str):
    try:
        if size_str.endswith("T"):
            return float(size_str[:-1]) * 1024
        elif size_str.endswith("G"):
            return float(size_str[:-1])
        elif size_str.endswith("M"):
            return float(size_str[:-1]) / 1024
        elif size_str.endswith("K"):
            return float(size_str[:-1]) / 1024 / 1024
        else:
            return float(size_str)
    except Exception:
        return 0


def run_ioping(target, device, count, use_raw_devices=False):
    try:
        target_type = "device" if use_raw_devices else "mount point"
        logging.info(f"Running ioping on {target_type} {target} (device: {device}) with {count} requests")
        exporter_status.labels(device=device).set(1)  # running

        cmd = ["ioping", "-D", "-c", str(count), target]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8")
        logging.debug(f"Raw ioping output:\n{output}")

        # Parse device (fallback to passed device)
        match_dev = re.search(r"^---\s+(/dev/\w+)", output, re.MULTILINE)
        used_device = match_dev.group(1) if match_dev else device

        # Parse latency stats
        match_latency = re.search(
            r"min/avg/max/mdev = ([\d.]+) us / ([\d.]+) us / ([\d.]+) us / ([\d.]+) us",
            output,
        )
        if match_latency:
            latency_min.labels(device=used_device).set(float(match_latency.group(1)))
            latency_avg.labels(device=used_device).set(float(match_latency.group(2)))
            latency_max.labels(device=used_device).set(float(match_latency.group(3)))
            latency_mdev.labels(device=used_device).set(float(match_latency.group(4)))
            logging.info(
                f"Latency stats (us): min={match_latency.group(1)}, avg={match_latency.group(2)}, max={match_latency.group(3)}, mdev={match_latency.group(4)}"
            )

        # Active IOPS
        match_active_iops = re.search(r"([\d.]+) k iops", output)
        if match_active_iops:
            iops = float(match_active_iops.group(1)) * 1000
            iops_active.labels(device=used_device).set(iops)
            logging.info(f"Active IOPS: {iops}")

        # Sustained IOPS
        match_sustained_iops = re.search(r"generated.*?([\d.]+) iops", output)
        if match_sustained_iops:
            sustained = float(match_sustained_iops.group(1))
            iops_sustained.labels(device=used_device).set(sustained)
            logging.info(f"Sustained IOPS: {sustained}")

        exporter_status.labels(device=device).set(2)  # success

    except subprocess.CalledProcessError as e:
        target_type = "device" if use_raw_devices else "mount point"
        logging.error(f"ioping failed on {target_type} {target} (device {device}): {e.output.decode().strip()}")
        exporter_status.labels(device=device).set(3)
    except Exception as ex:
        target_type = "device" if use_raw_devices else "mount point"
        logging.exception(f"Unexpected error while running ioping on {target_type} {target} (device {device}): {ex}")
        exporter_status.labels(device=device).set(3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ioping Prometheus exporter")
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=60,
        help="Interval between ioping runs in seconds",
    )
    parser.add_argument(
        "--count", type=int, default=30, help="Number of ioping requests per run"
    )
    parser.add_argument(
        "--num-devices",
        type=int,
        default=2,
        help="Number of largest devices to monitor (default: 2)"
    )
    parser.add_argument(
        "--use-raw-devices",
        action="store_true",
        help="Monitor raw devices directly instead of mount points (requires root)"
    )
    args = parser.parse_args()

    devices = get_largest_devices(args.num_devices, args.use_raw_devices)
    target_type = "devices" if args.use_raw_devices else "mount points"
    device_info = ", ".join([f"{target} ({dev})" for target, dev in devices])
    print(
        f"Starting ioping exporter monitoring {len(devices)} {target_type}: {device_info}, interval {args.interval_seconds}s..."
    )

    start_http_server(8000)

    while True:
        for target, device in devices:
            run_ioping(target, device, args.count, args.use_raw_devices)
        time.sleep(args.interval_seconds)
        # Set status to idle for all monitored devices
        for _, device in devices:
            exporter_status.labels(device=device).set(0)
