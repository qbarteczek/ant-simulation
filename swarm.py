"""Wektorowa (numpy) reprezentacja całej kolonii mrówek.

Zamiast tysięcy osobnych obiektów Pythona aktualizowanych w pętli,
stan wszystkich mrówek trzymany jest w tablicach numpy i aktualizowany
za jednym razem (SIMD na CPU) - to jedyny sposób, żeby symulacja
kilku tysięcy agentów działała płynnie na słabym/starym GPU, gdzie
prawdziwe obliczenia na karcie graficznej (CUDA/OpenCL) nic by nie dały.
"""
import math
import random

import numpy as np
from pygame.math import Vector2

import config as C

STATE_SEARCH = 0
STATE_RETURN = 1


def _lerp_angle(a, b, t):
    diff = (b - a + np.pi) % (2 * np.pi) - np.pi
    return a + diff * t


class AntSwarm:
    def __init__(self, capacity, species_name, biome_name):
        sp = C.SPECIES[species_name]
        base_speed = sp["speed"]
        base_drain = sp["drain"]
        if sp["native"] == biome_name:
            base_speed *= C.NATIVE_BONUS_SPEED
            base_drain *= C.NATIVE_BONUS_DRAIN

        self.species_name = species_name
        # wartości bazowe gatunku - punkt startowy dla pokolenia zerowego,
        # dalsze pokolenia dziedziczą i mutują od żywej populacji
        self.base_speed_mult = base_speed
        self.base_drain_mult = base_drain
        self.base_strength = sp["strength"]
        self.base_sense_mult = sp["sense"]
        self.color = sp["color"]
        self.max_energy = C.ANT_ENERGY_MAX * sp["energy_cap"]

        self.capacity = capacity
        self.n = 0
        self.x = np.zeros(capacity, dtype=np.float32)
        self.y = np.zeros(capacity, dtype=np.float32)
        self.angle = np.zeros(capacity, dtype=np.float32)
        self.energy = np.zeros(capacity, dtype=np.float32)
        self.state = np.zeros(capacity, dtype=np.int8)
        self.carrying = np.zeros(capacity, dtype=bool)
        self.in_combat = np.zeros(capacity, dtype=bool)

        # dziedziczone, podlegające mutacji cechy - każda mrówka ma własne
        self.speed_mult = np.full(capacity, base_speed, dtype=np.float32)
        self.drain_mult = np.full(capacity, base_drain, dtype=np.float32)
        self.strength = np.full(capacity, sp["strength"], dtype=np.float32)
        self.sense_mult = np.full(capacity, sp["sense"], dtype=np.float32)

    # --- populacja -----------------------------------------------------------
    def spawn(self, count, nest_pos):
        count = int(min(count, self.capacity - self.n))
        if count <= 0:
            return
        sl = slice(self.n, self.n + count)
        self.x[sl] = nest_pos.x + np.random.uniform(-12, 12, count)
        self.y[sl] = nest_pos.y + np.random.uniform(-12, 12, count)
        self.angle[sl] = np.random.uniform(0, 2 * np.pi, count)
        self.energy[sl] = self.max_energy
        self.state[sl] = STATE_SEARCH
        self.carrying[sl] = False
        self.in_combat[sl] = False

        if self.n > 0:
            parents = np.random.randint(0, self.n, size=count)
            self.speed_mult[sl] = self._mutate(self.speed_mult[parents], "speed_mult")
            self.drain_mult[sl] = self._mutate(self.drain_mult[parents], "drain_mult")
            self.strength[sl] = self._mutate(self.strength[parents], "strength")
            self.sense_mult[sl] = self._mutate(self.sense_mult[parents], "sense_mult")
        else:
            self.speed_mult[sl] = self.base_speed_mult
            self.drain_mult[sl] = self.base_drain_mult
            self.strength[sl] = self.base_strength
            self.sense_mult[sl] = self.base_sense_mult

        self.n += count

    def _mutate(self, values, trait_name):
        lo, hi = C.EVO_BOUNDS[trait_name]
        mutated = values * (1.0 + np.random.normal(0.0, C.EVO_MUTATION_SIGMA, size=values.size))
        return np.clip(mutated, lo, hi)

    def kill(self, idx):
        if idx.size:
            self.energy[idx] = -1.0

    def _compact(self):
        n = self.n
        alive = self.energy[:n] > 0
        if alive.all():
            return
        keep = np.nonzero(alive)[0]
        k = keep.size
        for arr in (
            self.x, self.y, self.angle, self.energy, self.state, self.carrying, self.in_combat,
            self.speed_mult, self.drain_mult, self.strength, self.sense_mult,
        ):
            arr[:k] = arr[:n][keep]
        self.n = k

    # --- główna aktualizacja ---------------------------------------------------
    def update(self, dt, world):
        n = self.n
        if n == 0:
            return
        mods = world.mods
        activity = mods["activity"]

        x = self.x[:n]
        y = self.y[:n]
        angle = self.angle[:n]
        state = self.state[:n]
        carrying = self.carrying[:n]
        energy = self.energy[:n]
        in_combat = self.in_combat[:n]
        in_combat[:] = False
        speed_mult = self.speed_mult[:n]
        drain_mult = self.drain_mult[:n]
        sense_mult = self.sense_mult[:n]

        speed = C.ANT_BASE_SPEED * speed_mult * activity
        energy -= C.ANT_ENERGY_DRAIN * drain_mult * activity * dt

        searching = state == STATE_SEARCH
        returning = ~searching

        # --- depozyt feromonów -------------------------------------------------
        if searching.any():
            world.pher.deposit_bulk("home", x[searching], y[searching], 170.0)
        if returning.any():
            world.pher.deposit_bulk("food", x[returning], y[returning], 170.0)

        # --- bazowe sterowanie feromonami (3 sensory) ---------------------------
        self._steer_by_pheromone(world, dt, x, y, angle, sense_mult, searching, "food")
        self._steer_by_pheromone(world, dt, x, y, angle, sense_mult, returning, "home")
        if returning.any():
            dx = world.nest.pos.x - x[returning]
            dy = world.nest.pos.y - y[returning]
            home_angle = np.arctan2(dy, dx)
            angle[returning] = _lerp_angle(angle[returning], home_angle, 0.025)

        angle += np.random.uniform(-C.ANT_TURN_NOISE, C.ANT_TURN_NOISE, n) * dt * 5.0

        # --- nadpisanie: widoczne jedzenie (tylko szukające) ---------------------
        nearest_food_idx, nearest_food_dist = self._nearest_forageable(world, x, y)
        has_target = searching & (nearest_food_idx >= 0) & (nearest_food_dist <= C.ANT_SIGHT_RADIUS)
        if has_target.any():
            targets = world.all_forageables()
            tx = np.array([targets[i].pos.x for i in nearest_food_idx[has_target]])
            ty = np.array([targets[i].pos.y for i in nearest_food_idx[has_target]])
            da = np.arctan2(ty - y[has_target], tx - x[has_target])
            angle[has_target] = _lerp_angle(angle[has_target], da, 0.25)

        # --- nadpisanie: bliskość gniazda (tylko wracające) -----------------------
        d_nest = np.hypot(x - world.nest.pos.x, y - world.nest.pos.y)
        near_nest = returning & (d_nest <= C.ANT_SIGHT_RADIUS + world.nest.radius)
        if near_nest.any():
            da = np.arctan2(world.nest.pos.y - y[near_nest], world.nest.pos.x - x[near_nest])
            angle[near_nest] = _lerp_angle(angle[near_nest], da, 0.25)

        # --- nadpisanie: zagrożenie ze strony pająków (najwyższy priorytet) -------
        for sp in world.spiders:
            if not sp.alive:
                continue
            dx = x - sp.pos.x
            dy = y - sp.pos.y
            dist = np.hypot(dx, dy)
            threatened = dist <= C.ANT_THREAT_RADIUS
            if not threatened.any():
                continue
            in_combat[threatened] = True
            da = np.arctan2(-dy[threatened], -dx[threatened])
            angle[threatened] = _lerp_angle(angle[threatened], da, 0.35)

        # --- ruch + unikanie przeszkód i granic -----------------------------------
        next_x = x + np.cos(angle) * speed * dt
        next_y = y + np.sin(angle) * speed * dt

        handled = np.zeros(n, dtype=bool)
        for obs in world.obstacles:
            dxo = next_x - obs.pos.x
            dyo = next_y - obs.pos.y
            dist = np.hypot(dxo, dyo)
            collide = (~handled) & (dist < obs.radius + 5)
            if not collide.any():
                continue
            safe_dist = np.where(dist[collide] > 0, dist[collide], 1.0)
            ax = dxo[collide] / safe_dist
            ay = dyo[collide] / safe_dist
            new_ang = np.arctan2(ay, ax) + np.random.uniform(-0.4, 0.4, collide.sum())
            angle[collide] = new_ang
            next_x[collide] = x[collide] + np.cos(new_ang) * speed[collide] * dt
            next_y[collide] = y[collide] + np.sin(new_ang) * speed[collide] * dt
            handled |= collide

        margin = 8
        out = (next_x < margin) | (next_x > C.WIDTH - margin) | (next_y < margin) | (next_y > C.HEIGHT - margin)
        if out.any():
            inward_x = C.WIDTH / 2 - x[out]
            inward_y = C.HEIGHT / 2 - y[out]
            inward_angle = np.arctan2(inward_y, inward_x)
            angle[out] = _lerp_angle(angle[out], inward_angle, 0.5)
            next_x[out] = np.clip(next_x[out], margin, C.WIDTH - margin)
            next_y[out] = np.clip(next_y[out], margin, C.HEIGHT - margin)

        x[:] = next_x
        y[:] = next_y

        # --- podbieranie jedzenia (dla źródeł, na które ktoś "wszedł") -------------
        self._resolve_pickup(world, x, y, state, carrying)

        # --- powrót do gniazda: złożenie jedzenia ---------------------------------
        d_nest = np.hypot(x - world.nest.pos.x, y - world.nest.pos.y)
        arrived = returning & (d_nest <= world.nest.radius)
        if arrived.any():
            count = int(arrived.sum())
            world.nest.food += count * C.ANT_LOAD
            carrying[arrived] = False
            state[arrived] = STATE_SEARCH

        # --- karmienie przy gnieździe (regeneracja energii) ------------------------
        at_nest = d_nest <= world.nest.radius
        feeding = at_nest & (energy < self.max_energy) & (world.nest.food > 0)
        if feeding.any():
            gain = np.minimum(C.ANT_ENERGY_REGEN * dt, self.max_energy - energy[feeding])
            energy[feeding] += gain
            world.nest.food = max(0.0, world.nest.food - float(gain.sum()) * C.ANT_FEED_COST)

        self._compact()

    def _steer_by_pheromone(self, world, dt, x, y, angle, sense_mult, mask, channel):
        if not mask.any():
            return
        mx, my, ma, msense = x[mask], y[mask], angle[mask], sense_mult[mask]
        vals = np.empty((mx.size, 3), dtype=np.float32)
        angs = np.empty((mx.size, 3), dtype=np.float32)
        offsets = (-C.ANT_SENSOR_ANGLE, 0.0, C.ANT_SENSOR_ANGLE)
        for i, off in enumerate(offsets):
            a = ma + off
            sx = mx + np.cos(a) * C.ANT_SENSOR_DIST
            sy = my + np.sin(a) * C.ANT_SENSOR_DIST
            vals[:, i] = world.pher.sample_bulk(channel, sx, sy) * msense
            angs[:, i] = a

        total = vals.sum(axis=1)
        has_signal = total > 4
        if not has_signal.any():
            return
        sub_vals = vals[has_signal]
        sub_angs = angs[has_signal]
        sub_total = total[has_signal]
        r = np.random.uniform(0, sub_total)
        cumulative = np.cumsum(sub_vals, axis=1)
        idx = np.argmax(r[:, None] <= cumulative, axis=1)
        chosen_angle = sub_angs[np.arange(sub_angs.shape[0]), idx]

        new_sub = _lerp_angle(ma[has_signal], chosen_angle, 0.3)
        full_new = ma.copy()
        full_new[has_signal] = new_sub
        angle[mask] = full_new

    def _nearest_forageable(self, world, x, y):
        targets = world.all_forageables()
        n = x.size
        if not targets:
            return np.full(n, -1, dtype=np.int64), np.full(n, np.inf, dtype=np.float32)
        tx = np.array([t.pos.x for t in targets], dtype=np.float32)
        ty = np.array([t.pos.y for t in targets], dtype=np.float32)
        tr = np.array([t.radius for t in targets], dtype=np.float32)
        dx = x[:, None] - tx[None, :]
        dy = y[:, None] - ty[None, :]
        dist = np.hypot(dx, dy) - tr[None, :]
        idx = np.argmin(dist, axis=1)
        best = dist[np.arange(n), idx]
        return idx, best

    def _resolve_pickup(self, world, x, y, state, carrying):
        targets = world.all_forageables()
        searching = state == STATE_SEARCH
        if not targets.__len__() or not searching.any():
            return
        sx, sy = x[searching], y[searching]
        idxs_in_state = np.nonzero(searching)[0]
        for t in targets:
            if t.amount <= 0.5:
                continue
            dist = np.hypot(sx - t.pos.x, sy - t.pos.y)
            arrived = dist <= t.radius
            if not arrived.any():
                continue
            candidate_local = np.nonzero(arrived)[0]
            max_takers = int(t.amount // C.ANT_LOAD)
            if max_takers <= 0:
                continue
            takers_local = candidate_local[:max_takers]
            takers_global = idxs_in_state[takers_local]
            got = t.take(takers_local.size * C.ANT_LOAD)
            n_takers = int(got // C.ANT_LOAD) if C.ANT_LOAD > 0 else takers_global.size
            takers_global = takers_global[:max(n_takers, 0)] if n_takers < takers_global.size else takers_global
            carrying[takers_global] = True
            state[takers_global] = STATE_RETURN
            # ci sami "szukajacy" nie moga byc ponownie policzeni przy kolejnym zrodle w tej klatce
            still_searching = np.ones(sx.size, dtype=bool)
            still_searching[takers_local[:takers_global.size]] = False
            sx = sx[still_searching]
            sy = sy[still_searching]
            idxs_in_state = idxs_in_state[still_searching]
            if idxs_in_state.size == 0:
                break
