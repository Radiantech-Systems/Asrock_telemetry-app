
"""
LAN 1 and LAN 2 monitoring for ASRock.

Reports:
- Ethernet connectivity status
- IPv4 address
- MAC address
- Upload throughput (kbps)
- Download throughput (kbps)

Throughput is calculated using consecutive network counter samples.
"""

import socket
import time
import psutil


LAN_PORTS = ["lan1", "lan2"]
_last_samples = {}


def _mac_address(interface: str) -> str | None:
    try:
        for addr in psutil.net_if_addrs().get(interface, []):
            if addr.family == psutil.AF_LINK:
                return addr.address
    except Exception:
        pass
    return None


def _ip_address(interface: str) -> str | None:
    try:
        for addr in psutil.net_if_addrs().get(interface, []):
            if addr.family == socket.AF_INET:
                return addr.address
    except Exception:
        pass
    return None


def _is_up(interface: str) -> bool:
    """Check interface state and physical Ethernet link."""
    try:
        stats = psutil.net_if_stats().get(interface)

        if not stats or not stats.isup:
            return False

        # Prefer the Linux physical carrier status.
        try:
            with open(
                f"/sys/class/net/{interface}/carrier", "r"
            ) as carrier_file:
                return carrier_file.read().strip() == "1"
        except OSError:
            return stats.isup

    except Exception:
        return False


def collect(interface: str = "lan1") -> dict:
    """Collect metrics for one LAN interface."""
    now = time.monotonic()
    counters = psutil.net_io_counters(pernic=True).get(interface)

    upload_kbps = None
    download_kbps = None

    if counters:
        previous = _last_samples.get(interface)

        if previous is not None:
            elapsed = now - previous["time"]

            if elapsed > 0:
                sent_delta = counters.bytes_sent - previous["sent"]
                recv_delta = counters.bytes_recv - previous["recv"]

                if sent_delta >= 0:
                    upload_kbps = round(
                        sent_delta * 8 / 1000 / elapsed, 1
                    )

                if recv_delta >= 0:
                    download_kbps = round(
                        recv_delta * 8 / 1000 / elapsed, 1
                    )

        _last_samples[interface] = {
            "time": now,
            "sent": counters.bytes_sent,
            "recv": counters.bytes_recv,
        }

    return {
        "ethernet_status": "up" if _is_up(interface) else "down",
        "ip_address": _ip_address(interface),
        "mac_address": _mac_address(interface),
        "upload_speed_kbps": upload_kbps,
        "download_speed_kbps": download_kbps,
    }


def collect_all() -> list[dict]:
    """Collect metrics for LAN 1 and LAN 2."""
    results = []

    for interface in LAN_PORTS:
        results.append({
            "port": interface.upper(),
            "interface": interface,
            **collect(interface),
        })

    return results


if __name__ == "__main__":
    import json
    print(json.dumps(collect_all(), indent=2))
