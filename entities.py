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
    jest skończona, tak jak w naturze)."""

    def __init__(self, pos, mature=False):
        self.pos = Vector2(pos)
        self.growth = 1.0 if mature else 0.0
        self.stock = C.PLANT_STOCK_MAX * 0.5 if mature else 0.0
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

    def update(self, dt, world):
        daylight_factor = max(0.15, world.daylight)
        if self.growth < 1.0:
            self.growth = min(1.0, self.growth + dt * daylight_factor / C.PLANT_GROWTH_TIME)
            return None

        rate = C.PLANT_STOCK_RATE * world.mods["food_regen"] * daylight_factor
        self.stock = min(C.PLANT_STOCK_MAX, self.stock + rate * dt)

        offspring = None
        if (
            self.stock >= C.PLANT_REPRO_MIN_STOCK
            and len(world.plants) < C.MAX_PLANTS
            and random.random() < C.PLANT_REPRO_CHANCE * dt
        ):
            ang = random.uniform(0, 2 * math.pi)
            dist = random.uniform(*C.PLANT_SEED_SPREAD)
            newpos = self.pos + Vector2(math.cos(ang), math.sin(ang)) * dist
            _clamp_to_bounds(newpos, 30)
            offspring = Plant(newpos, mature=False)
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
        host_ready = self.host_plant is None or self.host_plant.growth >= 1.0
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
            return None

        self.energy -= C.SPIDER_ENERGY_DRAIN * dt
        if self.energy <= 0:
            self.alive = False  # padł z głodu
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
