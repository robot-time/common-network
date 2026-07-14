#!/usr/bin/env bash
# Install the Common Network node tool (macOS / Linux).
#
#   curl -fsSL https://raw.githubusercontent.com/robot-time/common-network/main/install.sh | sh
#
# Installs cloudflared (if missing), fetches join.py, and puts a
# `common-join` command on your PATH. Ollama is checked but not auto-
# installed on macOS since it's a GUI app you install once.
set -euo pipefail

REPO="robot-time/common-network"
INSTALL_DIR="$HOME/.common-network"
BIN_DIR="$INSTALL_DIR/bin"
RAW="https://raw.githubusercontent.com/$REPO/main"

echo "Installing Common Network node tools..."
mkdir -p "$BIN_DIR"

OS="$(uname -s)"
ARCH="$(uname -m)"

# --- python3 ---
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required but wasn't found."
  if [ "$OS" = "Darwin" ]; then
    echo "  Install it with: xcode-select --install"
  else
    echo "  Install it with your package manager, e.g.: sudo apt install python3"
  fi
  exit 1
fi

# --- cloudflared ---
if ! command -v cloudflared >/dev/null 2>&1 && [ ! -x "$BIN_DIR/cloudflared" ]; then
  echo "Installing cloudflared (opens the free tunnel to your machine)..."
  if [ "$OS" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
    brew install cloudflared
  elif [ "$OS" = "Darwin" ]; then
    case "$ARCH" in
      arm64) CF_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz" ;;
      *)     CF_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz" ;;
    esac
    TMP_TGZ="$(mktemp)"
    curl -fsSL "$CF_URL" -o "$TMP_TGZ"
    tar -xzf "$TMP_TGZ" -C "$BIN_DIR"
    rm -f "$TMP_TGZ"
    chmod +x "$BIN_DIR/cloudflared"
  elif [ "$OS" = "Linux" ]; then
    case "$ARCH" in
      x86_64)        CF_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" ;;
      aarch64|arm64) CF_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64" ;;
      *) echo "Unsupported architecture: $ARCH. Install cloudflared manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"; exit 1 ;;
    esac
    curl -fsSL "$CF_URL" -o "$BIN_DIR/cloudflared"
    chmod +x "$BIN_DIR/cloudflared"
  else
    echo "Unsupported OS: $OS. Install cloudflared manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
    exit 1
  fi
fi

# --- ollama ---
if ! command -v ollama >/dev/null 2>&1; then
  if [ "$OS" = "Linux" ]; then
    echo "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
  else
    echo ""
    echo "Ollama isn't installed yet. Download it from https://ollama.com/download,"
    echo "open it once (so it's running), then re-run this installer."
    exit 1
  fi
fi

# --- join.py ---
echo "Downloading the join script..."
curl -fsSL "$RAW/join/join.py" -o "$INSTALL_DIR/join.py"
chmod +x "$INSTALL_DIR/join.py"

# --- wrapper command ---
cat > "$BIN_DIR/common-join" <<WRAPPER
#!/usr/bin/env bash
export PATH="$BIN_DIR:\$PATH"
exec python3 "$INSTALL_DIR/join.py" "\$@"
WRAPPER
chmod +x "$BIN_DIR/common-join"

# --- PATH setup ---
SHELL_RC=""
case "${SHELL:-}" in
  */zsh)  SHELL_RC="$HOME/.zshrc" ;;
  */bash) SHELL_RC="$HOME/.bashrc" ;;
esac

if [ -n "$SHELL_RC" ] && ! grep -qs "$BIN_DIR" "$SHELL_RC" 2>/dev/null; then
  echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$SHELL_RC"
  ADDED_TO_RC=1
fi

echo ""
echo "Done! To join the network, run:"
echo ""
echo "    common-join"
echo ""
if [ "${ADDED_TO_RC:-0}" = "1" ]; then
  echo "(Restart your terminal first, or run: export PATH=\"$BIN_DIR:\$PATH\")"
fi
