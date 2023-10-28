#!/bin/sh

# install.sh is generated from .build/install.j2.sh. Do not edit it directly.
# This script is intended to be sourced from the current shell.
# It will clone the hyakvnc repository to ~/.hyakvnc/hyakvnc and create a symlink in it to ~/.local/bin/hyakvnc.
# These locations can be changed by setting the following environment variables:
# - HYAKVNC_DIR: Local directory to store application data (default: `$HOME/.hyakvnc`)
# - HYAKVNC_REPO_DIR: Local directory to store git repository (default: `$HYAKVNC_DIR/hyakvnc`)
# - HYAKVNC_REPO_URL: URL of the git repository to clone (default: )
# - BIN_INSTALL_DIR: Local directory to store executable (default: `$HOME/.local/bin`)

_add_hyakvnc_to_path() {
	[ -z "${_UNEXPANDED_BIN_INSTALL_DIR:-}" ] || [ -z "${_BIN_INSTALL_DIR:-}" ] && return 1
	case "${PATH:-}" in
	*"${_BIN_INSTALL_DIR}"*) ;;
	*)
		if [ -n "${BASH_VERSION:-}" ]; then
			echo "export PATH=\"${_UNEXPANDED_BIN_INSTALL_DIR}:\$PATH\"" >>"${HOME:-}/.bashrc"
			echo "Added hyakvnc to PATH in ${HOME:-}/.bashrc" 2>&1
			export PATH="${_BIN_INSTALL_DIR}:${PATH:-}"
		elif [ -n "${ZSH_VERSION:-}" ]; then
			echo "export PATH=\"${_UNEXPANDED_BIN_INSTALL_DIR}:\$PATH\"" >>"${ZDOTDIR:-${HOME:-}}/.zshrc" && echo "Added hyakvnc to PATH in ${ZDOTDIR:-${HOME}}/.zshrc" 2>&1
			export PATH="${_BIN_INSTALL_DIR}:${PATH:-}"
			rehash 2>/dev/null || true
		elif [ "${0:-}" = "dash" ] || [ "${0:-}" = "sh" ]; then
			echo "export PATH=\"${_UNEXPANDED_BIN_INSTALL_DIR}:\$PATH\"" >>"${HOME}/.profile" && echo "Added hyakvnc to PATH in ${HOME}/.profile" 2>&1
			export PATH="${_BIN_INSTALL_DIR}:${PATH:-}"
		else
			echo "Could not add hyakvnc to PATH." 2>&1
			return 1
		fi
		;;
	esac
}

_install_hyakvnc() {
	_HYAKVNC_DIR="${_HYAKVNC_DIR:-${HOME}/.hyakvnc}"                  # %% Local directory to store application data (default: `$HOME/.hyakvnc`)
	_HYAKVNC_REPO_DIR="${_HYAKVNC_REPO_DIR:-${_HYAKVNC_DIR}/hyakvnc}" # Local directory to store git repository (default: `$HYAKVNC_DIR/hyakvnc`)
	_HYAKVNC_REPO_URL="${_HYAKVNC_REPO_URL:-"https://github.com/maouw/hyakvnc"}"
	_HYAKVNC_REPO_BRANCH="${_HYAKVNC_REPO_BRANCH:-"gh-build-fix"}"

	# shellcheck disable=SC2016
	_UNEXPANDED_BIN_INSTALL_DIR='${HOME}/.local/bin'                          # Local directory to store executable (default: `$HOME/.local/bin`)
	_EXPANDED_BIN_INSTALL_DIR="$(eval echo "${_UNEXPANDED_BIN_INSTALL_DIR}")" # Expand environment variables in path
	_BIN_INSTALL_DIR="${_BIN_INSTALL_DIR:-${_EXPANDED_BIN_INSTALL_DIR}}"

	mkdir -p "${_BIN_INSTALL_DIR}" &&
		rm -rf "${_HYAKVNC_DIR}/hyakvnc-tmp" &&
		echo "Fetching hyakvnc from ${_HYAKVNC_REPO_URL}" 2>&1 &&
		git clone --branch "${_HYAKVNC_REPO_BRANCH}" --depth 1 --single-branch --quiet "${_HYAKVNC_REPO_URL}" ~/.hyakvnc/hyakvnc-tmp &&
		rm -rf "${_HYAKVNC_REPO_DIR}" &&
		mv "${_HYAKVNC_DIR}/hyakvnc-tmp" "${_HYAKVNC_REPO_DIR}" &&
		ln -sf "${_HYAKVNC_REPO_DIR}/hyakvnc" "${_BIN_INSTALL_DIR}/hyakvnc" &&
		echo "Installed hyakvnc to ${_BIN_INSTALL_DIR}/hyakvnc linking to hyakvnc in ${_HYAKVNC_REPO_DIR}" 2>&1 ||
		return 1
}

if _install_hyakvnc; then
	echo "Successfully installed hyakvnc." 2>&1
	if _add_hyakvnc_to_path; then
		echo "Added hyakvnc to PATH." 2>&1
	else
		echo "Could not add hyakvnc to PATH." 2>&1
	fi
else
	echo "Failed to install hyakvnc." 2>&1
fi

# Unset all variables and functions defined in this script:
unset _HYAKVNC_DIR _HYAKVNC_REPO_DIR _HYAKVNC_REPO_URL _UNEXPANDED_BIN_INSTALL_DIR _EXPANDED_BIN_INSTALL_DIR _BIN_INSTALL_DIR
unset -f _install_hyakvnc _add_hyakvnc_to_path
