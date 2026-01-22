#!/usr/bin/env python3

import ipaddress
import os
import sys
from typing import Optional


def _env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    v = os.environ.get(name, default)
    if required and (v is None or v == ""):
        raise ValueError(f"Missing required env var: {name}")
    return v if v is not None else ""


def _stack_order(ip_stack: str) -> list[str]:
    if ip_stack == "v4":
        return ["v4"]
    if ip_stack == "v6":
        return ["v6"]
    if ip_stack == "v4v6":
        return ["v4", "v6"]
    if ip_stack == "v6v4":
        return ["v6", "v4"]
    raise ValueError(f"Invalid IP_STACK={ip_stack}. Expected one of: v4, v6, v4v6, v6v4")


def _require_cidr(ip_stack: str, fam: str) -> str:
    v = _env(f"MACHINE_NETWORK_{fam.upper()}", default="")
    if v == "":
        raise ValueError(f"IP_STACK={ip_stack} requires MACHINE_NETWORK_{fam.upper()} to be set")
    return v


def _render_ipv4_block(cidr: str) -> str:
    n = ipaddress.IPv4Network(cidr, strict=False)
    # Convention: .1 gateway, .2..(broadcast-1) DHCP
    if n.num_addresses < 4:
        raise ValueError(f"IPv4 CIDR {cidr} is too small for gateway/DHCP range")
    gw = str(ipaddress.IPv4Address(int(n.network_address) + 1))
    dhcp_start = ipaddress.IPv4Address(int(n.network_address) + 2)
    dhcp_end = ipaddress.IPv4Address(int(n.broadcast_address) - 1)
    if dhcp_start > dhcp_end:
        raise ValueError(f"IPv4 CIDR {cidr} is too small for gateway/DHCP range")
    return "\n".join(
        [
            f"  <ip family='ipv4' address='{gw}' prefix='{n.prefixlen}'>",
            "    <dhcp>",
            f"      <range start='{dhcp_start}' end='{dhcp_end}'/>",
            "    </dhcp>",
            "  </ip>",
        ]
    )


def _render_ipv6_block(cidr: str) -> str:
    n = ipaddress.IPv6Network(cidr, strict=False)
    # Convention: ::1 gateway, ::2..(small deterministic range) DHCP
    if n.num_addresses < 3:
        raise ValueError(f"IPv6 CIDR {cidr} is too small for gateway/DHCP range")
    gw = ipaddress.IPv6Address(int(n.network_address) + 1)
    dhcp_start = ipaddress.IPv6Address(int(n.network_address) + 2)

    # Keep DHCPv6 range modest; clamp to subnet
    last = ipaddress.IPv6Address(int(n.network_address) + (n.num_addresses - 1))
    preferred_end = ipaddress.IPv6Address(int(n.network_address) + 0x1FFF)
    dhcp_end = preferred_end if preferred_end <= last else last
    if dhcp_end == last and dhcp_end > n.network_address:
        dhcp_end = ipaddress.IPv6Address(int(dhcp_end) - 1)

    if dhcp_start > dhcp_end:
        raise ValueError(f"IPv6 CIDR {cidr} is too small for gateway/DHCP range")

    return "\n".join(
        [
            f"  <ip family='ipv6' address='{gw}' prefix='{n.prefixlen}'>",
            "    <dhcp>",
            f"      <range start='{dhcp_start}' end='{dhcp_end}'/>",
            "    </dhcp>",
            "  </ip>",
        ]
    )


def main() -> int:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "net.xml"

    net_name = _env("NET_NAME", required=True)
    net_uuid = _env("NET_UUID", required=True)
    bridge = _env("NET_BRIDGE_NAME", required=True)
    mac = _env("NET_MAC", required=True)
    base_domain = _env("BASE_DOMAIN", required=True)

    ip_stack = _env("IP_STACK", default="v4")
    order = _stack_order(ip_stack)

    ip_blocks: list[str] = []
    for fam in order:
        cidr = _require_cidr(ip_stack, fam)
        if fam == "v4":
            ip_blocks.append(_render_ipv4_block(cidr))
        else:
            ip_blocks.append(_render_ipv6_block(cidr))

    xml = "\n".join(
        [
            "<network>",
            f"  <name>{net_name}</name>",
            f"  <uuid>{net_uuid}</uuid>",
            "  <forward mode='nat'/>",
            f"  <bridge name='{bridge}' stp='on' delay='0'/>",
            "  <mtu size='1500'/>",
            f"  <mac address='{mac}'/>",
            f"  <domain name='{base_domain}' localOnly='yes'/>",
            "  <dns enable='yes'/>",
            *ip_blocks,
            "</network>",
            "",
        ]
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"render-net-xml.py: error: {e}", file=sys.stderr)
        raise SystemExit(1)


