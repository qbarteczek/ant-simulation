"""Punkt wejścia: menu konfiguracji -> symulacja życia mrówek."""
import sys

import pygame

import config as C
from menu import Menu
from simulation import Simulation


def _make_window():
    """Tworzy okno dopasowane do rozdzielczości ekranu (na małych ekranach
    skaluje w dół, żeby cała zawartość - w tym przycisk startu - była widoczna)."""
    info = pygame.display.Info()
    avail_w = max(info.current_w - 60, 320)
    avail_h = max(info.current_h - 100, 240)
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


def main():
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

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
