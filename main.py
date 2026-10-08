"""Punkt wejścia: menu konfiguracji -> symulacja życia mrówek.

Pętla główna jest asynchroniczna (async/await), żeby ten sam kod dało się
uruchomić natywnie (desktop) i w przeglądarce przez pygbag (WebAssembly) -
przeglądarka wymaga oddania sterowania (await asyncio.sleep(0)) w każdej
klatce, inaczej zawiesza kartę.

Blok niżej to metadane PEP 723 - pygbag (NIE Pyodide, więc bez micropip)
skanuje go, żeby wiedzieć jakie paczki realnie zainstalować (nie tylko
pobrać do cache) do sys.path przed uruchomieniem main.py w przeglądarce.
"""
# /// script
# dependencies = ["numpy"]
# ///
import asyncio
import sys
import traceback

import pygame

import config as C
from menu import Menu

# "Simulation" (i przez nie numpy) importowane leniwie w main() dopiero po
# narysowaniu ekranu ładowania - import numpy bywa bardzo wolny/zawodny w
# WebAssembly, a leniwy import pozwala pokazać komunikat i złapać ewentualny
# wyjątek zamiast wywalać się jeszcze przed uruchomieniem pętli try/except


def _query_screen_size():
    try:
        info = pygame.display.Info()
        screen_w, screen_h = info.current_w, info.current_h
        if screen_w <= 0 or screen_h <= 0:
            raise ValueError("nieprawidlowy rozmiar ekranu zgloszony przez SDL")
        return screen_w, screen_h
    except Exception:
        # w przeglądarce (WASM/canvas) pygame.display.Info() bywa niedostępne
        # lub zwraca śmieciowe wartości przed pierwszym set_mode - bezpieczny
        # rozmiar zastępczy zamiast wywalania się tutaj
        return C.WIDTH, C.HEIGHT


def _fit_size(screen_w, screen_h):
    # w przeglądarce nie ma paska tytułu/ramki okna do odjęcia jak na
    # desktopie - canvas ma zajmować praktycznie całą dostępną przestrzeń
    margin_w, margin_h = (10, 10) if sys.platform == "emscripten" else (60, 100)
    avail_w = max(screen_w - margin_w, 320)
    avail_h = max(screen_h - margin_h, 240)
    scale = min(1.0, avail_w / C.WIDTH, avail_h / C.HEIGHT)
    return (max(1, int(C.WIDTH * scale)), max(1, int(C.HEIGHT * scale)))


def _make_window():
    """Tworzy okno dopasowane do rozdzielczości ekranu (na małych ekranach
    skaluje w dół, żeby cała zawartość - w tym przycisk startu - była widoczna)."""
    win_size = _fit_size(*_query_screen_size())
    screen = pygame.display.set_mode(win_size, pygame.RESIZABLE)
    return screen


def _to_virtual(pos, screen):
    sw, sh = screen.get_size()
    return (pos[0] * C.WIDTH / sw, pos[1] * C.HEIGHT / sh)


def _rescale_event(event, screen):
    if event.type == pygame.MOUSEBUTTONDOWN:
        return pygame.event.Event(event.type, button=event.button, pos=_to_virtual(event.pos, screen))
    return event


async def _show_fatal_error(message):
    """Rysuje treść wyjątku bezpośrednio na canvasie i zostaje na nim -
    w przeglądarce traceback z konsoli bywa trudno dostępny/niewidoczny,
    więc to najpewniejszy sposób, żeby błąd był w ogóle widoczny."""
    pygame.font.init()
    screen = pygame.display.set_mode((900, 600))
    pygame.display.set_caption("Błąd uruchamiania symulacji")
    font = pygame.font.Font(None, 20)
    lines = message.splitlines() or ["(brak treści błędu)"]
    while True:
        screen.fill((20, 10, 10))
        title = font.render("Symulacja nie uruchomiła się - szczegóły błędu:", True, (255, 210, 90))
        screen.blit(title, (16, 12))
        for i, line in enumerate(lines[:32]):
            txt = font.render(line, True, (255, 120, 110))
            screen.blit(txt, (16, 40 + i * 18))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        pygame.display.flip()
        await asyncio.sleep(0)


async def _load_simulation_module(screen):
    """Import "simulation" (a przez nie numpy) leniwie, z widocznym na
    canvasie komunikatem ładowania - import numpy bywa bardzo wolny w
    WebAssembly (rzędu dziesiątek sekund/kilku minut), więc bez tego
    strona wygląda na zawieszoną/pustą przez cały ten czas."""
    font = pygame.font.Font(None, 24)
    screen.fill((25, 30, 25))
    msg = "Ładowanie silnika symulacji (numpy)... to może potrwać do kilku minut w przeglądarce."
    screen.blit(font.render(msg, True, (230, 230, 210)), (16, 16))
    pygame.display.flip()
    for _ in range(3):
        await asyncio.sleep(0)

    # instalacja numpy (jeśli potrzebna) załatwiona przez pygbag na podstawie
    # bloku PEP 723 na górze tego pliku - tu tylko zwykły import
    from simulation import Simulation

    return Simulation


async def _run():
    pygame.init()
    pygame.display.set_caption("Symulacja życia mrówek")
    screen = _make_window()
    Simulation = await _load_simulation_module(screen)
    virtual = pygame.Surface((C.WIDTH, C.HEIGHT))
    clock = pygame.time.Clock()

    state = "MENU"
    menu = Menu()
    sim = None
    last_cfg = None
    running = True
    is_web = sys.platform == "emscripten"
    last_screen_size = _query_screen_size()
    resize_check_timer = 0.0

    while running:
        dt = min(clock.tick(C.FPS) / 1000.0, 0.05)

        # w przeglądarce zmiana rozmiaru okna nie zawsze dociera jako
        # pygame.VIDEORESIZE (pygbag tego nie gwarantuje) - dopytujemy więc
        # okresowo o realny rozmiar i sami dopasowujemy okno, gdy się zmieni
        if is_web:
            resize_check_timer -= dt
            if resize_check_timer <= 0:
                resize_check_timer = 0.5
                current_size = _query_screen_size()
                if current_size != last_screen_size:
                    last_screen_size = current_size
                    screen = pygame.display.set_mode(_fit_size(*current_size), pygame.RESIZABLE)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            else:
                event = _rescale_event(event, screen)
                if state == "MENU":
                    cfg = menu.handle_event(event)
                    if cfg is not None:
                        last_cfg = cfg
                        sim = Simulation(cfg)
                        state = "SIM"
                elif state == "SIM":
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            state = "MENU"
                        elif event.key == pygame.K_SPACE:
                            sim.paused = not sim.paused
                        elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                            sim.speed_up()
                        elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                            sim.speed_down()
                        elif event.key == pygame.K_r and last_cfg is not None:
                            sim = Simulation(last_cfg)
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:
                            sim.add_food_at(event.pos)
                        elif event.button == 3:
                            sim.add_obstacle_at(event.pos)

        if state == "MENU":
            menu.draw(virtual)
        else:
            sim.update(dt)
            sim.draw(virtual)

        if screen.get_size() == (C.WIDTH, C.HEIGHT):
            screen.blit(virtual, (0, 0))
        else:
            pygame.transform.smoothscale(virtual, screen.get_size(), screen)
        pygame.display.flip()
        await asyncio.sleep(0)

    pygame.quit()
    sys.exit()


async def main():
    try:
        await _run()
    except SystemExit:
        raise
    except Exception:
        await _show_fatal_error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())
