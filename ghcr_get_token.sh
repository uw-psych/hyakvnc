#!/bin/bash
# # Apptainer utility functions:
set -o pipefail
shopt -s checkwinsize
set -m

[[ "${XDEBUG:-}" == "true" ]] && set -x

function log {
	echo "$*"
}
# ## General utility functions:

# check_command()
# Check if a command is available
# Arguments:
# - <command> - The command to check
# - <loglevel> <message> - Passed to log if the command is not available (optional)
function check_command {
	local cmd
	[[ -z "${cmd:=${1:-}}" ]] && return 1

	if ! command -v "${cmd}" >/dev/null 2>&1; then
		if [[ $# -gt 1 ]]; then
			local loglevel="${2}"
			shift
			log "${loglevel}" "${@:-"${cmd} is not installed!"}"
		fi
		return 1
	fi
	return 0
}

function ghcr_get_oras_sif {
	local url output_path
	[[ -z "${url:=${1:-}}" ]] && {
		log ERROR "URL must be specified"
		return 1
	}
	output_path="${2:-./}" # Optionally set the output file
	[[ -d "${output_path}" ]] && [[ ! -w "${output_path}" ]] && {
		log ERROR "Output directory \"${output_path}\" is not writable"
		return 1
	}

	# Check that the URL is an ORAS GitHub Container Registry URL:
	local address image_ref repo image_tag
	case "${url}" in
	oras://ghcr.io/*)
		address="${url#oras://}"
		image_ref="${address#ghcr.io/}"
		repo="${image_ref%%:*}"
		[[ -z "${repo}" ]] && {
			log ERROR "Failed to parse repository from URL \"${url}\""
			return 1
		}
		[[ ${image_ref} == *:* ]] && image_tag="${image_ref##*:}"
		image_tag="${image_tag:-latest}"
		[[ -d "${output_path}" ]] && output_path="${output_path}/${repo//\//--}--${image_tag}.sif"
		;;
	*) # Not a GitHub Container Registry URL
		log ERROR "URL \"${url}\" is not a GitHub Container Registry URL for an ORAS image"
		return 1
		;;
	esac

	# Get a token for the repository (required to get the manifest, but freely available by this request):
	# Uses curl to get the token, then python to parse the JSON response
	local repo_token
	repo_token="$(curl -sSL "https://ghcr.io/token?scope=repository:${repo}:pull&service=ghcr.io" | python3 -I -c 'import sys,json; print(json.load(sys.stdin)["token"])' 2>/dev/null || true)"
	[[ -z "${repo_token}" ]] && {
		log ERROR "Failed to get token for repository ${repo}"
		return 1
	}

	# Request the manifest for the image tag:
	local manifest
	manifest="$(curl -sSL \
		-H "Accept: application/vnd.oci.image.manifest.v1+json" \
		-H "Authorization: Bearer ${repo_token}" \
		"https://ghcr.io/v2/${repo}/manifests/${image_tag}" \
		2>/dev/null || true)"
	[[ -z "${manifest}" ]] && {
		log ERROR "Failed to get manifest for repository ${repo}"
		return 1
	}

	local image_sha256
	image_sha256="$(echo "${manifest}" | python3 -I -c \
		'import sys, json; s=[ x for x in json.load(sys.stdin)["layers"] if x.get("mediaType", "") == "application/vnd.sylabs.sif.layer.v1.sif" and x.get("digest", "").startswith("sha256")]; sys.exit(1) if len(s) != 1 else print(s[0]["digest"])' \
		2>/dev/null || true)"
	[[ -z "${image_sha256:-}" ]] && {
		log ERROR "Failed to get image info for repository ${repo}"
		return 1
	}

	# Download the image:

	local image_url
	image_url="https://ghcr.io/v2/${repo}/blobs/${image_sha256}"
	curl -fSL -H "Authorization: Bearer ${repo_token}" -o "${output_path}" -C - "${image_url}" || {
		log ERROR "Failed to download image from ${image_url} to ${output_path}"
		return 1
	}
	log DEBUG "Downloaded image to ${output_path}"
	echo "${output_path}"
	return 0
}

function progress_bar {
	local current total filled empty cols i barwidth
	# Check that the arguments are valid:
	[[ -z "${current:=${1:-}}" ]] || [[ -z "${total:=${2:-}}" ]] || [[ "${current}" -gt "${total}" ]] && return 1

	# Check or get the number of columns:
	[[ -z "${cols:=${3:-$(tput cols || true)}}" ]] && return 1

	barwidth=$((cols - 2))

	# Calculate the number of filled and empty columns:
	filled=$((current * barwidth / total))
	empty=$((barwidth - filled))

	# Open the progress bar:
	printf "["

	# Print the filled so:
	for ((i = 0; i < filled; i++)); do
		printf "#"
	done

	# Print the empty spaces:
	for ((i = 0; i < empty; i++)); do
		printf " "
	done

	# Close the progress bar:
	printf "]"
}

# bytes_to_human()
# Convert bytes to a human readable format
# Arguments: <bytes> (required)
function bytes_to_human {
	local bytes
	[[ -z "${bytes:=${1:-}}" ]] && return 1
	if [[ ${bytes} -lt 1024 ]]; then
		echo "${bytes} B"
	elif [[ ${bytes} -lt 1048576 ]]; then
		echo $((bytes / 1024)) "KiB"
	elif [[ ${bytes} -lt 1073741824 ]]; then
		echo $((bytes / 1048576)) "MiB"
	else
		echo $((bytes / 1073741824)) "GiB"
	fi
	return 0
}

url="${1:-"oras://ghcr.io/maouw/ubuntu22.04_turbovnc:latest"}"
ghcr_get_oras_sif "${url}"
