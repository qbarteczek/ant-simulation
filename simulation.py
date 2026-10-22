"""Świat symulacji: inicjalizacja sceny, pętla aktualizacji i rysowanie."""
import math
import random

import numpy as np
import pygame
from pygame.math import Vector2

import config as C
from entities import (
    AphidCluster,
    Beetle,
    BirdFlock,
    Corpse,
    Earthworm,
    Ladybug,
    Nest,
    Obstacle,
    Plant,
    Spider,
    Wasp,
)
from agenci import ZarzadAgentow
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
        self.wasps = [
            Wasp(self._random_pos(150)) for _ in range(cfg["companions"].get("Osy", 0))
        ]
        self.beetles = [
            Beetle(self._random_pos(80)) for _ in range(cfg["companions"].get("Chrząszcze", 0))
        ]
        self.earthworms = [
            Earthworm(self._random_pos(60)) for _ in range(cfg["companions"].get("Dżdżownice", 0))
        ]
        self.corpses = []
        self.bird_flocks = []
        self.bird_cooldown = random.uniform(*C.BIRD_COOLDOWN)

        self.ant_swarm = AntSwarm(C.MAX_POPULATION, self.species_name, cfg["biome"])
        self.ant_swarm.spawn(cfg["ant_count"], self.nest.pos)

        self.time = 0.0
        self.daylight = 1.0
        self.temperature = C.SEASON_TEMP_BASE[cfg["season"]]
        self._temp_noise = 0.0
        self.weather = "clear"  # "clear" | "rain" | "snow" | "drought"
        self.precip_intensity = 0.0
        self.weather_timer = random.uniform(*C.WEATHER_CHECK_INTERVAL)
        self.wind = 0.2
        self._rain_particles = None
        self._snow_particles = None
        self._dust_particles = None
        self.paused = False
        self.speed_idx = 0
        self.speed_mult = C.SPEED_LEVELS[self.speed_idx]
        self.bg_surface = self._build_background()
        self.font = pygame.font.Font(None, 20)
        self.font_small = pygame.font.Font(None, 17)

        # mrówki-agenci Claude (agenci.py); 0 = wyłączone, np. w balance_test.py
        n_agents = cfg.get("agents", 0)
        self.agents = ZarzadAgentow(n_agents, self) if n_agents > 0 else None

    def close(self):
        """Zatrzymuje wątki zapytań do Claude (przy wyjściu, resecie, powrocie do menu)."""
        if self.agents is not None:
            self.agents.zamknij()

    def toggle_agent_panel(self):
        if self.agents is not None:
            self.agents.pokaz_panel = not self.agents.pokaz_panel

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
        mix = self.biome["plant_mix"]
        species_names = list(mix.keys())
        weights = list(mix.values())
        plants = []
        for _ in range(count):
            pos = self._random_pos(140)
            species_name = random.choices(species_names, weights=weights, k=1)[0]
            plants.append(Plant(pos, species_name, mature=True))
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

    def nearest_corpse_within(self, pos, radius):
        best, bestd = None, None
        for c in self.corpses:
            d = pos.distance_to(c.pos)
            if d <= radius and (bestd is None or d < bestd):
                bestd, best = d, c
        return best

    def nearest_plant_within(self, pos, radius):
        best, bestd = None, None
        for p in self.plants:
            d = pos.distance_to(p.pos)
            if d <= radius and (bestd is None or d < bestd):
                bestd, best = d, p
        return best

    def fertilize_near(self, pos, radius, amount):
        for p in self.plants:
            if pos.distance_to(p.pos) <= radius:
                p.fertilize(amount)

    def spawn_corpse(self, pos, kind):
        if len(self.corpses) >= C.MAX_CORPSES:
            return
        self.corpses.append(Corpse(pos, kind))

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
            mix = self.biome["plant_mix"]
            species_name = random.choices(list(mix.keys()), weights=list(mix.values()), k=1)[0]
            self.plants.append(Plant(Vector2(pos), species_name, mature=True))

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
        mean, amplitude = C.SEASON_DAYLIGHT_PARAMS[self.cfg["season"]]
        self.daylight = max(0.03, min(1.0, mean + amplitude * math.cos(2 * math.pi * phase)))

        self._update_weather(dt)

        temp_factor = self._temperature_activity_factor(self.temperature)
        precip_factor = 1.0
        food_weather_factor = 1.0
        if self.weather == "rain":
            precip_factor = 1.0 - 0.35 * self.precip_intensity
            food_weather_factor = 1.0 + 0.25 * self.precip_intensity
        elif self.weather == "snow":
            precip_factor = 1.0 - 0.45 * self.precip_intensity
            food_weather_factor = 1.0 - 0.5 * self.precip_intensity
        elif self.weather == "drought":
            food_weather_factor = 1.0 - 0.45 * self.precip_intensity
        wind_factor = 1.0 - 0.15 * self.wind

        # kilka mnożników z osobna mogłoby zbić aktywność do zera w skrajnej
        # pogodzie (mróz + śnieżyca + noc naraz) - twardy dolny próg chroni
        # przed pułapką wymarcia, tak jak przy poprzednich poprawkach balansu
        weather_activity = max(0.3, temp_factor * precip_factor * wind_factor)
        self.mods["activity"] = self.season["activity"] * weather_activity
        self.mods["food_regen"] = (
            self.biome["food_regen"] * self.season["food_regen"] * max(0.4, food_weather_factor)
        )

        self.ant_swarm.update(dt, self)
        if self.agents is not None:
            self.agents.update(dt, self)
        self._resolve_ant_predator_combat(dt)

        newborn_spiders = []
        for s in self.spiders:
            child = s.update(dt, self)
            if child is not None:
                newborn_spiders.append(child)
        self.spiders = [s for s in self.spiders if s.alive] + newborn_spiders

        newborn_wasps = []
        for w in self.wasps:
            child = w.update(dt, self)
            if child is not None:
                newborn_wasps.append(child)
        self.wasps = [w for w in self.wasps if w.alive] + newborn_wasps

        newborn_ladybugs = []
        for lb in self.ladybugs:
            child = lb.update(dt, self)
            if child is not None:
                newborn_ladybugs.append(child)
        self.ladybugs = [lb for lb in self.ladybugs if lb.alive] + newborn_ladybugs

        newborn_beetles = []
        for b in self.beetles:
            child = b.update(dt, self)
            if child is not None:
                newborn_beetles.append(child)
        self.beetles = [b for b in self.beetles if b.alive] + newborn_beetles

        newborn_worms = []
        for ew in self.earthworms:
            child = ew.update(dt, self)
            if child is not None:
                newborn_worms.append(child)
        self.earthworms = [ew for ew in self.earthworms if ew.alive] + newborn_worms

        for c in self.aphids:
            c.update(dt, self)

        newborn_plants = []
        for p in self.plants:
            child = p.update(dt, self)
            if child is not None:
                newborn_plants.append(child)
        self.plants = [p for p in self.plants if p.alive] + newborn_plants

        self.corpses = [c for c in self.corpses if c.update(dt)]
        self._update_bird_flocks(dt)

        self.pher.evaporate(dt, wind=self.wind)
        self._handle_spawning()

    def _update_weather(self, dt):
        season_name = self.cfg["season"]
        base_temp = C.SEASON_TEMP_BASE[season_name] + C.BIOME_TEMP_OFFSET[self.cfg["biome"]]
        day_swing = C.TEMP_DAY_AMPLITUDE * (2 * self.daylight - 1)

        # losowy "pogodowy" dryf temperatury - powracający do zera, żeby nie
        # utrwalać ciągłych ekstremów (Ornstein-Uhlenbeck w uproszczeniu)
        self._temp_noise += random.gauss(0, C.TEMP_NOISE_SIGMA) - self._temp_noise * C.TEMP_NOISE_REVERT
        self._temp_noise = max(-6.0, min(6.0, self._temp_noise))

        precip_cooling = 0.0
        if self.weather == "rain":
            precip_cooling = -2.0 * self.precip_intensity
        elif self.weather == "snow":
            precip_cooling = -3.0 * self.precip_intensity
        elif self.weather == "drought":
            precip_cooling = 2.5 * self.precip_intensity  # susza = fala upałów, nie chłodzenia
        self.temperature = base_temp + day_swing + self._temp_noise + precip_cooling

        # wiatr - wolny losowy spacer w granicach [MIN, MAX]
        self.wind += random.gauss(0, C.WIND_DRIFT_SIGMA) - (self.wind - 0.25) * C.WIND_REVERT
        self.wind = max(C.WIND_MIN, min(C.WIND_MAX, self.wind))

        self.weather_timer -= dt
        if self.weather_timer <= 0:
            if self.weather == "clear":
                roll = random.random()
                snow_p = C.WEATHER_SNOW_CHANCE.get(season_name, 0.0)
                rain_p = C.WEATHER_RAIN_CHANCE.get(season_name, 0.0)
                drought_p = C.WEATHER_DROUGHT_CHANCE.get(season_name, 0.0)
                if roll < snow_p:
                    self.weather = "snow"
                    self.precip_intensity = random.uniform(0.4, 1.0)
                    self.weather_timer = random.uniform(*C.WEATHER_DURATION)
                elif roll < snow_p + rain_p:
                    self.weather = "rain"
                    self.precip_intensity = random.uniform(0.4, 1.0)
                    self.weather_timer = random.uniform(*C.WEATHER_DURATION)
                elif roll < snow_p + rain_p + drought_p:
                    self.weather = "drought"
                    self.precip_intensity = random.uniform(0.4, 1.0)
                    self.weather_timer = random.uniform(*C.WEATHER_DROUGHT_DURATION)
                else:
                    self.weather_timer = random.uniform(*C.WEATHER_CHECK_INTERVAL)
            else:
                self.weather = "clear"
                self.precip_intensity = 0.0
                self.weather_timer = random.uniform(*C.WEATHER_CHECK_INTERVAL)

    @staticmethod
    def _temperature_activity_factor(temp):
        """Owady są zmiennocieplne - ich aktywność silnie zależy od temperatury
        otoczenia. Krzywa w przybliżeniu odpowiada biologii mrówek w klimacie
        umiarkowanym: optimum ok. 18-28°C, mróz = niemal bezruch."""
        if temp <= -10:
            return 0.30
        if temp <= 0:
            return 0.30 + (temp + 10) / 10 * 0.30
        if temp <= 18:
            return 0.60 + (temp - 0) / 18 * 0.40
        if temp <= 28:
            return 1.0
        if temp <= 36:
            return 1.0 - (temp - 28) / 8 * 0.25
        return 0.75

    def _resolve_ant_predator_combat(self, dt):
        swarm = self.ant_swarm
        for sp in self.spiders + self.wasps:
            if not sp.alive:
                continue
            attack_radius = C.SPIDER_ATTACK_RADIUS if isinstance(sp, Spider) else C.WASP_ATTACK_RADIUS
            idx, _, _ = self.ants_near(sp.pos, attack_radius)
            if idx.size == 0:
                continue
            # tylko mrówki, które faktycznie zauważyły zagrożenie i się bronią -
            # nie te, które akurat przechodziły obok w swoich sprawach
            idx = idx[swarm.in_combat[idx]]
            if idx.size == 0:
                continue
            # pojedyncza mrówka rzadko coś zdziała - dopiero liczny rój
            # ma realną szansę zabić drapieżnika w rozsądnym czasie
            # (siła jest teraz cechą dziedziczoną per mrówka, więc silniejsze
            # linie genetyczne realnie skuteczniej bronią kolonii)
            hit_chance = 0.15 * swarm.strength[idx] * dt
            hits = np.random.random(idx.size) < hit_chance
            sp.hp -= int(hits.sum())

    def _update_bird_flocks(self, dt):
        for flock in self.bird_flocks:
            flock.update(dt, self)
        self.bird_flocks = [f for f in self.bird_flocks if f.alive]

        if self.bird_flocks:
            return
        self.bird_cooldown -= dt
        if self.bird_cooldown > 0:
            return

        pressure = len(self.spiders) + len(self.wasps) + len(self.ladybugs)
        if pressure < C.BIRD_TRIGGER_THRESHOLD or len(self.bird_flocks) >= C.MAX_CONCURRENT_BIRD_FLOCKS:
            self.bird_cooldown = random.uniform(*C.BIRD_COOLDOWN)
            return

        edge = random.choice(["top", "bottom", "left", "right"])
        if edge == "top":
            pos = Vector2(random.uniform(0, C.WIDTH), 0)
        elif edge == "bottom":
            pos = Vector2(random.uniform(0, C.WIDTH), C.HEIGHT)
        elif edge == "left":
            pos = Vector2(0, random.uniform(0, C.HEIGHT))
        else:
            pos = Vector2(C.WIDTH, random.uniform(0, C.HEIGHT))
        self.bird_flocks.append(BirdFlock(pos))
        self.bird_cooldown = random.uniform(*C.BIRD_COOLDOWN)

    def _handle_spawning(self):
        # dolny próg mnożnika NIE może być zbyt niski - inaczej zimą próg
        # zakupu nowej robotnicy staje się praktycznie nieosiągalny i kolonia
        # usycha mimo pełnego magazynu jedzenia (pułapka wymarcia)
        effective_cost = C.SPAWN_FOOD_COST / max(0.4, self.mods["spawn"])
        capacity_left = self.ant_swarm.capacity - self.ant_swarm.n
        # rezerwa jedzenia NIEnaruszalna przez zakup nowych robotnic - bez niej
        # kolonia potrafi w jednej chwili wydać cały zapas na "boom" nowych
        # mrówek, zostawiając 0 jedzenia na regenerację energii już żyjących -
        # te wracają głodne, nie mają czym się nakarmić, wracają w pole i giną
        # w drodze, co po wielu takich cyklach (wykryte dopiero w wielomiesięcznym
        # teście) prowadzi do nieodwracalnego wymarcia (n=0 => nikt już nie
        # zbiera jedzenia). Rezerwa skaluje się z docelową wielkością kolonii.
        reserve = C.NEST_FOOD_RESERVE_BASE * self.economy_scale
        spendable = self.nest.food - reserve
        if capacity_left <= 0 or spendable < effective_cost:
            return
        affordable = int(spendable // effective_cost)
        # twardy limit na liczbę robotnic kupowanych jednorazowo - zapobiega
        # gwałtownym skokom populacji, które wyprzedzają zdolność zaopatrzenia
        max_per_tick = max(2, int(C.SPAWN_MAX_PER_TICK_BASE * self.economy_scale))
        count = min(affordable, capacity_left, max_per_tick)
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
        for co in self.corpses:
            self._draw_corpse(surface, co)
        self._draw_nest(surface)

        self.pher.render(surface)

        self._draw_ants(surface)
        if self.agents is not None:
            self.agents.draw(surface, self.font, self.font_small)
        for sp in self.spiders:
            self._draw_spider(surface, sp)
        for w in self.wasps:
            self._draw_wasp(surface, w)
        for lb in self.ladybugs:
            self._draw_ladybug(surface, lb)
        for be in self.beetles:
            self._draw_beetle(surface, be)
        for ew in self.earthworms:
            self._draw_earthworm(surface, ew)
        for flock in self.bird_flocks:
            self._draw_bird_flock(surface, flock)

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

        self._draw_precipitation(surface)
        self._draw_hud(surface)

    def _draw_precipitation(self, surface):
        if self.weather == "rain":
            self._draw_rain(surface)
        elif self.weather == "snow":
            self._draw_snow(surface)
        elif self.weather == "drought":
            self._draw_dust(surface)

    def _draw_rain(self, surface):
        if self._rain_particles is None:
            self._rain_particles = np.column_stack(
                [
                    np.random.uniform(0, C.WIDTH, C.RAIN_PARTICLE_COUNT),
                    np.random.uniform(0, C.HEIGHT, C.RAIN_PARTICLE_COUNT),
                ]
            ).astype(np.float32)
        pts = self._rain_particles
        drop_x = (self.wind - 0.25) * 14
        drop_y = 16 + 8 * self.wind
        pts[:, 0] += drop_x
        pts[:, 1] += drop_y
        wrap = pts[:, 1] > C.HEIGHT
        if wrap.any():
            pts[wrap, 1] -= C.HEIGHT
            pts[wrap, 0] = np.random.uniform(0, C.WIDTH, int(wrap.sum()))
        pts[:, 0] %= C.WIDTH

        n = max(1, int(C.RAIN_PARTICLE_COUNT * self.precip_intensity))
        color = (170, 195, 225)
        for x, y in pts[:n]:
            # rzutowanie z numpy.float32 na zwykly float - niektóre backendy
            # pygame (m.in. WASM/pygame-ce w przeglądarce) nie akceptują
            # skalarów numpy jako współrzędnych pygame.draw.line
            x, y = float(x), float(y)
            pygame.draw.line(surface, color, (x, y), (x - drop_x * 0.4, y - 9), 1)

    def _draw_snow(self, surface):
        if self._snow_particles is None:
            self._snow_particles = np.column_stack(
                [
                    np.random.uniform(0, C.WIDTH, C.SNOW_PARTICLE_COUNT),
                    np.random.uniform(0, C.HEIGHT, C.SNOW_PARTICLE_COUNT),
                    np.random.uniform(0, 2 * math.pi, C.SNOW_PARTICLE_COUNT),
                ]
            ).astype(np.float32)
        pts = self._snow_particles
        pts[:, 1] += 3.5
        pts[:, 2] += 0.05
        pts[:, 0] += np.sin(pts[:, 2]) * 0.8 + (self.wind - 0.25) * 3
        wrap = pts[:, 1] > C.HEIGHT
        if wrap.any():
            pts[wrap, 1] -= C.HEIGHT
            pts[wrap, 0] = np.random.uniform(0, C.WIDTH, int(wrap.sum()))
        pts[:, 0] %= C.WIDTH

        n = max(1, int(C.SNOW_PARTICLE_COUNT * self.precip_intensity))
        color = (250, 250, 255)
        for x, y, _ in pts[:n]:
            pygame.draw.circle(surface, color, (int(x), int(y)), 2)

    def _draw_dust(self, surface):
        if self._dust_particles is None:
            self._dust_particles = np.column_stack(
                [
                    np.random.uniform(0, C.WIDTH, C.DUST_PARTICLE_COUNT),
                    np.random.uniform(0, C.HEIGHT, C.DUST_PARTICLE_COUNT),
                ]
            ).astype(np.float32)
        pts = self._dust_particles
        drift_x = 12 + (self.wind - 0.25) * 20
        pts[:, 0] += drift_x
        pts[:, 1] += (self.wind - 0.5) * 4
        wrap = pts[:, 0] > C.WIDTH
        if wrap.any():
            pts[wrap, 0] -= C.WIDTH
            pts[wrap, 1] = np.random.uniform(0, C.HEIGHT, int(wrap.sum()))
        pts[:, 1] %= C.HEIGHT

        n = max(1, int(C.DUST_PARTICLE_COUNT * self.precip_intensity))
        color = (196, 168, 108)
        for x, y in pts[:n]:
            pygame.draw.circle(surface, color, (int(x), int(y)), 1)
        overlay = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
        overlay.fill((210, 170, 90, int(18 * self.precip_intensity)))
        surface.blit(overlay, (0, 0))

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
        color = p.spec["color"]
        if p.growth < 1.0:
            r = max(2, int(p.radius))
            pygame.draw.circle(surface, color, (x, y), r)
            return
        frac = max(0.2, p.stock / p.spec["stock_max"])
        r = int(p.radius)
        outline = tuple(max(0, c - 40) for c in color)
        pygame.draw.circle(surface, outline, (x, y), r, width=2)
        pygame.draw.circle(surface, color, (x, y), max(3, int(r * frac)))
        if p.fertility_bonus > 0.05:
            glow_r = r + 4
            s = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            alpha = int(120 * min(1.0, p.fertility_bonus / C.PLANT_FERTILITY_MAX))
            pygame.draw.circle(s, (150, 110, 60, alpha), (glow_r, glow_r), glow_r, width=2)
            surface.blit(s, (x - glow_r, y - glow_r))

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

    def _draw_wasp(self, surface, w):
        x, y = int(w.pos.x), int(w.pos.y)
        hx = x + int(math.cos(w.angle) * 5)
        hy = y + int(math.sin(w.angle) * 5)
        pygame.draw.line(surface, (40, 30, 10), (x, y), (hx, hy), 2)
        pygame.draw.circle(surface, (235, 195, 40), (x, y), 3)
        pygame.draw.circle(surface, (30, 25, 10), (x, y), 3, width=1)

    def _draw_beetle(self, surface, be):
        x, y = int(be.pos.x), int(be.pos.y)
        rect = pygame.Rect(0, 0, 9, 6)
        rect.center = (x, y)
        pygame.draw.ellipse(surface, (45, 35, 25), rect)
        pygame.draw.ellipse(surface, (20, 15, 10), rect, width=1)

    def _draw_earthworm(self, surface, ew):
        x, y = int(ew.pos.x), int(ew.pos.y)
        tail = ew.pos - Vector2(math.cos(ew.angle), math.sin(ew.angle)) * 6
        pygame.draw.line(surface, (210, 140, 150), (x, y), (int(tail.x), int(tail.y)), 2)

    def _draw_corpse(self, surface, co):
        x, y = int(co.pos.x), int(co.pos.y)
        frac = max(0.2, co.biomass / max(0.1, C.CORPSE_BIOMASS.get(co.kind, 1.0)))
        r = max(2, int(3 + frac * 3))
        pygame.draw.circle(surface, (90, 75, 60), (x, y), r)

    def _draw_bird_flock(self, surface, flock):
        x, y = int(flock.pos.x), int(flock.pos.y)
        for i in range(flock.count):
            off = (i - flock.count / 2) * 7
            wx = x + int(math.cos(flock.angle + math.pi / 2) * off)
            wy = y + int(math.sin(flock.angle + math.pi / 2) * off)
            span = 5
            hx = wx + int(math.cos(flock.angle) * span)
            hy = wy + int(math.sin(flock.angle) * span)
            lx = wx - int(math.cos(flock.angle - 0.9) * span)
            ly = wy - int(math.sin(flock.angle - 0.9) * span)
            rx = wx - int(math.cos(flock.angle + 0.9) * span)
            ry = wy - int(math.sin(flock.angle + 0.9) * span)
            pygame.draw.line(surface, (30, 30, 35), (lx, ly), (hx, hy), 1)
            pygame.draw.line(surface, (30, 30, 35), (rx, ry), (hx, hy), 1)

    def _weather_line(self):
        weather_label = {
            "clear": "bezchmurnie", "rain": "deszcz", "snow": "śnieg", "drought": "susza",
        }[self.weather]
        extra = f" ({self.precip_intensity*100:.0f}%)" if self.weather != "clear" else ""
        return (
            f"Pogoda: {self.temperature:+.1f}°C   {weather_label}{extra}   Wiatr: {self.wind:.2f}"
        )

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
            f"Mszyce: {sum(c.count for c in self.aphids)}   Pająki: {len(self.spiders)}   Osy: {len(self.wasps)}"
            f"   Biedronki: {len(self.ladybugs)}",
            f"Chrząszcze: {len(self.beetles)}   Dżdżownice: {len(self.earthworms)}"
            f"   Truchła: {len(self.corpses)}   Stada ptaków: {len(self.bird_flocks)}",
            f"Dzień symulacji: {self.time / C.DAY_LENGTH_SECONDS:.2f} ({day_label})   Prędkość: x{self.speed_mult}"
            + ("   [PAUZA]" if self.paused else ""),
            self._weather_line(),
            self._evolution_line(n),
            *([self.agents.linia_hud()] if self.agents is not None else []),
            "SPACJA=pauza  +/-=predkosc(x1..x20)  ESC=menu  R=reset  LPM=zasadz roslinę  PPM=przeszkoda  TAB=panel agentów",
        ]
        box_h = 18 * len(lines) + 14
        panel = pygame.Surface((640, box_h), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 140))
        surface.blit(panel, (8, 8))
        for i, line in enumerate(lines):
            txt = self.font.render(line, True, (255, 255, 255))
            surface.blit(txt, (16, 12 + i * 18))
