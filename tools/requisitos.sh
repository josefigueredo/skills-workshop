#!/bin/bash
# Checks what the team skills workshop needs on a Mac.
# Runs under the stock /bin/bash 3.2: no associative arrays, no mapfile, no `timeout`.
set -u

APPS_DIR="${REQ_APPS_DIR:-/Applications}"
# Where the Homebrew installer puts brew (Apple silicon, Intel), checked when brew is not on PATH.
BREW_DIRS="${REQ_BREW_DIRS:-/opt/homebrew/bin /usr/local/bin}"
OFFLINE=0
REPO=""
FAILS=0
SKIPS=0
GIT_OK=0
SSH_OK=0
BREW_STATE=missing   # ok | offpath | missing
SSH_WHY="primero arreglá la clave SSH"

usage() {
  cat <<'EOF'
Uso: bash requisitos.sh [--repo DUEÑO/NOMBRE] [--offline]

Revisa lo que necesitás para el taller de skills y te dice qué falta:
brew, git, Python 3.9 o más, uv, tmux, jq, Cursor, tu clave SSH en GitHub
y el acceso a un repo de la org.

  --repo DUEÑO/NOMBRE  repo de la org al que tenés que poder entrar
                       (te lo pasa quien organiza el curso)
  --offline            no revisa lo que necesita conexión (SSH y repo)
  -h, --help           muestra esta ayuda

Cada línea dice ✓ (está), ✗ (falta, con cómo arreglarlo) o – (no se revisó).
Termina con 0 si no falta nada y con 1 si falta algo.
EOF
}

ok()   { printf '✓ %s\n' "$1"; }
fail() { printf '✗ %s — %s\n' "$1" "$2"; FAILS=$((FAILS + 1)); }
skip() { printf '– %s (%s)\n' "$1" "$2"; SKIPS=$((SKIPS + 1)); }

# A tool counts only if it answers: on a fresh Mac /usr/bin/git is a shim that fails.
runs() { "$@" >/dev/null 2>&1; }

check_brew() {
  local label="Homebrew (brew)" dir
  if runs brew --version; then ok "$label"; BREW_STATE=ok; return; fi
  # Installed but the installer's «Next steps» were skipped: brew is not on PATH yet.
  for dir in $BREW_DIRS; do
    if [ -x "$dir/brew" ]; then
      BREW_STATE=offpath
      fail "$label" "Está instalado pero la terminal no lo encuentra. Corré: eval \"\$($dir/brew shellenv)\""
      printf "  Para que quede siempre: echo 'eval \"\$(%s/brew shellenv)\"' >> ~/.zprofile\n" "$dir"
      return
    fi
  done
  fail "$label" "Instalalo con el comando de brew.sh (copiar, pegar en la terminal, Enter)"
}

# The fix for something Homebrew installs; it depends on whether brew itself works.
brew_fix() {
  case "$BREW_STATE" in
    ok) printf 'Corré: brew install %s' "$1" ;;
    offpath) printf 'primero arreglá Homebrew (arriba) y volvé a correr esto; si sigue, brew install %s' "$1" ;;
    *) printf 'primero instalá Homebrew (arriba), después: brew install %s' "$1" ;;
  esac
}

check_git() {
  if runs git --version; then ok "git"; GIT_OK=1
  else fail "git" "Corré: xcode-select --install"; fi
}

check_python() {
  local label="Python 3.9 o más (python3)" out re major minor
  out=$(python3 -c 'import sys; print(sys.version_info[:2])' 2>/dev/null) || out=""
  re='^\(([0-9]+), ([0-9]+)\)$'
  if [[ $out =~ $re ]]; then
    major=${BASH_REMATCH[1]}
    minor=${BASH_REMATCH[2]}
    if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 9 ]; }; then
      ok "$label"
    else
      fail "$label" "Tenés Python $major.$minor. $(brew_fix python)"
    fi
  else
    fail "$label" "$(brew_fix python)"
  fi
}

check_tool() {  # name, version flag
  if runs "$1" "$2"; then ok "$1"
  else fail "$1" "$(brew_fix "$1")"; fi
}

check_cursor() {
  if [ -d "$APPS_DIR/Cursor.app" ] || command -v cursor >/dev/null 2>&1; then ok "Cursor"
  else fail "Cursor" "Instalá Cursor desde cursor.com"; fi
}

check_ssh() {
  local label="Clave SSH cargada en GitHub" out
  if [ "$OFFLINE" -eq 1 ]; then skip "$label" "sin conexión, no se revisó"; return; fi
  # GitHub answers the greeting and exits 1: that is the normal, successful case.
  out=$(ssh -T -o BatchMode=yes -o ConnectTimeout=5 git@github.com 2>&1 </dev/null)
  case "$out" in
    *"successfully authenticated"*) ok "$label"; SSH_OK=1 ;;
    # BatchMode cannot answer the first-connection question: the key may be fine.
    *"Host key verification failed"*)
      fail "$label" "Corré una vez: ssh -T git@github.com y respondé yes" ;;
    *"Could not resolve"*|*"timed out"*|*"Network is unreachable"*|*"Connection refused"*)
      SSH_WHY="primero resolvé la conexión"
      fail "$label" "No se pudo llegar a GitHub. Revisá tu conexión a internet y volvé a correr" ;;
    *"Permission denied (publickey)"*)
      fail "$label" "Cargá tu clave SSH en GitHub: docs.github.com/es/authentication/connecting-to-github-with-ssh; si no sabés cómo, pedí ayuda antes del curso" ;;
    *) fail "$label" "Cargá tu clave SSH en GitHub: docs.github.com/es/authentication/connecting-to-github-with-ssh" ;;
  esac
}

check_repo() {
  if [ "$OFFLINE" -eq 1 ]; then
    skip "Acceso al repo ${REPO:-de la org}" "sin conexión, no se revisó"; return
  fi
  if [ -z "$REPO" ]; then skip "Acceso al repo de la org" "no se pasó --repo"; return; fi
  if [ "$GIT_OK" -eq 0 ]; then skip "Acceso al repo $REPO" "primero instalá git"; return; fi
  if [ "$SSH_OK" -eq 0 ]; then skip "Acceso al repo $REPO" "$SSH_WHY"; return; fi
  if GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=5' \
      git ls-remote --heads "git@github.com:$REPO.git" >/dev/null 2>&1 </dev/null; then
    ok "Acceso al repo $REPO"
  else
    fail "Acceso al repo $REPO" "Pedile acceso a quien organiza el curso"
  fi
}

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --offline) OFFLINE=1 ;;
    --repo)
      if [ $# -lt 2 ]; then echo "requisitos.sh: --repo needs OWNER/NAME" >&2; exit 2; fi
      REPO="$2"; shift ;;
    --repo=*) REPO="${1#--repo=}" ;;
    *) echo "requisitos.sh: unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
  shift
done

if [ -n "$REPO" ] && ! [[ $REPO =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]]; then
  echo "requisitos.sh: --repo must look like OWNER/NAME, got: $REPO" >&2
  exit 2
fi

check_brew
check_git
check_python
check_tool uv --version
check_tool tmux -V
check_tool jq --version
check_cursor
check_ssh
check_repo

echo
if [ "$FAILS" -eq 0 ] && [ "$SKIPS" -eq 0 ]; then
  echo "Todo listo."
elif [ "$FAILS" -eq 0 ]; then
  echo "No falta nada de lo que se revisó."
elif [ "$FAILS" -eq 1 ]; then
  echo "Falta 1 cosa."
else
  echo "Faltan $FAILS cosas."
fi
[ "$FAILS" -eq 0 ]
