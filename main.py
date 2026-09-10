"""Punkt wejścia: menu konfiguracji -> symulacja życia mrówek.

Pętla główna jest asynchroniczna (async/await), żeby ten sam kod dało się
uruchomić natywnie (desktop) i w przeglądarce przez pygbag (WebAssembly) -
przeglądarka wymaga oddania sterowania (await asyncio.sleep(0)) w każdej
klatce, inaczej zawiesza kartę.
"""
import asyncio
import sys
import traceback

import pygame

import config as C
from menu import Menu
from simulation import Simulation


def _make_window():
    """Tworzy okno dopasowane do rozdzielczości ekranu (na małych ekranach
    skaluje w dół, żeby cała zawartość - w tym przycisk startu - była widoczna)."""
    try:
        info = pygame.display.Info()
        screen_w, screen_h = info.current_w, info.current_h
        if screen_w <= 0 or screen_h <= 0:
            raise ValueError("nieprawidlowy rozmiar ekranu zgloszony przez SDL")
    except Exception:
        # w przeglądarce (WASM/canvas) pygame.display.Info() bywa niedostępne
        # lub zwraca śmieciowe wartości przed pierwszym set_mode - bezpieczny
        # rozmiar zastępczy zamiast wywalania się tutaj
        screen_w, screen_h = C.WIDTH, C.HEIGHT
    avail_w = max(screen_w - 60, 320)
    avail_h = max(screen_h - 100, 240)
    scale = min(1.0, avail_w / C.WIDTH, avail_h / C.HEIGHT)
    win_size = (max(1, int(C.WIDTH * scale)), max(1, int(C.HEIGHT * scale)))
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


async def _run():
    pygame.init()
    pygame.display.set_caption("Symulacja życia mrówek")
    screen = _make_window()
    virtual = pygame.Surface((C.WIDTH, C.HEIGHT))
    clock = pygame.time.Clock()

    state = "MENU"
    menu = Menu()
    sim = None
    last_cfg = None
    running = True

    while running:
        dt = min(clock.tick(C.FPS) / 1000.0, 0.05)

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
