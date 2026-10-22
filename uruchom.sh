#!/bin/sh
# Uruchamia symulację mrówek niezależnie od bieżącego katalogu roboczego.
# Przy pierwszym uruchomieniu (lub jeśli środowisko wirtualne jest niekompletne
# albo utworzone w innym środowisku) sam odtwarza venv i instaluje zależności.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/venv"
PY="$VENV/bin/python"

check_ok() {
    "$PY" -c "import pygame, numpy; pygame.font.init(); pygame.font.Font(None, 12)" >/dev/null 2>&1
}

if [ ! -x "$PY" ] || ! check_ok; then
    echo "[uruchom.sh] Przygotowuję środowisko Pythona (pierwsze uruchomienie lub naprawa venv)..." >&2
    rm -rf "$VENV"
    if ! python3 -m venv "$VENV" >&2; then
        echo "[uruchom.sh] BŁĄD: nie udało się utworzyć venv. Zainstaluj pakiet python3-venv (lub odpowiednik dla Twojej dystrybucji) i spróbuj ponownie." >&2
        exit 1
    fi
    "$PY" -m pip install --quiet --upgrade pip >&2
    # Zwykły pakiet "pygame" długo nie nadąża z wydaniami dla nowych wersji
    # Pythona (brak gotowych paczek -> błędy przy imporcie, np. modułu czcionek).
    # pygame-ce (community edition) to w pełni zgodny zamiennik (ten sam
    # "import pygame") z szybszym wsparciem nowych wersji Pythona.
    if ! "$PY" -m pip install --quiet pygame-ce numpy anthropic >&2; then
        echo "[uruchom.sh] BŁĄD: nie udało się zainstalować pygame-ce/numpy przez pip." >&2
        exit 1
    fi
    if ! check_ok; then
        echo "[uruchom.sh] BŁĄD: pygame zainstalował się, ale nie działa poprawnie w tej wersji Pythona." >&2
        exit 1
    fi
    echo "[uruchom.sh] Środowisko gotowe." >&2
fi

# Jeśli okno się nie pojawia (np. błąd sterownika Wayland w SDL2 na niektórych
# wersjach KDE/KWin), spróbuj wymusić X11 przez XWayland:
#   SDL_VIDEODRIVER=x11 ./uruchom.sh

exec "$PY" "$DIR/main.py"
