#!/bin/bash

tmpfile=$(mktemp)
_cleanup(){
    rm -f $tmpfile
}
trap _cleanup exit

# _dnsmasq_add_if_not_exists domain_name ip_address
_dnsmasq_add_if_not_exists(){
    grep -vE "^address=/$1/" /etc/NetworkManager/dnsmasq.d/bip.conf > $tmpfile
    echo "address=/$1/$2" >> $tmpfile
    sudo tee /etc/NetworkManager/dnsmasq.d/bip.conf < $tmpfile
}

_ip_family() {
    if [[ "$1" == *:* ]]; then
        echo ipv6
    else
        echo ipv4
    fi
}

_parent_index_for_family() {
    local fam="$1"
    sudo virsh net-dumpxml "$NET_NAME" | awk -v fam="$fam" '
        BEGIN{idx=0}
        /<ip /{
            if ($0 ~ "family='\''"fam"'\''") { print idx; exit 0 }
            idx++
        }
        END{ exit 1 }
    '
}

_update_dhcp_host() {
    local ip="$1"
    local fam="$(_ip_family "$ip")"
    local parent_index
    if ! parent_index="$(_parent_index_for_family "$fam")"; then
        echo "WARN: no <ip family='$fam'> block found in libvirt network $NET_NAME; skipping DHCP host update for $ip" >&2
        return 0
    fi

    # Update libvirt dhcp configuration (idempotent)
    if sudo virsh net-dumpxml "$NET_NAME" | grep -q "mac='$HOST_MAC'" ; then
        action=modify
    else
        action=add-last
    fi
    sudo virsh net-update "$NET_NAME" "$action" ip-dhcp-host \
        '<host mac="'$HOST_MAC'" name="'$HOST_NAME'" ip="'$ip'"/>' \
        --live --parent-index "$parent_index"
}

# Primary IP (required)
_update_dhcp_host "$HOST_IP"

# Optional secondary IP for dual-stack
if [[ -n "${HOST_IP_SECONDARY}" ]]; then
    _update_dhcp_host "$HOST_IP_SECONDARY"
fi

# Update dnsmasq configuration
_dnsmasq_add_if_not_exists api.${CLUSTER_NAME}.${BASE_DOMAIN} ${HOST_IP}
_dnsmasq_add_if_not_exists apps.${CLUSTER_NAME}.${BASE_DOMAIN} ${HOST_IP}
sudo systemctl reload NetworkManager.service
