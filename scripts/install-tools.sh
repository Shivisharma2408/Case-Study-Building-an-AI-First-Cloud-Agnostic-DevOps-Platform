#!/usr/bin/env bash
# Optional: download pinned kind / helm / terraform into ./.tools/bin (git-ignored),
# verifying SHA-256 checksums. Use this if you prefer not to install them system-wide.
source "$(dirname "$0")/lib.sh"
require curl

KIND_VERSION="${KIND_VERSION:-v0.26.0}"
HELM_VERSION="${HELM_VERSION:-v3.16.4}"
TERRAFORM_VERSION="${TERRAFORM_VERSION:-1.9.8}"

case "$(uname -s)" in
  Linux*) os=linux ;;
  Darwin*) os=darwin ;;
  MINGW*|MSYS*|CYGWIN*) os=windows ;;
  *) die "unsupported OS $(uname -s)" ;;
esac
case "$(uname -m)" in
  x86_64|amd64) arch=amd64 ;;
  arm64|aarch64) arch=arm64 ;;
  *) die "unsupported arch $(uname -m)" ;;
esac
# kind ships windows/amd64 only; Windows on ARM runs it under emulation.
[[ "$os" == windows ]] && arch=amd64
exe=""; [[ "$os" == windows ]] && exe=".exe"

bin="$REPO_ROOT/.tools/bin"; tmp="$REPO_ROOT/.tools/tmp"
mkdir -p "$bin" "$tmp"
PY="$(python_bin)"

sha256() { "$PY" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"; }
unzip_to() { "$PY" -c 'import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$1" "$2"; }
verify() { # file expected
  local got; got="$(sha256 "$1")"
  [[ "$got" == "$2" ]] || die "checksum mismatch for $(basename "$1"): got $got expected $2"
}

if ! has kind; then
  url="https://kind.sigs.k8s.io/dl/$KIND_VERSION/kind-$os-$arch"
  log "kind $KIND_VERSION"
  curl -fsSL --retry 5 --retry-delay 3 --retry-all-errors "$url" -o "$tmp/kind"
  verify "$tmp/kind" "$(curl -fsSL --retry 5 --retry-delay 3 --retry-all-errors "$url.sha256sum" | awk '{print $1}')"
  mv "$tmp/kind" "$bin/kind$exe" && chmod +x "$bin/kind$exe"
fi

if ! has helm; then
  ext="tar.gz"; [[ "$os" == windows ]] && ext="zip"
  url="https://get.helm.sh/helm-$HELM_VERSION-$os-$arch.$ext"
  log "helm $HELM_VERSION"
  curl -fsSL --retry 5 --retry-delay 3 --retry-all-errors "$url" -o "$tmp/helm.$ext"
  verify "$tmp/helm.$ext" "$(curl -fsSL --retry 5 --retry-delay 3 --retry-all-errors "$url.sha256sum" | awk '{print $1}')"
  if [[ "$ext" == zip ]]; then unzip_to "$tmp/helm.zip" "$tmp/helm"; else mkdir -p "$tmp/helm" && tar -xzf "$tmp/helm.tar.gz" -C "$tmp/helm"; fi
  mv "$tmp/helm/$os-$arch/helm$exe" "$bin/" && chmod +x "$bin/helm$exe"
fi

if ! has terraform; then
  base="https://releases.hashicorp.com/terraform/$TERRAFORM_VERSION"
  file="terraform_${TERRAFORM_VERSION}_${os}_${arch}.zip"
  log "terraform $TERRAFORM_VERSION"
  curl -fsSL --retry 5 --retry-delay 3 --retry-all-errors "$base/$file" -o "$tmp/$file"
  verify "$tmp/$file" "$(curl -fsSL --retry 5 --retry-delay 3 --retry-all-errors "$base/terraform_${TERRAFORM_VERSION}_SHA256SUMS" | awk -v f="$file" '$2==f {print $1}')"
  unzip_to "$tmp/$file" "$bin"
  chmod +x "$bin/terraform$exe"
fi

rm -rf "$tmp"
ok "tools in $bin (scripts pick them up automatically):"
ls "$bin"
