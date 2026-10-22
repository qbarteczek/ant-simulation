"""Klasy bytów świata: mrówki, gniazdo, jedzenie, mszyce, pająki, biedronki, przeszkody."""
import math
import random

import numpy as np
from pygame.math import Vector2

import config as C


def _lerp_angle(a, b, t):
    diff = (b - a + math.pi) % (2 * math.pi) - math.pi
    return a + diff * t


def _clamp_to_bounds(pos, margin=8):
    pos.x = min(max(pos.x, margin), C.WIDTH - margin)
    pos.y = min(max(pos.y, margin), C.HEIGHT - margin)
    return pos


class Obstacle:
    def __init__(self, pos, radius):
        self.pos = Vector2(pos)
        self.radius = radius


class Nest:
    def __init__(self, pos):
        self.pos = Vector2(pos)
        self.radius = C.NEST_RADIUS
        self.food = 40.0


class Plant:
    """Roślina: kiełkuje, rośnie w świetle dnia, dojrzała daje ograniczony,
    powoli odnawiający się zapas jedzenia i może się rozsiewać - ale zapas
    na roślinę i liczba roślin są twardo ograniczone (produkcja żywności
    jest skończona, tak jak w naturze). Cechy (tempo wzrostu, zapas, długość
    życia, odporność na mróz/suszę) zależą od gatunku - patrz C.PLANT_SPECIES."""

    def __init__(self, pos, species_name, mature=False):
        self.pos = Vector2(pos)
        self.species_name = species_name
        self.spec = C.PLANT_SPECIES[species_name]
        self.growth = 1.0 if mature else 0.0
        self.stock = self.spec["stock_max"] * 0.5 if mature else 0.0
        self.age = 0.0
        self.lifespan = random.uniform(*self.spec["lifespan_range"])
        self.fertility_bonus = 0.0
        self.alive = True

    @property
    def radius(self):
        return C.PLANT_SEED_RADIUS + (C.PLANT_MATURE_RADIUS - C.PLANT_SEED_RADIUS) * self.growth

    @property
    def amount(self):
        return self.stock if self.growth >= 1.0 else 0.0

    def take(self, load):
        got = min(load, self.stock)
        self.stock -= got
        return got

    def fertilize(self, amount):
        self.fertility_bonus = min(C.PLANT_FERTILITY_MAX, self.fertility_bonus + amount)

    def update(self, dt, world):
        self.age += dt
        if self.age >= self.lifespan:
            self.alive = False  # usycha ze starości
            return None

        temperature = getattr(world, "temperature", 15.0)
        if temperature <= self.spec["frost_temp"]:
            if random.random() < self.spec["frost_death_chance"] * dt:
                self.alive = False  # przemarzła
                return None

        if getattr(world, "weather", "clear") == "drought":
            drought_chance = (
                C.PLANT_DROUGHT_DEATH_CHANCE_BASE * self.spec["drought_tolerance"] * world.precip_intensity
            )
            if random.random() < drought_chance * dt:
                self.alive = False  # uschła z suszy
                return None

        self.fertility_bonus = max(0.0, self.fertility_bonus - C.PLANT_FERTILITY_DECAY * dt)

        daylight_factor = max(0.15, world.daylight)
        if self.growth < 1.0:
            self.growth = min(1.0, self.growth + dt * daylight_factor / self.spec["growth_time"])
            return None

        rate = self.spec["stock_rate"] * world.mods["food_regen"] * daylight_factor * (1.0 + self.fertility_bonus)
        self.stock = min(self.spec["stock_max"], self.stock + rate * dt)

        offspring = None
        if (
            self.stock >= self.spec["repro_min_stock"]
            and len(world.plants) < C.MAX_PLANTS
            and random.random() < self.spec["repro_chance"] * dt
        ):
            ang = random.uniform(0, 2 * math.pi)
            dist = random.uniform(*C.PLANT_SEED_SPREAD)
            newpos = self.pos + Vector2(math.cos(ang), math.sin(ang)) * dist
            _clamp_to_bounds(newpos, 30)
            offspring = Plant(newpos, self.species_name, mature=False)
        return offspring


class AphidCluster:
    def __init__(self, pos, count, host_plant=None):
        self.pos = Vector2(pos)
        self.radius = 20
        self.count = count
        self.max_count = max(count, C.APHID_MAX_PER_CLUSTER_BASE)
        self.honeydew = 0.0
        self.repro_timer = random.uniform(4, 8)
        self.host_plant = host_plant

    def update(self, dt, world):
        if self.count <= 0:
            return
        host_ready = self.host_plant is None or (self.host_plant.alive and self.host_plant.growth >= 1.0)
        rate = C.APHID_HONEYDEW_RATE * self.count * world.mods["food_regen"]
        rate *= 1.0 if host_ready else 0.1  # mszyce żywią się rośliną - bez niej ledwo produkują
        self.honeydew = min(C.APHID_HONEYDEW_MAX, self.honeydew + rate * dt)
        self.repro_timer -= dt * world.mods["activity"]
        if self.repro_timer <= 0:
            self.repro_timer = random.uniform(6, 12)
            if self.count < self.max_count and random.random() < 0.5:
                self.count += 1

    def take(self, load):
        got = min(load, self.honeydew)
        self.honeydew -= got
        return got

    @property
    def amount(self):
        return self.honeydew

    @property
    def depleted(self):
        return False  # klaster mszyc nigdy nie znika całkowicie z mapy


class Spider:
    def __init__(self, pos, energy=None):
        self.pos = Vector2(pos)
        self.hp = C.SPIDER_HP
        self.angle = random.uniform(0, 2 * math.pi)
        self.state = "WANDER"
        self.attack_cooldown = 0.0
        self.energy = C.SPIDER_ENERGY_MAX * 0.6 if energy is None else energy
        self.alive = True

    def update(self, dt, world):
        if self.hp <= 0:
            self.alive = False
            world.spawn_corpse(self.pos, "spider")
            return None

        self.energy -= C.SPIDER_ENERGY_DRAIN * dt
        if self.energy <= 0:
            self.alive = False  # padł z głodu
            world.spawn_corpse(self.pos, "spider")
            return None

        predator_mult = world.mods["predator"]
        idx, xs, ys = world.ants_near(self.pos, C.SPIDER_HUNT_RADIUS)
        idx2, xs2, ys2 = world.ants_near(self.pos, C.SPIDER_ATTACK_RADIUS * 2.5)

        if idx2.size >= C.SPIDER_FLEE_ANTS:
            self.state = "FLEE"
        elif idx.size > 0:
            self.state = "HUNT"
        else:
            self.state = "WANDER"

        speed = C.SPIDER_SPEED
        if self.state == "WANDER":
            # czyha przy wydeptanych szlakach mrówek zamiast czysto losowo
            # błądzić - realistyczne zachowanie zasadzki, ułatwia upolowanie
            # czegokolwiek zanim padnie z głodu
            ahead = self.pos + Vector2(math.cos(self.angle), math.sin(self.angle)) * 30
            trail = world.pher.sample("home", ahead.x, ahead.y) + world.pher.sample("food", ahead.x, ahead.y)
            if trail < 20 or random.random() < 0.5:
                self.angle += random.uniform(-0.3, 0.3)
            speed *= 0.5
        elif self.state == "HUNT":
            dxs = xs - self.pos.x
            dys = ys - self.pos.y
            j = int(np.argmin(dxs * dxs + dys * dys))
            tx, ty = float(xs[j]), float(ys[j])
            desired = Vector2(tx, ty) - self.pos
            if desired.length_squared() > 0:
                self.angle = math.atan2(desired.y, desired.x)
            speed *= predator_mult
            if desired.length() <= C.SPIDER_ATTACK_RADIUS:
                self.attack_cooldown -= dt
                if self.attack_cooldown <= 0:
                    self.attack_cooldown = C.SPIDER_ATTACK_COOLDOWN
                    # rzadka zdobycz = trudniej upolować - chroni kolonię
                    # przed nieodwracalnym wybiciem, tak jak w naturze
                    prey_factor = min(1.0, world.ant_swarm.n / C.SPIDER_PREY_SATURATION)
                    if random.random() < C.SPIDER_KILL_CHANCE * predator_mult * prey_factor:
                        world.kill_ants(np.array([idx[j]]))
                        world.spawn_corpse(Vector2(tx, ty), "ant")
                        self.energy = min(C.SPIDER_ENERGY_MAX, self.energy + C.SPIDER_ENERGY_PER_KILL)
        else:  # FLEE
            cx = float(xs2.mean())
            cy = float(ys2.mean())
            away = self.pos - Vector2(cx, cy)
            if away.length_squared() > 0:
                self.angle = math.atan2(away.y, away.x)
            speed *= 1.3

        direction = Vector2(math.cos(self.angle), math.sin(self.angle))
        next_pos = self.pos + direction * speed * dt
        self.pos = _clamp_to_bounds(next_pos, 10)

        offspring = None
        if (
            self.energy >= C.SPIDER_REPRO_THRESHOLD
            and len(world.spiders) < C.MAX_SPIDERS
            and random.random() < C.SPIDER_REPRO_CHANCE * dt
        ):
            self.energy -= C.SPIDER_REPRO_COST
            jitter = Vector2(random.uniform(-16, 16), random.uniform(-16, 16))
            offspring = Spider(self.pos + jitter, energy=C.SPIDER_REPRO_COST * 0.5)
        return offspring


class Ladybug:
    def __init__(self, pos, energy=None):
        self.pos = Vector2(pos)
        self.angle = random.uniform(0, 2 * math.pi)
        self.eat_cooldown = 0.0
        self.energy = C.LADYBUG_ENERGY_MAX * 0.6 if energy is None else energy
        self.alive = True

    def update(self, dt, world):
        self.energy -= C.LADYBUG_ENERGY_DRAIN * dt
        if self.energy <= 0:
            self.alive = False  # padła z głodu
            world.spawn_corpse(self.pos, "ladybug")
            return None

        cluster = world.nearest_aphid_cluster_within(self.pos, C.LADYBUG_HUNT_RADIUS)
        speed = C.LADYBUG_SPEED
        if cluster is not None and cluster.count > 0:
            desired = cluster.pos - self.pos
            if desired.length_squared() > 0:
                self.angle = math.atan2(desired.y, desired.x)
            if self.pos.distance_to(cluster.pos) <= cluster.radius:
                self.eat_cooldown -= dt
                if self.eat_cooldown <= 0:
                    self.eat_cooldown = C.LADYBUG_EAT_COOLDOWN
                    # zawsze zostaw co najmniej jedną mszycę - refugium chroniące
                    # przed lokalnym wytępieniem całego klastra
                    if cluster.count > 1 and random.random() < 0.6:
                        cluster.count -= 1
                        self.energy = min(C.LADYBUG_ENERGY_MAX, self.energy + C.LADYBUG_ENERGY_PER_MEAL)
                    elif cluster.count > 0:
                        self.energy = min(C.LADYBUG_ENERGY_MAX, self.energy + C.LADYBUG_ENERGY_PER_MEAL * 0.3)
        else:
            self.angle += random.uniform(-0.3, 0.3)
            speed *= 0.6

        direction = Vector2(math.cos(self.angle), math.sin(self.angle))
        next_pos = self.pos + direction * speed * dt
        self.pos = _clamp_to_bounds(next_pos, 10)
        offspring = None
        if (
            self.energy >= C.LADYBUG_REPRO_THRESHOLD
            and len(world.ladybugs) < C.MAX_LADYBUGS
            and random.random() < C.LADYBUG_REPRO_CHANCE * dt
        ):
            self.energy -= C.LADYBUG_REPRO_COST
            jitter = Vector2(random.uniform(-14, 14), random.uniform(-14, 14))
            offspring = Ladybug(self.pos + jitter, energy=C.LADYBUG_REPRO_COST * 0.5)
        return offspring


class Wasp:
    """Drapieżnik generalistyczny: preferuje tanie posiłki z klastrów mszyc,
    a gdy głodna i nie ma mszyc w zasięgu - poluje na pojedyncze mrówki jak
    pająk, tylko mniej skutecznie (mniejszy, mniej wyspecjalizowany łowca)."""

    def __init__(self, pos, energy=None):
        self.pos = Vector2(pos)
        self.hp = C.WASP_HP
        self.angle = random.uniform(0, 2 * math.pi)
        self.state = "WANDER"
        self.eat_cooldown = 0.0
        self.attack_cooldown = 0.0
        self.energy = C.WASP_ENERGY_MAX * 0.6 if energy is None else energy
        self.alive = True

    def update(self, dt, world):
        if self.hp <= 0:
            self.alive = False
            world.spawn_corpse(self.pos, "wasp")
            return None
        self.energy -= C.WASP_ENERGY_DRAIN * dt
        if self.energy <= 0:
            self.alive = False  # padła z głodu
            world.spawn_corpse(self.pos, "wasp")
            return None

        predator_mult = world.mods["predator"]
        idx, xs, ys = world.ants_near(self.pos, C.WASP_ANT_HUNT_RADIUS)
        idx2, xs2, ys2 = world.ants_near(self.pos, C.WASP_ATTACK_RADIUS * 2.5)
        cluster = world.nearest_aphid_cluster_within(self.pos, C.WASP_APHID_HUNT_RADIUS)
        hungry = self.energy <= C.WASP_HUNGRY_THRESHOLD

        if idx2.size >= C.WASP_FLEE_ANTS:
            self.state = "FLEE"
        elif cluster is not None and cluster.count > 0:
            self.state = "HUNT_APHID"
        elif hungry and idx.size > 0:
            self.state = "HUNT_ANT"
        else:
            self.state = "WANDER"

        speed = C.WASP_SPEED
        if self.state == "WANDER":
            self.angle += random.uniform(-0.3, 0.3)
            speed *= 0.6
        elif self.state == "HUNT_APHID":
            desired = cluster.pos - self.pos
            if desired.length_squared() > 0:
                self.angle = math.atan2(desired.y, desired.x)
            if self.pos.distance_to(cluster.pos) <= cluster.radius:
                self.eat_cooldown -= dt
                if self.eat_cooldown <= 0:
                    self.eat_cooldown = C.WASP_EAT_COOLDOWN
                    if cluster.count > 1 and random.random() < 0.6:
                        cluster.count -= 1
                        self.energy = min(C.WASP_ENERGY_MAX, self.energy + C.WASP_ENERGY_PER_APHID)
                    elif cluster.count > 0:
                        self.energy = min(C.WASP_ENERGY_MAX, self.energy + C.WASP_ENERGY_PER_APHID * 0.3)
        elif self.state == "HUNT_ANT":
            dxs = xs - self.pos.x
            dys = ys - self.pos.y
            j = int(np.argmin(dxs * dxs + dys * dys))
            tx, ty = float(xs[j]), float(ys[j])
            desired = Vector2(tx, ty) - self.pos
            if desired.length_squared() > 0:
                self.angle = math.atan2(desired.y, desired.x)
            speed *= predator_mult
            if desired.length() <= C.WASP_ATTACK_RADIUS:
                self.attack_cooldown -= dt
                if self.attack_cooldown <= 0:
                    self.attack_cooldown = C.WASP_ATTACK_COOLDOWN
                    prey_factor = min(1.0, world.ant_swarm.n / C.WASP_PREY_SATURATION)
                    if random.random() < C.WASP_KILL_CHANCE * predator_mult * prey_factor:
                        world.kill_ants(np.array([idx[j]]))
                        world.spawn_corpse(Vector2(tx, ty), "ant")
                        self.energy = min(C.WASP_ENERGY_MAX, self.energy + C.WASP_ENERGY_PER_KILL)
        else:  # FLEE
            cx = float(xs2.mean())
            cy = float(ys2.mean())
            away = self.pos - Vector2(cx, cy)
            if away.length_squared() > 0:
                self.angle = math.atan2(away.y, away.x)
            speed *= 1.4

        direction = Vector2(math.cos(self.angle), math.sin(self.angle))
        next_pos = self.pos + direction * speed * dt
        self.pos = _clamp_to_bounds(next_pos, 10)

        offspring = None
        if (
            self.energy >= C.WASP_REPRO_THRESHOLD
            and len(world.wasps) < C.MAX_WASPS
            and random.random() < C.WASP_REPRO_CHANCE * dt
        ):
            self.energy -= C.WASP_REPRO_COST
            jitter = Vector2(random.uniform(-16, 16), random.uniform(-16, 16))
            offspring = Wasp(self.pos + jitter, energy=C.WASP_REPRO_COST * 0.5)
        return offspring


class Corpse:
    """Truchło - zostaje po śmierci zwierzęcia, żerują na nim chrząszcze,
    znika samo po CORPSE_DECAY_TIME jeśli nikt go nie zje."""

    def __init__(self, pos, kind):
        self.pos = Vector2(pos)
        self.kind = kind
        self.biomass = C.CORPSE_BIOMASS.get(kind, 1.0)
        self.age = 0.0

    def take(self, amount):
        got = min(amount, self.biomass)
        self.biomass -= got
        return got

    def update(self, dt):
        self.age += dt
        return self.biomass > 0.05 and self.age < C.CORPSE_DECAY_TIME


class Beetle:
    """Chrząszcz padlinożerny: szuka truchła w zasięgu, żywi się nim, a podczas
    żerowania lekko użyźnia pobliskie rośliny - domyka obieg materii."""

    def __init__(self, pos, energy=None):
        self.pos = Vector2(pos)
        self.angle = random.uniform(0, 2 * math.pi)
        self.energy = C.BEETLE_ENERGY_MAX * 0.6 if energy is None else energy
        self.alive = True

    def update(self, dt, world):
        self.energy -= C.BEETLE_ENERGY_DRAIN * dt
        if self.energy <= 0:
            self.alive = False  # padł z głodu
            return None

        corpse = world.nearest_corpse_within(self.pos, C.BEETLE_SENSE_RADIUS)
        speed = C.BEETLE_SPEED
        if corpse is not None and corpse.biomass > 0.05:
            desired = corpse.pos - self.pos
            if desired.length_squared() > 0:
                self.angle = math.atan2(desired.y, desired.x)
            if self.pos.distance_to(corpse.pos) <= 10:
                got = corpse.take(C.BEETLE_FEED_RATE * dt)
                self.energy = min(C.BEETLE_ENERGY_MAX, self.energy + got * C.BEETLE_ENERGY_PER_BIOMASS)
                world.fertilize_near(self.pos, C.BEETLE_FERTILIZE_RADIUS, C.BEETLE_FERTILIZE_AMOUNT * dt)
                speed *= 0.2
        else:
            self.angle += random.uniform(-0.3, 0.3)
            speed *= 0.6

        direction = Vector2(math.cos(self.angle), math.sin(self.angle))
        next_pos = self.pos + direction * speed * dt
        self.pos = _clamp_to_bounds(next_pos, 10)

        offspring = None
        if (
            self.energy >= C.BEETLE_REPRO_THRESHOLD
            and len(world.beetles) < C.MAX_BEETLES
            and random.random() < C.BEETLE_REPRO_CHANCE * dt
        ):
            self.energy -= C.BEETLE_REPRO_COST
            jitter = Vector2(random.uniform(-14, 14), random.uniform(-14, 14))
            offspring = Beetle(self.pos + jitter, energy=C.BEETLE_REPRO_COST * 0.5)
        return offspring


class Earthworm:
    """Dżdżownica: czysty mutualista bez drapieżników - przebywając blisko
    rośliny, stopniowo podnosi jej żyzność (fertility_bonus). Ginie rzadko
    przy silnym mrozie lub przedłużonej suszy (potrzebuje wilgotnej gleby)."""

    def __init__(self, pos):
        self.pos = Vector2(pos)
        self.angle = random.uniform(0, 2 * math.pi)
        self.alive = True

    def update(self, dt, world):
        temperature = getattr(world, "temperature", 15.0)
        if temperature <= C.EARTHWORM_FROST_TEMP:
            if random.random() < C.EARTHWORM_FROST_DEATH_CHANCE * dt:
                self.alive = False
                return None
        if getattr(world, "weather", "clear") == "drought":
            if random.random() < C.EARTHWORM_DROUGHT_DEATH_CHANCE * world.precip_intensity * dt:
                self.alive = False
                return None

        plant = world.nearest_plant_within(self.pos, C.EARTHWORM_SENSE_RADIUS)
        speed = C.EARTHWORM_SPEED
        near_plant = False
        if plant is not None:
            desired = plant.pos - self.pos
            if desired.length_squared() > 0:
                self.angle = math.atan2(desired.y, desired.x)
            if self.pos.distance_to(plant.pos) <= C.EARTHWORM_FERTILIZE_RADIUS:
                plant.fertilize(C.EARTHWORM_FERTILIZE_RATE * dt)
                near_plant = True
                speed *= 0.3
        else:
            self.angle += random.uniform(-0.3, 0.3)

        direction = Vector2(math.cos(self.angle), math.sin(self.angle))
        next_pos = self.pos + direction * speed * dt
        self.pos = _clamp_to_bounds(next_pos, 6)

        offspring = None
        if (
            near_plant
            and plant.growth >= 1.0
            and len(world.earthworms) < C.MAX_EARTHWORMS
            and random.random() < C.EARTHWORM_REPRO_CHANCE * dt
        ):
            jitter = Vector2(random.uniform(-10, 10), random.uniform(-10, 10))
            offspring = Earthworm(self.pos + jitter)
        return offspring


class BirdFlock:
    """Stado ptaków - drapieżnik szczytowy pojawiający się epizodycznie (jak
    pogoda), gdy populacja średnich drapieżników (pająki+osy+biedronki)
    urośnie za bardzo. Przerzedza ją, po czym odlatuje - domyka pętlę
    kontroli populacji "od góry"."""

    def __init__(self, pos):
        self.pos = Vector2(pos)
        self.angle = random.uniform(0, 2 * math.pi)
        self.count = random.randint(*C.BIRD_FLOCK_SIZE)
        self.timer = C.BIRD_VISIT_DURATION
        self.alive = True

    def update(self, dt, world):
        self.timer -= dt
        if self.timer <= 0:
            self.alive = False
            return

        targets = [t for t in (world.spiders + world.wasps + world.ladybugs) if t.alive]
        if targets:
            target = min(targets, key=lambda t: self.pos.distance_to(t.pos))
            desired = target.pos - self.pos
            if desired.length_squared() > 0:
                self.angle = math.atan2(desired.y, desired.x)
        else:
            self.angle += random.uniform(-0.2, 0.2)

        next_pos = self.pos + Vector2(math.cos(self.angle), math.sin(self.angle)) * C.BIRD_SPEED * dt
        self.pos = _clamp_to_bounds(next_pos, 10)

        for t in targets:
            if self.pos.distance_to(t.pos) <= C.BIRD_CATCH_RADIUS:
                if random.random() < C.BIRD_CULL_CHANCE * self.count * dt:
                    t.alive = False
                    if isinstance(t, Spider):
                        kind = "spider"
                    elif isinstance(t, Wasp):
                        kind = "wasp"
                    else:
                        kind = "ladybug"
                    world.spawn_corpse(t.pos, kind)
