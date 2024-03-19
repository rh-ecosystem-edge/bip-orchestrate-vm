#!/usr/bin/env bash
set -euo pipefail

dir=${1:-/opt/proxy}
image=quay.io/karampok/squid:latest
#fqdn=$(hostname -f)

#[ -d "$dir" ] && echo "$dir exists" && exit 1
[ "$EUID" -ne 0 ] && echo "sudo $0 $dir" && exit 1

mkdir -p "$dir"

#2620:52:0:1351::/64

cat <<EOF > "$dir/squid.conf"
acl seed src fdfa:bada:faba:da::/64
acl recipient src fdfa:bada:faba:db::/64
http_access allow seed
http_access allow recipient
http_access deny all
http_port [::]:3128
cache_dir ufs /var/spool/squid 100 16 256
coredump_dir /var/spool/squid
EOF

cat <<EOF > /etc/systemd/system/podman-proxy.service
[Unit]
Description=Podman container - squid proxy
After=network.target

[Service]
Type=simple
WorkingDirectory=/root
TimeoutStartSec=300
ExecStartPre=-/usr/bin/podman rm -f squid-proxy
ExecStart=/usr/bin/podman run --name squid-proxy --hostname squid-proxy --network=host -v $dir/squid.conf:/etc/squid/squid.conf:Z $image
ExecStop=-/usr/bin/podman rm -f squid-proxy
Restart=always
RestartSec=30s
StartLimitInterval=60s
StartLimitBurst=99

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable podman-proxy --now

firewall-cmd --permanent --zone=libvirt --add-port=3128/tcp
firewall-cmd --reload

echo "systemctl cat podman-proxy"
echo "curl  https://[::1]:9090"
echo "curl -k https://[::1]:9443"
echo "sudo podman run --name squid-proxy --hostname squid-proxy --network=host -v $dir/squid.conf:/etc/squid/squid.conf:Z $image"
# curl -O -L "https://www.redhat.com/index.html" -x "proxy.example.com:3128"
