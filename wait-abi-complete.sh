#!/bin/bash

set -euxo pipefail

if [ -z ${INSTALLER_BIN+x} ]; then
	echo "Please set INSTALLER_BIN"
	exit 1
fi

if [ -z ${INSTALLER_WORKDIR+x} ]; then
	echo "Please set INSTALLER_WORKDIR"
	exit 1
fi

${INSTALLER_BIN} agent wait-for install-complete --dir="${INSTALLER_WORKDIR}"

# TODO: For now this is needed to ensure our kubeconfig gets all the ingress
# certificates that are created late (these kubeconfig certificates are
# required for conformance using that kubeconfig to pass). Remove once the ABI
# ticket AGENT-916 is fixed in all versions we use such that the above agent
# command will ensure this instead
${INSTALLER_BIN} wait-for install-complete --dir="${INSTALLER_WORKDIR}"
