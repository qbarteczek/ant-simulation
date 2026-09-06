"""Świat symulacji: inicjalizacja sceny, pętla aktualizacji i rysowanie."""
import math
import random

import numpy as np
import pygame
from pygame.math import Vector2

import config as C
from entities import AphidCluster, Ladybug, Nest, Obstacle, Plant, Spider
from pheromone import PheromoneGrid
from swarm import AntSwarm


class Simulation:
    def __init__(self, cfg):
        self.cfg = cfg
        self.biome = C.BIOMES[cfg["biome"]]
        self.season = C.SEASONS[cfg["season"]]
        self.species_name = cfg["species"]
        self.mods = dict(
            food_regen=self.biome["food_regen"] * self.season["food_regen"],
            activity=self.season["activity"],
            spawn=self.season["spawn"],
            predator=self.season["predator"],
        )
        # im większa kolonia na start, tym więcej roślin w otoczeniu -
        # bez tego środowisko nastawione na ~40 mrówek nie wyżywiłoby tysięcy
        self.economy_scale = max(1.0, cfg["ant_count"] / 40)

        self.pher = PheromoneGrid()
        self.nest = Nest((C.WIDTH / 2, C.HEIGHT / 2))
        self.obstacles = self._make_obstacles()
        self.plants = self._make_plants()
        self.aphids = self._make_aphid_clusters(cfg["companions"].get("Mszyce", 0))
        self.spiders = [
            Spider(self._random_pos(150)) for _ in range(cfg["companions"].get("Pająki", 0))
        ]
        self.ladybugs = [
            Ladybug(self._random_pos(100)) for _ in range(cfg["companions"].get("Biedronki", 0))
        ]

        self.ant_swarm = AntSwarm(C.MAX_POPULATION, self.species_name, cfg["biome"])
        self.ant_swarm.spawn(cfg["ant_count"], self.nest.pos)

        self.time = 0.0
        self.daylight = 1.0
        self.paused = False
        self.speed_idx = 0
        self.speed_mult = C.SPEED_LEVELS[self.speed_idx]
        self.bg_surface = self._build_background()
        self.font = pygame.font.Font(None, 20)

    # --- inicjalizacja sceny -------------------------------------------------
    def _random_pos(self, min_dist_from_nest=80, margin=40):
        for _ in range(200):
            x = random.uniform(margin, C.WIDTH - margin)
            y = random.uniform(margin, C.HEIGHT - margin)
            if Vector2(x, y).distance_to(self.nest.pos) >= min_dist_from_nest:
                return Vector2(x, y)
        return Vector2(margin, margin)

    def _make_obstacles(self):
        count = self.biome["obstacle_density"]
        obstacles = []
        for _ in range(count):
            pos = self._random_pos(90)
            radius = random.randint(10, 22)
            obstacles.append(Obstacle(pos, radius))
        return obstacles

    def _make_plants(self):
        count = min(
            C.MAX_PLANTS,
            max(4, int(C.PLANT_COUNT_BASE * self.biome["food_density"] * self.economy_scale)),
        )
        plants = []
        for _ in range(count):
            pos = self._random_pos(140)
            plants.append(Plant(pos, mature=True))
        return plants

    def _make_aphid_clusters(self, total_aphids):
        if total_aphids <= 0:
            return []
        n_clusters = max(1, min(8, total_aphids // 6))
        base, rem = divmod(total_aphids, n_clusters)
        clusters = []
        for i in range(n_clusters):
            cnt = base + (1 if i < rem else 0)
            if cnt <= 0:
                continue
            host = random.choice(self.plants) if self.plants else None
            if host is not None:
                pos = host.pos + Vector2(random.uniform(-18, 18), random.uniform(-18, 18))
            else:
                pos = self._random_pos(110)
            clusters.append(AphidCluster(pos, cnt, host_plant=host))
        return clusters

    def _build_background(self):
        surf = pygame.Surface((C.WIDTH, C.HEIGHT))
        surf.fill(self.biome["bg"])
        rng = random.Random(1234)
        for _ in range(900):
            x = rng.randint(0, C.WIDTH)
            y = rng.randint(0, C.HEIGHT)
            r = rng.randint(1, 3)
            pygame.draw.circle(surf, self.biome["bg2"], (x, y), r)
        return surf

    # --- zapytania świata używane przez byty ---------------------------------
    def all_forageables(self):
        return [p for p in self.plants if p.amount > 0.5] + [a for a in self.aphids if a.amount > 0.5]

    def nearest_aphid_cluster_within(self, pos, radius):
        best, bestd = None, None
        for c in self.aphids:
            d = pos.distance_to(c.pos)
            if d <= radius and (bestd is None or d < bestd):
                bestd, best = d, c
        return best

    def ants_near(self, pos, radius):
        """Indeksy i pozycje żywych mrówek w promieniu - używane przez pająki."""
        swarm = self.ant_swarm
        n = swarm.n
        if n == 0:
            empty = np.empty(0, dtype=np.float32)
            return np.empty(0, dtype=np.int64), empty, empty
        dx = swarm.x[:n] - pos.x
        dy = swarm.y[:n] - pos.y
        mask = (dx * dx + dy * dy) <= radius * radius
        idx = np.nonzero(mask)[0]
        return idx, swarm.x[idx], swarm.y[idx]

    def kill_ants(self, idx):
        if idx.size:
            self.ant_swarm.kill(idx)

    # --- interakcje myszą -----------------------------------------------------
    def add_food_at(self, pos):
        if len(self.plants) < C.MAX_PLANTS:
            self.plants.append(Plant(Vector2(pos), mature=True))

    def add_obstacle_at(self, pos):
        self.obstacles.append(Obstacle(Vector2(pos), random.randint(12, 22)))

    # --- sterowanie prędkością -------------------------------------------------
    def speed_up(self):
        self.speed_idx = min(len(C.SPEED_LEVELS) - 1, self.speed_idx + 1)
        self.speed_mult = C.SPEED_LEVELS[self.speed_idx]

    def speed_down(self):
        self.speed_idx = max(0, self.speed_idx - 1)
        self.speed_mult = C.SPEED_LEVELS[self.speed_idx]

    # --- aktualizacja ---------------------------------------------------------
    def update(self, raw_dt):
        if self.paused:
            return
        # szybkość osiągana przez wielokrotne wykonanie kroku o tym samym małym
        # dt (a nie jeden duży krok) - inaczej przy x20 mrówki "przeskakiwałyby"
        # przez przeszkody i granice zamiast się od nich odbijać
        for _ in range(int(self.speed_mult)):
            self._update_once(raw_dt)

    def _update_once(self, dt):
        self.time += dt
        phase = (self.time % C.DAY_LENGTH_SECONDS) / C.DAY_LENGTH_SECONDS
        self.daylight = 0.5 + 0.5 * math.cos(2 * math.pi * phase)
        night_factor = C.DAY_NIGHT_MIN_ACTIVITY + (1 - C.DAY_NIGHT_MIN_ACTIVITY) * self.daylight
        self.mods["activity"] = self.season["activity"] * night_factor

        self.ant_swarm.update(dt, self)
        self._resolve_ant_spider_combat(dt)

        newborn_spiders = []
        for s in self.spiders:
            child = s.update(dt, self)
            if child is not None:
                newborn_spiders.append(child)
        self.spiders = [s for s in self.spiders if s.alive] + newborn_spiders

        newborn_ladybugs = []
        for lb in self.ladybugs:
            child = lb.update(dt, self)
            if child is not None:
                newborn_ladybugs.append(child)
        self.ladybugs = [lb for lb in self.ladybugs if lb.alive] + newborn_ladybugs

        for c in self.aphids:
            c.update(dt, self)

        newborn_plants = []
        for p in self.plants:
            child = p.update(dt, self)
            if child is not None:
                newborn_plants.append(child)
        self.plants.extend(newborn_plants)

        self.pher.evaporate(dt)
        self._handle_spawning()

    def _resolve_ant_spider_combat(self, dt):
        swarm = self.ant_swarm
        for sp in self.spiders:
            if not sp.alive:
                continue
            idx, _, _ = self.ants_near(sp.pos, C.SPIDER_ATTACK_RADIUS)
            if idx.size == 0:
                continue
            # tylko mrówki, które faktycznie zauważyły zagrożenie i się bronią -
            # nie te, które akurat przechodziły obok w swoich sprawach
            idx = idx[swarm.in_combat[idx]]
            if idx.size == 0:
                continue
            # pojedyncza mrówka rzadko coś zdziała - dopiero liczny rój
            # ma realną szansę zabić pająka w rozsądnym czasie
            # (siła jest teraz cechą dziedziczoną per mrówka, więc silniejsze
            # linie genetyczne realnie skuteczniej bronią kolonii)
            hit_chance = 0.15 * swarm.strength[idx] * dt
            hits = np.random.random(idx.size) < hit_chance
            sp.hp -= int(hits.sum())

    def _handle_spawning(self):
        # dolny próg mnożnika NIE może być zbyt niski - inaczej zimą próg
        # zakupu nowej robotnicy staje się praktycznie nieosiągalny i kolonia
        # usycha mimo pełnego magazynu jedzenia (pułapka wymarcia)
        effective_cost = C.SPAWN_FOOD_COST / max(0.4, self.mods["spawn"])
        capacity_left = self.ant_swarm.capacity - self.ant_swarm.n
        if capacity_left <= 0 or self.nest.food < effective_cost:
            return
        affordable = int(self.nest.food // effective_cost)
        count = min(affordable, capacity_left)
        if count > 0:
            self.nest.food -= count * effective_cost
            self.ant_swarm.spawn(count, self.nest.pos)

    # --- rysowanie --------------------------------------------------------------
    def draw(self, surface):
        surface.blit(self.bg_surface, (0, 0))

        for obs in self.obstacles:
            self._draw_obstacle(surface, obs)
        for p in self.plants:
            self._draw_plant(surface, p)
        for cl in self.aphids:
            self._draw_aphid_cluster(surface, cl)
        self._draw_nest(surface)

        self.pher.render(surface)

        self._draw_ants(surface)
        for sp in self.spiders:
            self._draw_spider(surface, sp)
        for lb in self.ladybugs:
            self._draw_ladybug(surface, lb)

        tint = self.season["tint"]
        if tint is not None:
            overlay = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
            overlay.fill(tint)
            surface.blit(overlay, (0, 0))

        night_alpha = int(C.NIGHT_OVERLAY_MAX_ALPHA * (1 - self.daylight))
        if night_alpha > 4:
            overlay = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
            overlay.fill((10, 15, 45, night_alpha))
            surface.blit(overlay, (0, 0))

        self._draw_hud(surface)

    def _draw_obstacle(self, surface, obs):
        shape = self.biome["obstacle_shape"]
        color = self.biome["obstacle_color"]
        x, y = int(obs.pos.x), int(obs.pos.y)
        if shape == "tuft":
            for dx, dy in ((-4, 2), (4, 2), (0, -3)):
                pygame.draw.circle(surface, color, (x + dx, y + dy), max(4, obs.radius // 2))
        elif shape == "log":
            rect = pygame.Rect(0, 0, obs.radius * 2, obs.radius)
            rect.center = (x, y)
            pygame.draw.ellipse(surface, color, rect)
            pygame.draw.ellipse(surface, (30, 20, 15), rect, width=2)
        else:
            pygame.draw.circle(surface, color, (x, y), obs.radius)
            pygame.draw.circle(surface, (110, 90, 60), (x, y), obs.radius, width=2)

    def _draw_plant(self, surface, p):
        x, y = int(p.pos.x), int(p.pos.y)
        if p.growth < 1.0:
            r = max(2, int(p.radius))
            pygame.draw.circle(surface, (120, 170, 80), (x, y), r)
            return
        frac = max(0.2, p.stock / C.PLANT_STOCK_MAX)
        r = int(p.radius)
        pygame.draw.circle(surface, (60, 110, 40), (x, y), r, width=2)
        pygame.draw.circle(surface, (100, 175, 70), (x, y), max(3, int(r * frac)))

    def _draw_aphid_cluster(self, surface, cl):
        bx, by = int(cl.pos.x), int(cl.pos.y)
        if cl.honeydew > 1:
            glow_r = 10 + int(10 * min(1, cl.honeydew / C.APHID_HONEYDEW_MAX))
            s = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (230, 210, 120, 90), (glow_r, glow_r), glow_r)
            surface.blit(s, (bx - glow_r, by - glow_r))
        for i in range(cl.count):
            ang = (2 * math.pi / max(1, cl.count)) * i
            px = bx + int(math.cos(ang) * 8)
            py = by + int(math.sin(ang) * 8)
            pygame.draw.circle(surface, (140, 200, 90), (px, py), 3)

    def mound_level(self):
        """Poziom rozbudowy kopca mrowiska - rośnie wraz z populacją, czyli
        realnym sukcesem kolonii (więcej robotnic kopie i buduje więcej)."""
        return min(6, self.ant_swarm.n // 40)

    def _draw_nest(self, surface):
        x, y = int(self.nest.pos.x), int(self.nest.pos.y)
        level = self.mound_level()
        mound_bonus = level * 4.5
        r = int(self.nest.radius + mound_bonus)
        layers = 2 + level // 2
        for i in range(layers, 0, -1):
            t = i / layers
            layer_r = max(6, int(r * t))
            shade = 92 - i * 5
            pygame.draw.circle(surface, (shade, int(shade * 0.66), int(shade * 0.33)), (x, y), layer_r)
        pygame.draw.circle(surface, (60, 40, 20), (x, y), r, width=2)
        pygame.draw.circle(surface, (20, 15, 10), (x, y), 6)

        if level > 0:
            n_pellets = level * 5
            for i in range(n_pellets):
                ang = (2 * math.pi / n_pellets) * i + 0.3
                dist = r + 5 + (i % 3) * 4
                px = x + int(math.cos(ang) * dist)
                py = y + int(math.sin(ang) * dist)
                pygame.draw.circle(surface, (70, 48, 26), (px, py), 2)

    def _draw_ants(self, surface):
        swarm = self.ant_swarm
        n = swarm.n
        if n == 0:
            return
        if n <= 400:
            self._draw_ants_detailed(surface, swarm, n)
        else:
            self._draw_ants_fast(surface, swarm, n)

    def _draw_ants_detailed(self, surface, swarm, n):
        color = swarm.color
        for i in range(n):
            x, y = int(swarm.x[i]), int(swarm.y[i])
            pygame.draw.circle(surface, color, (x, y), 3)
            hx = x + int(math.cos(swarm.angle[i]) * 5)
            hy = y + int(math.sin(swarm.angle[i]) * 5)
            pygame.draw.line(surface, color, (x, y), (hx, hy), 1)
            if swarm.carrying[i]:
                pygame.draw.circle(surface, (255, 215, 60), (x, y), 2)
            if swarm.in_combat[i]:
                pygame.draw.circle(surface, (255, 40, 40), (x, y), 5, width=1)

    def _draw_ants_fast(self, surface, swarm, n):
        xs = np.clip(swarm.x[:n].astype(np.int32), 0, C.WIDTH - 1)
        ys = np.clip(swarm.y[:n].astype(np.int32), 0, C.HEIGHT - 1)
        arr = pygame.surfarray.pixels3d(surface)
        arr[xs, ys] = swarm.color
        xs2 = np.clip(xs + 1, 0, C.WIDTH - 1)
        ys2 = np.clip(ys + 1, 0, C.HEIGHT - 1)
        arr[xs2, ys] = swarm.color
        arr[xs, ys2] = swarm.color
        carrying = swarm.carrying[:n]
        if carrying.any():
            arr[xs[carrying], ys[carrying]] = (255, 215, 60)
        del arr

    def _draw_spider(self, surface, sp):
        x, y = int(sp.pos.x), int(sp.pos.y)
        pygame.draw.circle(surface, (30, 20, 20), (x, y), 7)
        for i in range(4):
            ang = sp.angle + i * 0.5 - 0.75
            lx = x + int(math.cos(ang) * 10)
            ly = y + int(math.sin(ang) * 10)
            pygame.draw.line(surface, (20, 15, 15), (x, y), (lx, ly), 1)
        if sp.hp < C.SPIDER_HP:
            w = 16
            frac = max(0, sp.hp) / C.SPIDER_HP
            pygame.draw.rect(surface, (60, 0, 0), (x - w // 2, y - 13, w, 3))
            pygame.draw.rect(surface, (200, 20, 20), (x - w // 2, y - 13, int(w * frac), 3))

    def _draw_ladybug(self, surface, lb):
        x, y = int(lb.pos.x), int(lb.pos.y)
        pygame.draw.circle(surface, (200, 30, 30), (x, y), 4)
        pygame.draw.circle(surface, (20, 20, 20), (x, y), 4, width=1)
        pygame.draw.circle(surface, (20, 20, 20), (x - 1, y - 1), 1)

    def _evolution_line(self, n):
        if n == 0:
            return "Ewolucja: brak żywej populacji"
        swarm = self.ant_swarm
        speed = float(swarm.speed_mult[:n].mean())
        drain = float(swarm.drain_mult[:n].mean())
        strength = float(swarm.strength[:n].mean())
        sense = float(swarm.sense_mult[:n].mean())
        return (
            f"Ewolucja (śr. cechy kolonii): szybkość x{speed:.2f}  metabolizm x{drain:.2f}"
            f"  siła x{strength:.2f}  węch x{sense:.2f}"
        )

    def _draw_hud(self, surface):
        n = self.ant_swarm.n
        day_label = "Dzień" if self.daylight >= 0.5 else "Noc"
        lines = [
            f"Biom: {self.cfg['biome']}   Pora roku: {self.cfg['season']}   Gatunek: {self.cfg['species']}",
            f"Populacja: {n}/{C.MAX_POPULATION}   Jedzenie w gnieździe: {int(self.nest.food)}"
            f"   Rośliny: {len(self.plants)}/{C.MAX_PLANTS}   Kopiec: poziom {self.mound_level()}/6",
            f"Mszyce: {sum(c.count for c in self.aphids)}   Pająki: {len(self.spiders)}   Biedronki: {len(self.ladybugs)}",
            f"Dzień symulacji: {self.time / C.DAY_LENGTH_SECONDS:.2f} ({day_label})   Prędkość: x{self.speed_mult}"
            + ("   [PAUZA]" if self.paused else ""),
            self._evolution_line(n),
            "SPACJA=pauza  +/-=predkosc(x1..x20)  ESC=menu  R=reset  LPM=zasadz roslinę  PPM=przeszkoda",
        ]
        box_h = 18 * len(lines) + 14
        panel = pygame.Surface((640, box_h), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 140))
        surface.blit(panel, (8, 8))
        for i, line in enumerate(lines):
            txt = self.font.render(line, True, (255, 255, 255))
            surface.blit(txt, (16, 12 + i * 18))
