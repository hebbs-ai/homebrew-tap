#!/bin/sh
# HEBBS Installer
# Usage: curl -sSf https://hebbs.ai/install | sh
#
# Environment variables:
#   HEBBS_VERSION       - Version to install (default: latest)
#   HEBBS_INSTALL_DIR   - Installation directory (default: /usr/local/bin or ~/.hebbs/bin)
#   HEBBS_REPO          - GitHub repository (default: hebbs-ai/hebbs)
#   HEBBS_NO_VERIFY     - Skip checksum verification if set to 1

set -eu

REPO="${HEBBS_REPO:-hebbs-ai/hebbs}"
BASE_URL="https://github.com/${REPO}/releases"

# ── Formatting ───────────────────────────────────────────────────────────────

bold=""
reset=""
green=""
red=""
yellow=""
if [ -t 1 ]; then
    bold="\033[1m"
    reset="\033[0m"
    green="\033[32m"
    red="\033[31m"
    yellow="\033[33m"
fi

info()  { printf "${bold}${green}  ▸${reset} %s\n" "$1"; }
warn()  { printf "${bold}${yellow}  ▸${reset} %s\n" "$1"; }
err()   { printf "${bold}${red}  ✗${reset} %s\n" "$1" >&2; }
die()   { err "$1"; exit 1; }

# ── Platform detection ───────────────────────────────────────────────────────

detect_platform() {
    OS="$(uname -s)"
    ARCH="$(uname -m)"

    case "$OS" in
        Linux)  OS_NAME="linux"  ;;
        Darwin) OS_NAME="macos"  ;;
        *)      die "Unsupported operating system: $OS" ;;
    esac

    case "$ARCH" in
        x86_64|amd64)       ARCH_NAME="x86_64"  ;;
        aarch64|arm64)      ARCH_NAME="aarch64"  ;;
        *)                  die "Unsupported architecture: $ARCH" ;;
    esac

    # Map to tarball naming convention from release.yml
    case "${OS_NAME}-${ARCH_NAME}" in
        linux-x86_64)   ARTIFACT="hebbs-linux-x86_64"   ;;
        linux-aarch64)  ARTIFACT="hebbs-linux-aarch64"   ;;
        macos-aarch64)  ARTIFACT="hebbs-macos-arm64"     ;;
        macos-x86_64)   die "macOS x86_64 (Intel) is not supported. HEBBS requires Apple Silicon (M1+)." ;;
        *)              die "Unsupported platform: ${OS_NAME}-${ARCH_NAME}" ;;
    esac

    info "Detected platform: ${OS} ${ARCH} → ${ARTIFACT}"
}

# ── Version resolution ───────────────────────────────────────────────────────

resolve_version() {
    if [ -n "${HEBBS_VERSION:-}" ]; then
        VERSION="$HEBBS_VERSION"
        info "Using requested version: ${VERSION}"
        return
    fi

    info "Resolving latest version..."

    if command -v curl > /dev/null 2>&1; then
        VERSION=$(curl -sSf "https://api.github.com/repos/${REPO}/releases/latest" \
            | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": *"//;s/".*//')
    elif command -v wget > /dev/null 2>&1; then
        VERSION=$(wget -qO- "https://api.github.com/repos/${REPO}/releases/latest" \
            | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": *"//;s/".*//')
    else
        die "Neither curl nor wget found. Install one of them and retry."
    fi

    if [ -z "$VERSION" ]; then
        die "Could not determine latest version. Set HEBBS_VERSION manually and retry."
    fi

    info "Latest version: ${VERSION}"
}

# ── Install directory ────────────────────────────────────────────────────────

resolve_install_dir() {
    if [ -n "${HEBBS_INSTALL_DIR:-}" ]; then
        INSTALL_DIR="$HEBBS_INSTALL_DIR"
    elif [ "$(id -u)" = "0" ]; then
        INSTALL_DIR="/usr/local/bin"
    else
        INSTALL_DIR="${HOME}/.hebbs/bin"
    fi

    mkdir -p "$INSTALL_DIR"
    info "Install directory: ${INSTALL_DIR}"
}

# ── Download ─────────────────────────────────────────────────────────────────

download() {
    URL="${BASE_URL}/download/${VERSION}/${ARTIFACT}.tar.gz"
    CHECKSUM_URL="${BASE_URL}/download/${VERSION}/checksums.txt"

    TMPDIR=$(mktemp -d)
    trap 'rm -rf "$TMPDIR"' EXIT

    TARBALL="${TMPDIR}/${ARTIFACT}.tar.gz"

    info "Downloading ${URL}..."

    if command -v curl > /dev/null 2>&1; then
        HTTP_CODE=$(curl -fSL -o "$TARBALL" -w '%{http_code}' "$URL" 2>/dev/null) || true
        if [ ! -f "$TARBALL" ] || [ "$HTTP_CODE" = "404" ]; then
            die "Download failed (HTTP ${HTTP_CODE}). Version ${VERSION} may not have a build for ${ARTIFACT}."
        fi
    elif command -v wget > /dev/null 2>&1; then
        wget -q -O "$TARBALL" "$URL" || die "Download failed. Version ${VERSION} may not have a build for ${ARTIFACT}."
    fi

    # Verify checksum
    if [ "${HEBBS_NO_VERIFY:-0}" != "1" ]; then
        CHECKSUM_FILE="${TMPDIR}/checksums.txt"
        if command -v curl > /dev/null 2>&1; then
            curl -fsSL -o "$CHECKSUM_FILE" "$CHECKSUM_URL" 2>/dev/null || true
        elif command -v wget > /dev/null 2>&1; then
            wget -q -O "$CHECKSUM_FILE" "$CHECKSUM_URL" 2>/dev/null || true
        fi

        if [ -f "$CHECKSUM_FILE" ] && [ -s "$CHECKSUM_FILE" ]; then
            EXPECTED=$(grep "${ARTIFACT}.tar.gz" "$CHECKSUM_FILE" | awk '{print $1}')
            if [ -n "$EXPECTED" ]; then
                if command -v sha256sum > /dev/null 2>&1; then
                    ACTUAL=$(sha256sum "$TARBALL" | awk '{print $1}')
                elif command -v shasum > /dev/null 2>&1; then
                    ACTUAL=$(shasum -a 256 "$TARBALL" | awk '{print $1}')
                else
                    warn "No sha256sum or shasum found — skipping checksum verification"
                    ACTUAL="$EXPECTED"
                fi

                if [ "$ACTUAL" != "$EXPECTED" ]; then
                    die "Checksum mismatch! Expected ${EXPECTED}, got ${ACTUAL}. The download may be corrupted."
                fi
                info "Checksum verified: OK"
            else
                warn "Checksum entry not found for ${ARTIFACT}.tar.gz — skipping verification"
            fi
        else
            warn "Checksums file not available — skipping verification"
        fi
    fi

    # Extract
    info "Extracting to ${INSTALL_DIR}..."
    tar xzf "$TARBALL" -C "$INSTALL_DIR"

    # Ensure binaries are executable
    for bin in hebbs-server hebbs-cli hebbs-bench; do
        if [ -f "${INSTALL_DIR}/${bin}" ]; then
            chmod +x "${INSTALL_DIR}/${bin}"
        fi
    done
}

# ── Post-install ─────────────────────────────────────────────────────────────

post_install() {
    echo ""
    printf "${bold}${green}  ✓ HEBBS ${VERSION} installed successfully${reset}\n"
    echo ""

    for bin in hebbs-server hebbs-cli hebbs-bench; do
        if [ -f "${INSTALL_DIR}/${bin}" ]; then
            printf "    ${green}✓${reset} %s\n" "${INSTALL_DIR}/${bin}"
        fi
    done

    echo ""

    # Check if install dir is in PATH
    case ":$PATH:" in
        *":${INSTALL_DIR}:"*) ;;
        *)
            warn "${INSTALL_DIR} is not in your PATH."
            echo ""
            echo "  Add it by running:"
            echo ""
            echo "    export PATH=\"${INSTALL_DIR}:\$PATH\""
            echo ""
            echo "  Or add that line to your ~/.bashrc, ~/.zshrc, or ~/.profile."
            echo ""
            ;;
    esac

    echo "  Get started:"
    echo ""
    echo "    hebbs-server                            # start the server"
    echo "    hebbs-cli remember \"hello world\"        # store a memory"
    echo "    hebbs-cli recall \"hello\"                 # recall it"
    echo ""
}

# ── Main ─────────────────────────────────────────────────────────────────────

main() {
    echo ""
    printf "${bold}  HEBBS Installer${reset}\n"
    echo ""

    detect_platform
    resolve_version
    resolve_install_dir
    download
    post_install
}

main
