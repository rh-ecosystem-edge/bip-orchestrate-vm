#!/bin/bash
# Create a libvirt virtual network called 'test-net' configured
# to assign sno1.test-cluster.redhat.com/192.168.126.10 to
# DHCP requests from 52:54:00:ee:42:e1
# libvirt will also configure dnsmasq (listening on 192.168.126.1)
# to respond to DNS queries for several hosts under
# test-cluster.redhat.com with the 192.168.126.10 address.
# This dnsmasq is also configured to not forward unresolved requests
# within the test-cluster.redhat.com domain to upstream DNS servers.
# Finally, we configure NetworkManager to send any DNS queries
# on this machine for api.test-cluster.redhat.com to the libvirt
# configured dnsmasq on 192.168.126.1

# Warn terminal users about dns changes
if [ -t 1 ]; then
    function ask_yes_or_no() {
        read -p "$1 ([y]es or [N]o): "
        case $(echo "$REPLY" | tr '[A-Z]' '[a-z]') in
            y|yes) echo "yes" ;;
            *)     echo "no" ;;
        esac
    }

    echo "This script will make changes to the DNS configuration of your machine, read $0 to learn more"

    if [[ -f .dns_changes_confirmed || "yes" == $(ask_yes_or_no "Are you sure you want to continue?") ]]; then
        touch .dns_changes_confirmed
    else
        exit 1
    fi
fi

if [ -z ${NET_XML+x} ]; then
    echo "Please set NET_XML"
    exit 1
fi

NET_TYPE=$(cat ${NET_XML} | xargs -n1|grep family | cut -d = -f 2)
[[ "$NET_TYPE" == "ipv6" ]] && default_dad=$(sysctl -n net.ipv6.conf.default.accept_dad)

# Only create network if it does not exist
if ! sudo virsh net-dumpxml $NET_NAME | grep -q "<uuid>$NET_UUID</uuid>"; then
    # In IPV6 disable Duplicate Address Detection on the new interface
    [[ "$NET_TYPE" == "ipv6" ]] && sudo sysctl -w net.ipv6.conf.default.accept_dad=0
    sudo virsh net-define "${NET_XML}"
    sudo virsh net-autostart $NET_NAME
    sudo virsh net-start $NET_NAME
    # In IPV6 restore default accept_dad setting
    [[ "$NET_TYPE" == "ipv6" ]] && sudo sysctl -w net.ipv6.conf.default.accept_dad=$default_dad
fi

echo -e "[main]\ndns=dnsmasq" | sudo tee /etc/NetworkManager/conf.d/bip.conf
sudo systemctl reload NetworkManager.service
