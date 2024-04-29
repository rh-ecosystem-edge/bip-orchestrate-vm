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

# Update libvirt dhcp configuration
if sudo virsh net-dumpxml $NET_NAME | grep -q "mac='$HOST_MAC'" ; then
    action=modify
else
    action=add-last
fi
sudo virsh net-update $NET_NAME $action ip-dhcp-host '<host mac="'$HOST_MAC'" name="'$HOST_NAME'" ip="'$HOST_IP'"/>' --live --parent-index 0

# Update dnsmasq configuration
_dnsmasq_add_if_not_exists api.${CLUSTER_NAME}.${BASE_DOMAIN} ${HOST_IP}
_dnsmasq_add_if_not_exists apps.${CLUSTER_NAME}.${BASE_DOMAIN} ${HOST_IP}
sudo systemctl reload NetworkManager.service
