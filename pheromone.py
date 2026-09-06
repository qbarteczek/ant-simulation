"""Siatka feromonów: dwa kanały (powrót do gniazda / do jedzenia)."""
import numpy as np
import pygame

import config as C


class PheromoneGrid:
    def __init__(self):
        self.home = np.zeros((C.GRID_H, C.GRID_W), dtype=np.float32)
        self.food = np.zeros((C.GRID_H, C.GRID_W), dtype=np.float32)
        self._surf = pygame.Surface((C.GRID_W, C.GRID_H), pygame.SRCALPHA)

    def _clamp_cell(self, x, y):
        cx = min(max(int(x // C.CELL), 0), C.GRID_W - 1)
        cy = min(max(int(y // C.CELL), 0), C.GRID_H - 1)
        return cx, cy

    def deposit(self, channel, x, y, amount=C.PHEROMONE_DEPOSIT):
        grid = self.home if channel == "home" else self.food
        cx, cy = self._clamp_cell(x, y)
        grid[cy, cx] = min(C.PHEROMONE_MAX, grid[cy, cx] + amount)

    def sample(self, channel, x, y):
        grid = self.home if channel == "home" else self.food
        cx, cy = self._clamp_cell(x, y)
        return grid[cy, cx]

    def deposit_bulk(self, channel, xs, ys, amount=C.PHEROMONE_DEPOSIT):
        """Wektorowy depozyt feromonu dla wielu mrówek naraz (numpy).

        Używa np.add.at, żeby kilka mrówek trafiających w tę samą komórkę
        siatki w tej samej klatce poprawnie się sumowało (zwykłe przypisanie
        przez fancy-indexing nadpisywałoby wartości zamiast je dodawać).
        """
        if xs.size == 0:
            return
        grid = self.home if channel == "home" else self.food
        cx = np.clip((xs // C.CELL).astype(np.int32), 0, C.GRID_W - 1)
        cy = np.clip((ys // C.CELL).astype(np.int32), 0, C.GRID_H - 1)
        np.add.at(grid, (cy, cx), amount)
        np.clip(grid, 0, C.PHEROMONE_MAX, out=grid)

    def sample_bulk(self, channel, xs, ys):
        grid = self.home if channel == "home" else self.food
        cx = np.clip((xs // C.CELL).astype(np.int32), 0, C.GRID_W - 1)
        cy = np.clip((ys // C.CELL).astype(np.int32), 0, C.GRID_H - 1)
        return grid[cy, cx]

    def evaporate(self, dt):
        factor = C.PHEROMONE_EVAPORATION ** (dt * 60.0)
        self.home *= factor
        self.food *= factor

    def render(self, target_surface):
        self._surf.fill((0, 0, 0, 0))
        # kanał "food" -> zielony, kanał "home" -> niebieski
        food_a = np.clip(self.food, 0, C.PHEROMONE_MAX) / C.PHEROMONE_MAX
        home_a = np.clip(self.home, 0, C.PHEROMONE_MAX) / C.PHEROMONE_MAX

        arr = pygame.surfarray.pixels3d(self._surf)
        alpha = pygame.surfarray.pixels_alpha(self._surf)
        # numpy arrays są (row=y, col=x); pygame surfarray chce (x, y)
        food_t = (food_a.T * 255).astype(np.uint8)
        home_t = (home_a.T * 255).astype(np.uint8)

        arr[:, :, 1] = np.maximum(arr[:, :, 1], food_t)  # zielony = jedzenie
        arr[:, :, 2] = np.maximum(arr[:, :, 2], home_t)  # niebieski = dom
        combined = np.maximum(food_t, home_t)
        alpha[:, :] = (combined * 0.75).astype(np.uint8)
        del arr
        del alpha

        scaled = pygame.transform.smoothscale(self._surf, (C.WIDTH, C.HEIGHT))
        target_surface.blit(scaled, (0, 0))
