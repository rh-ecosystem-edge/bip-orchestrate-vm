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


def _indent_block(text: str, spaces: int) -> str:
    prefix = " " * spaces
    lines = text.splitlines() or [""]
    return "\n".join(prefix + line for line in lines)


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


def _require_for_stack(ip_stack: str, fam: str, name: str) -> str:
    v = _env(f"{name}_{fam.upper()}", default="")
    if v == "":
        raise ValueError(f"IP_STACK={ip_stack} requires {name}_{fam.upper()} to be set")
    return v


def _yaml_cluster_networks(ip_stack: str, order: list[str]) -> str:
    out: list[str] = []
    for fam in order:
        cidr = _require_for_stack(ip_stack, fam, "CLUSTER_NETWORK")
        hp = _env(
            f"CLUSTER_NETWORK_HOST_PREFIX_{fam.upper()}",
            default="64" if fam == "v6" else "23",
            required=False,
        )
        # Must match template indentation (2 spaces before list item)
        out.append(f"  - cidr: {cidr}\n    hostPrefix: {int(hp)}")
    return "\n".join(out)


def _yaml_machine_networks(ip_stack: str, order: list[str]) -> str:
    out: list[str] = []
    for fam in order:
        cidr = _require_for_stack(ip_stack, fam, "MACHINE_NETWORK")
        out.append(f"  - cidr: {cidr}")
    return "\n".join(out)


def _yaml_service_networks(ip_stack: str, order: list[str]) -> str:
    out: list[str] = []
    for fam in order:
        cidr = _require_for_stack(ip_stack, fam, "CLUSTER_SVC_NETWORK")
        # serviceNetwork list items are scalar strings
        out.append(f"  - {cidr}")
    return "\n".join(out)


def _validate_ip_families(order: list[str]) -> None:
    # Validate that provided CIDRs are parseable and match their family.
    for fam in order:
        for base in ("CLUSTER_NETWORK", "MACHINE_NETWORK", "CLUSTER_SVC_NETWORK"):
            cidr = _env(f"{base}_{fam.upper()}", "")
            if cidr == "":
                continue
            n = ipaddress.ip_network(cidr, strict=False)
            if fam == "v4" and n.version != 4:
                raise ValueError(f"{base}_{fam.upper()} must be IPv4 CIDR, got: {cidr}")
            if fam == "v6" and n.version != 6:
                raise ValueError(f"{base}_{fam.upper()} must be IPv6 CIDR, got: {cidr}")


def main() -> int:
    template_path = sys.argv[1] if len(sys.argv) > 1 else "install-config.yaml.template"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "install-config.yaml"

    base_domain = _env("BASE_DOMAIN", required=True)
    cluster_name = _env("CLUSTER_NAME", required=True)
    installation_disk = _env("INSTALLATION_DISK", required=True)
    pull_secret = _env("PULL_SECRET", required=True)
    ssh_key_pub_path = _env("SSH_KEY_PUB_PATH", required=True)

    ip_stack = _env("IP_STACK", default="v4")
    order = _stack_order(ip_stack)
    _validate_ip_families(order)

    with open(ssh_key_pub_path, "r", encoding="utf-8") as f:
        ssh_key = f.read().strip()

    with open(template_path, "r", encoding="utf-8") as f:
        data = f.read()

    data = data.replace("BASE_DOMAIN", base_domain)
    data = data.replace("CLUSTER_NAME", cluster_name)
    data = data.replace("INSTALLATION_DISK", installation_disk)

    data = data.replace("CLUSTER_NETWORKS_YAML", _yaml_cluster_networks(ip_stack, order))
    data = data.replace("MACHINE_NETWORKS_YAML", _yaml_machine_networks(ip_stack, order))
    data = data.replace("SERVICE_NETWORKS_YAML", _yaml_service_networks(ip_stack, order))

    # Preserve existing indentation in template for these blocks (8 spaces after the pipe)
    data = data.replace("YOUR_PULL_SECRET", _indent_block(pull_secret, 8))
    data = data.replace("YOUR_SSH_KEY", _indent_block(ssh_key, 8))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(data)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"render-install-config.py: error: {e}", file=sys.stderr)
        raise SystemExit(1)


