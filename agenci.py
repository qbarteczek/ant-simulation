"""Mrówki-agenci Claude.

Kilka wyróżnionych mrówek (z imieniem, rolą, pamięcią i własnym zdaniem)
nie należy do wektorowego roju z swarm.py. Co kilka sekund każda z nich
dostaje tekstowy opis tego, co widzi, i pyta model Claude, co robić dalej.
Claude odpowiada jednym wywołaniem narzędzia "dzialaj": akcja, cel, krótka
myśl (rysowana w dymku), wiadomość do innej mrówki i notatka do pamięci.

Zapytania idą w osobnych wątkach, więc symulacja na nie nie czeka. Dopóki
mrówka nie dostanie nowej decyzji, kontynuuje poprzednią, a gdy ją skończy,
działa na "autopilocie" (niesie jedzenie do gniazda albo idzie po najbliższe).

Każde zapytanie jest niezależne: pamięć mrówki (notatki, zdarzenia,
wiadomości) trzymamy tutaj i wklejamy do opisu sytuacji, zamiast wysyłać
coraz dłuższą historię rozmowy. Dzięki temu koszt zapytania jest stały.

Klucz API: zmienna ANTHROPIC_API_KEY albo plik klucz_api.txt obok tego
pliku (plik jest w .gitignore - nie trafia do repozytorium).
"""
import json
import math
import os
import random
import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import pygame
from pygame.math import Vector2

import config as C

try:
    import anthropic
except ImportError:  # np. wersja przeglądarkowa (pygbag) - agenci działają wtedy na autopilocie
    anthropic = None

KATALOG = os.path.dirname(os.path.abspath(__file__))
PLIK_KLUCZA = os.path.join(KATALOG, "klucz_api.txt")

AKCJE = {
    "zbieraj": "idź do źródła jedzenia (najbliższego tobie albo punktowi cel_x, cel_y) i weź porcję",
    "wracaj_do_gniazda": "zanieś niesione jedzenie do gniazda i najedz się tam",
    "idz_do": "idź do punktu cel_x, cel_y",
    "eksploruj": "wędruj w stronę cel_x, cel_y (albo losowo, gdy cel pusty), rozglądając się za nowym",
    "atakuj": "zaatakuj najbliższego pająka lub osę (albo tego przy cel_x, cel_y)",
    "uciekaj": "uciekaj od najbliższego zagrożenia w stronę gniazda",
    "odpoczywaj": "idź do gniazda i odpoczywaj, aż odzyskasz siły",
}

NARZEDZIE = {
    "name": "dzialaj",
    "description": (
        "Wybierz, co robisz od teraz. Akcja trwa, dopóki się nie skończy albo dopóki "
        "nie zdecydujesz inaczej. Akcje: "
        + "; ".join(f"{k} - {v}" for k, v in AKCJE.items())
        + "."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "mysl": {
                "type": "string",
                "description": "Twoja krótka myśl na głos, po polsku, najwyżej 8 słów. Widać ją w dymku nad tobą.",
            },
            "akcja": {"type": "string", "enum": list(AKCJE.keys())},
            "cel_x": {"type": ["integer", "null"], "description": "x celu (0-1200) albo null"},
            "cel_y": {"type": ["integer", "null"], "description": "y celu (0-800) albo null"},
            "zostawiaj_feromon": {
                "type": "boolean",
                "description": "true = znakujesz drogę silnym feromonem jedzenia, za którym pójdą zwykłe mrówki z roju",
            },
            "wiadomosc_do": {
                "type": ["string", "null"],
                "description": "imię innej mrówki-agenta, 'wszystkie' albo null, gdy nic nie mówisz",
            },
            "wiadomosc": {"type": ["string", "null"], "description": "treść wiadomości (krótko) albo null"},
            "notatka": {
                "type": ["string", "null"],
                "description": "coś, co chcesz zapamiętać na później (np. gdzie jest jedzenie) albo null",
            },
            "lekcja": {
                "type": ["string", "null"],
                "description": "nowa ogólna lekcja do Księgi mrowiska (bez współrzędnych, jedno zdanie) albo null",
            },
            "potwierdz_lekcje": {
                "type": ["integer", "null"],
                "description": "numer lekcji z Księgi, która właśnie się sprawdziła, albo null",
            },
        },
        "required": [
            "mysl", "akcja", "cel_x", "cel_y", "zostawiaj_feromon", "wiadomosc_do", "wiadomosc", "notatka",
            "lekcja", "potwierdz_lekcje",
        ],
        "additionalProperties": False,
    },
}

SYSTEM_WSPOLNY = """Jesteś mrówką w symulacji mrowiska. Żyjesz na płaskiej mapie 1200 x 800 px \
(x rośnie w prawo, y w dół; północ to góra mapy). Gniazdo jest pośrodku mapy.

Twoja kolonia to setki zwykłych mrówek, które same chodzą po śladach feromonowych, \
oraz kilka mrówek takich jak ty - z imieniem, rolą i własnym rozumem. Razem dbacie, \
żeby kolonia przetrwała: w gnieździe musi być zapas jedzenia, bo z niego rodzą się \
nowe mrówki i z niego wszystkie się karmią. Jedzenie dają rośliny i kolonie mszyc (spadź). \
Pająki i osy polują na mrówki; jedna mrówka rzadko je pokona, ale żołnierki mają \
więcej siły. Energia spada z czasem - gdy dojdzie do zera, umierasz. Najesz się tylko w gnieździe.

Zostawiając feromon jedzenia na drodze od źródła do gniazda, ściągasz tam zwykłe mrówki.
Możesz pisać do innych mrówek-agentów: dzielcie się, gdzie jest nowe jedzenie i zagrożenie, \
proście o pomoc, umawiajcie się. Pisz tylko wtedy, gdy masz coś nowego i ważnego - zwykle \
wiadomość ma być null. Nie powtarzaj tego, co inni już wiedzą.

Kolonia prowadzi Księgę mrowiska - wiedzę, którą przekazuje kolejnym pokoleniom i kolejnym \
koloniom (mapa w każdej grze jest inna, więc współrzędne w Księdze nic nie znaczą). \
Czytaj ją i kieruj się nią. Gdy nauczysz się czegoś ogólnego, co pomoże przetrwać, \
zapisz to w polu "lekcja", np. "Pająki czatują przy roślinach na skraju mapy - zbieraj \
bliżej gniazda" albo "Przed zimą zapas w gnieździe powinien przekraczać 300". \
Nie dopisuj tego, co już jest w Księdze - wtedy podaj jej numer w "potwierdz_lekcje", \
jeśli właśnie się sprawdziła. Zwykle oba pola są null; lekcja ma wynikać z tego, co \
naprawdę się wydarzyło. Gdzie konkretnie jest jedzenie, zapisuj w "notatka".

Za każdym razem dostajesz opis tego, co widzisz. Odpowiedz, wywołując narzędzie \
"dzialaj" dokładnie raz. Myśli i wiadomości pisz po polsku, krótko i z charakterem."""


def czytaj_klucz():
    klucz = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if klucz:
        return klucz
    try:
        with open(PLIK_KLUCZA, encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _kierunek(dx, dy):
    if abs(dx) < 1 and abs(dy) < 1:
        return "tutaj"
    kat = math.degrees(math.atan2(-dy, dx)) % 360  # 0 = wschód, 90 = północ
    nazwy = ["wschód", "północny wschód", "północ", "północny zachód",
             "zachód", "południowy zachód", "południe", "południowy wschód"]
    return nazwy[int((kat + 22.5) // 45) % 8]


def _opis_miejsca(od, do):
    d = od.distance_to(do)
    return f"({int(do.x)}, {int(do.y)}), {int(d)} px na {_kierunek(do.x - od.x, do.y - od.y)}"


def _zawin(tekst, szer):
    slowa, linie, biez = tekst.split(), [], ""
    for s in slowa:
        if len(biez) + len(s) + 1 > szer and biez:
            linie.append(biez)
            biez = s
        else:
            biez = f"{biez} {s}".strip()
    if biez:
        linie.append(biez)
    return linie


class AgentAnt:
    """Pojedyncza mrówka-agent. Ruch i działania liczone tu, decyzje z Claude."""

    def __init__(self, profil, pozycja):
        self.imie = profil["imie"]
        self.rola = profil["rola"]
        self.charakter = profil["charakter"]
        self.kolor = profil["kolor"]
        self.sila = profil.get("sila", 1.0)
        self.szybkosc = profil.get("szybkosc", 1.0) * C.AGENT_SPEED_MULT

        self.pos = Vector2(pozycja) + Vector2(random.uniform(-10, 10), random.uniform(-10, 10))
        self.angle = random.uniform(0, 2 * math.pi)
        self.max_energy = C.ANT_ENERGY_MAX * 1.5
        self.energy = self.max_energy
        self.niesie = 0.0
        self.alive = True

        self.akcja = "zbieraj"
        self.cel = None  # Vector2 albo None
        self.cel_obiekt = None
        self.feromon = False
        self.czas_akcji = 0.0
        self.akcja_skonczona = True
        self.wynik = "Właśnie wyklułaś się w gnieździe."

        self.mysl = ""
        self.mysl_czas = 0.0  # czas rzeczywisty pokazania myśli
        self.notatki = deque(maxlen=C.AGENT_MEMORY_NOTES)
        self.zdarzenia = deque(maxlen=C.AGENT_MEMORY_EVENTS)
        self.skrzynka = []
        self.znane_zagrozenia = set()
        self.zglosila_glod = False
        self.okazja = None  # ważne zdarzenie, z którego warto wyciągnąć lekcję

        self.zapytanie = None  # Future z odpowiedzią Claude
        self.ostatnie_zapytanie = -1e9  # time.monotonic()
        self.potrzebna_decyzja = True

        self.dostarczone = 0.0
        self.trafienia = 0

    # --- pomocnicze ---------------------------------------------------------
    def zdarzenie(self, czas_dnia, tekst):
        self.zdarzenia.append(f"[dzień {czas_dnia:.1f}] {tekst}")

    def _idz_w_strone(self, punkt, dt, world, predkosc_mult=1.0):
        d = punkt - self.pos
        if d.length_squared() > 1e-6:
            docelowy = math.atan2(d.y, d.x)
            roznica = (docelowy - self.angle + math.pi) % (2 * math.pi) - math.pi
            self.angle += roznica * min(1.0, 8.0 * dt)
        self._krok(dt, world, predkosc_mult)

    def _krok(self, dt, world, predkosc_mult=1.0):
        v = C.ANT_BASE_SPEED * self.szybkosc * world.mods["activity"] * predkosc_mult
        nast = self.pos + Vector2(math.cos(self.angle), math.sin(self.angle)) * v * dt
        for obs in world.obstacles:
            od = nast - obs.pos
            if od.length() < obs.radius + 5:
                # obejście przeszkody: skręt wzdłuż jej brzegu
                styczna = math.atan2(od.y, od.x) + math.pi / 2
                self.angle = styczna
                nast = self.pos + Vector2(math.cos(styczna), math.sin(styczna)) * v * dt
                break
        nast.x = min(max(nast.x, 8), C.WIDTH - 8)
        nast.y = min(max(nast.y, 8), C.HEIGHT - 8)
        self.pos = nast
        if self.feromon:
            world.pher.deposit("food", self.pos.x, self.pos.y, C.AGENT_PHEROMONE)

    def _najblizsze_jedzenie(self, world, punkt):
        best, bestd = None, None
        for t in world.all_forageables():
            d = punkt.distance_to(t.pos)
            if bestd is None or d < bestd:
                best, bestd = t, d
        return best

    def _najblizszy_drapieznik(self, world, punkt, promien):
        best, bestd = None, None
        for sp in world.spiders + world.wasps:
            if not sp.alive:
                continue
            d = punkt.distance_to(sp.pos)
            if d <= promien and (bestd is None or d < bestd):
                best, bestd = sp, d
        return best

    def _skoncz(self, wynik, rutyna=False):
        """Kończy akcję. Rutynowe końce (wzięła jedzenie, oddała je, odpoczęła)
        przejmuje autopilot bez pytania Claude - to obniża liczbę zapytań."""
        self.wynik = wynik
        self.akcja_skonczona = True
        if not rutyna:
            self.potrzebna_decyzja = True

    # --- ustawianie akcji ---------------------------------------------------
    def ustaw_akcje(self, akcja, cel=None, feromon=False):
        self.akcja = akcja
        self.cel = cel
        self.cel_obiekt = None
        self.feromon = feromon
        self.czas_akcji = 0.0
        self.akcja_skonczona = False
        if akcja == "eksploruj" and cel is None:
            kat = random.uniform(0, 2 * math.pi)
            self.cel = Vector2(
                min(max(self.pos.x + math.cos(kat) * 300, 30), C.WIDTH - 30),
                min(max(self.pos.y + math.sin(kat) * 300, 30), C.HEIGHT - 30),
            )

    def autopilot(self):
        """Co robi mrówka, gdy skończyła akcję, a Claude jeszcze nie odpowiedział."""
        if self.niesie > 0 or self.energy < self.max_energy * 0.25:
            self.ustaw_akcje("wracaj_do_gniazda", feromon=self.niesie > 0)
        else:
            self.ustaw_akcje("zbieraj")
        self.akcja_skonczona = False

    # --- aktualizacja -------------------------------------------------------
    def update(self, dt, world):
        if not self.alive:
            return
        dzien = world.time / C.DAY_LENGTH_SECONDS
        self.czas_akcji += dt
        self.energy -= C.ANT_ENERGY_DRAIN * 0.8 * world.mods["activity"] * dt
        if self.energy <= 0:
            self._smierc(world, "z głodu i wyczerpania")
            return
        if not self.zglosila_glod and self.energy < self.max_energy * 0.3:
            self.zglosila_glod = True
            self.zdarzenie(dzien, "Kończą ci się siły.")
            self.okazja = "Prawie padłaś z wyczerpania."
            self.potrzebna_decyzja = True
        if self.energy > self.max_energy * 0.6:
            self.zglosila_glod = False

        # nowe zagrożenie w polu widzenia - warto zapytać Claude, co dalej
        for sp in world.spiders + world.wasps:
            if sp.alive and id(sp) not in self.znane_zagrozenia and self.pos.distance_to(sp.pos) < 120:
                self.znane_zagrozenia.add(id(sp))
                rodzaj = "pająk" if sp in world.spiders else "osa"
                self.zdarzenie(dzien, f"Zauważyłaś: {rodzaj} blisko ciebie.")
                self.potrzebna_decyzja = True

        if self.akcja_skonczona:
            self.autopilot()

        getattr(self, "_akcja_" + self.akcja)(dt, world, dzien)
        self._walka_i_niebezpieczenstwo(dt, world, dzien)

    def _akcja_idz_do(self, dt, world, dzien):
        if self.cel is None:
            self._skoncz("Nie podałaś celu.")
            return
        self._idz_w_strone(self.cel, dt, world)
        if self.pos.distance_to(self.cel) < 10:
            self._skoncz(f"Dotarłaś do ({int(self.cel.x)}, {int(self.cel.y)}).")

    def _akcja_eksploruj(self, dt, world, dzien):
        if self.cel is None:
            self.ustaw_akcje("eksploruj")
        self.angle += random.uniform(-1, 1) * dt * 2
        self._idz_w_strone(self.cel, dt, world)
        if self.pos.distance_to(self.cel) < 15 or self.czas_akcji > 25:
            self._skoncz("Skończyłaś wędrówkę.")

    def _akcja_zbieraj(self, dt, world, dzien):
        if self.niesie > 0:
            self._skoncz("Już niesiesz jedzenie - zanieś je do gniazda.", rutyna=True)
            return
        t = self.cel_obiekt
        if t is None or t.amount <= 0.5 or (hasattr(t, "alive") and not t.alive):
            t = self._najblizsze_jedzenie(world, self.cel if self.cel is not None else self.pos)
            self.cel_obiekt = t
        if t is None:
            self._skoncz("Nigdzie na mapie nie ma teraz jedzenia.")
            return
        self._idz_w_strone(t.pos, dt, world)
        if self.pos.distance_to(t.pos) <= t.radius + 4:
            got = t.take(C.AGENT_LOAD)
            if got > 0:
                self.niesie = got
                nazwa = getattr(t, "species_name", "mszyce (spadź)")
                self._skoncz(f"Wzięłaś {got:.0f} jedzenia z: {nazwa} ({int(t.pos.x)}, {int(t.pos.y)}).", rutyna=True)
            else:
                self.cel_obiekt = None

    def _akcja_wracaj_do_gniazda(self, dt, world, dzien):
        nest = world.nest
        if self.pos.distance_to(nest.pos) > nest.radius:
            self._idz_w_strone(nest.pos, dt, world)
            return
        if self.niesie > 0:
            nest.food += self.niesie
            self.dostarczone += self.niesie
            self.zdarzenie(dzien, f"Dostarczyłaś {self.niesie:.0f} jedzenia do gniazda.")
            self.niesie = 0.0
            self.feromon = False
        if not self._jedz(dt, world):
            self._skoncz(f"Jesteś w gnieździe, energia {self._procent()}%.", rutyna=True)

    def _akcja_odpoczywaj(self, dt, world, dzien):
        self.feromon = False
        nest = world.nest
        if self.pos.distance_to(nest.pos) > nest.radius:
            self._idz_w_strone(nest.pos, dt, world)
            return
        if not self._jedz(dt, world):
            self._skoncz(f"Wypoczęta, energia {self._procent()}%.", rutyna=True)

    def _jedz(self, dt, world):
        """Zwraca True, dopóki jeszcze się karmi."""
        if self.energy >= self.max_energy - 0.5:
            return False
        if world.nest.food <= 0:
            self.zdarzenie(world.time / C.DAY_LENGTH_SECONDS, "W gnieździe nie ma jedzenia!")
            self.okazja = "Przyszłaś się najeść, a w gnieździe nie było jedzenia."
            return False
        gain = min(C.ANT_ENERGY_REGEN * dt, self.max_energy - self.energy)
        self.energy += gain
        world.nest.food = max(0.0, world.nest.food - gain * C.ANT_FEED_COST)
        return True

    def _akcja_atakuj(self, dt, world, dzien):
        sp = self.cel_obiekt
        if sp is None or not sp.alive:
            sp = self._najblizszy_drapieznik(world, self.cel if self.cel is not None else self.pos, C.AGENT_VIEW_RADIUS)
            if sp is None and self.cel_obiekt is not None:
                self._skoncz("Wróg pokonany albo zniknął.")
                return
            self.cel_obiekt = sp
        if sp is None:
            self._skoncz("W pobliżu nie ma wroga do zaatakowania.")
            return
        self._idz_w_strone(sp.pos, dt, world, 1.2)
        if self.czas_akcji > 30:
            self._skoncz("Pościg trwał za długo, odpuszczasz.")

    def _akcja_uciekaj(self, dt, world, dzien):
        sp = self._najblizszy_drapieznik(world, self.pos, 160)
        if sp is None or self.czas_akcji > 8:
            self._skoncz("Uciekłaś, jesteś bezpieczna.")
            return
        od = self.pos - sp.pos
        ku_gniazdu = world.nest.pos - self.pos
        kierunek = (od.normalize() if od.length() > 0 else Vector2(1, 0)) * 2
        if ku_gniazdu.length() > 0:
            kierunek += ku_gniazdu.normalize()
        self._idz_w_strone(self.pos + kierunek * 50, dt, world, 1.3)

    def _walka_i_niebezpieczenstwo(self, dt, world, dzien):
        for sp in world.spiders + world.wasps:
            if not sp.alive:
                continue
            pajak = sp in world.spiders
            zasieg = (C.SPIDER_ATTACK_RADIUS if pajak else C.WASP_ATTACK_RADIUS) + 4
            if self.pos.distance_to(sp.pos) > zasieg:
                continue
            nazwa = "pająka" if pajak else "osę"
            if self.akcja == "atakuj":
                if random.random() < C.AGENT_HIT_CHANCE * self.sila * dt:
                    sp.hp -= 1
                    self.trafienia += 1
                    if sp.hp <= 0:
                        self.zdarzenie(dzien, f"Zabiłaś {nazwa}!")
                        self.okazja = f"Pokonałaś {nazwa} w walce."
                        self._skoncz(f"Pokonałaś {nazwa}.")
                ryzyko = C.AGENT_DEATH_CHANCE_FIGHTING / self.sila
            else:
                ryzyko = C.AGENT_DEATH_CHANCE
            if random.random() < ryzyko * dt:
                self._smierc(world, f"zabita przez {nazwa}")
                return

    def _smierc(self, world, przyczyna):
        self.alive = False
        self.przyczyna = przyczyna
        world.spawn_corpse(self.pos, "ant")

    def _procent(self):
        return int(100 * self.energy / self.max_energy)


class KsiegaMrowiska:
    """Wspólna wiedza kolonii: ogólne lekcje zapisane przez agentki.

    Lekcje potwierdzane przez kolejne agentki zyskują wagę; gdy Księga jest
    pełna, wypada najsłabsza. Zapis do pliku ksiega_mrowiska.json, więc
    wiedza przechodzi do następnych gier (plik jest w .gitignore).
    """

    def __init__(self, sciezka=None):
        self.sciezka = sciezka or os.path.join(KATALOG, "ksiega_mrowiska.json")
        self.lekcje = []  # dict(tekst, autor, kolonia, waga)
        try:
            with open(self.sciezka, encoding="utf-8") as f:
                dane = json.load(f)
            self.lekcje = [l for l in dane.get("lekcje", []) if isinstance(l, dict) and l.get("tekst")]
        except (OSError, ValueError):
            pass

    def _zapisz(self):
        try:
            tmp = self.sciezka + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"lekcje": self.lekcje}, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.sciezka)
        except OSError:
            pass  # np. przeglądarka - Księga działa wtedy tylko w tej grze

    def posortowane(self):
        return sorted(self.lekcje, key=lambda l: -l.get("waga", 1))

    def dodaj(self, tekst, autor, kolonia):
        tekst = " ".join(tekst.split())[:200]
        if len(tekst) < 12:
            return None
        klucz = tekst.lower()
        for l in self.lekcje:
            if l["tekst"].lower() == klucz:
                l["waga"] = l.get("waga", 1) + 1
                self._zapisz()
                return None
        if len(self.lekcje) >= C.BOOK_MAX_LESSONS:
            najslabsza = min(self.lekcje, key=lambda l: l.get("waga", 1))
            self.lekcje.remove(najslabsza)
        self.lekcje.append(dict(tekst=tekst, autor=autor, kolonia=kolonia, waga=1))
        self._zapisz()
        return tekst

    def potwierdz(self, numer):
        """Numer jak w opisie sytuacji (1 = najważniejsza)."""
        lista = self.posortowane()[: C.BOOK_SHOWN]
        if not isinstance(numer, int) or not 1 <= numer <= len(lista):
            return None
        lista[numer - 1]["waga"] = lista[numer - 1].get("waga", 1) + 1
        self._zapisz()
        return lista[numer - 1]["tekst"]

    def opis(self):
        return [
            f"{i}. {l['tekst']} (waga {l.get('waga', 1)}; {l.get('autor', '?')}, {l.get('kolonia', '?')})"
            for i, l in enumerate(self.posortowane()[: C.BOOK_SHOWN], start=1)
        ]


class ZarzadAgentow:
    """Trzyma mrówki-agentów, rozsyła zapytania do Claude i stosuje odpowiedzi."""

    def __init__(self, liczba, world):
        self.world = world
        self.profile = list(C.AGENT_PROFILES[:liczba])
        self.agenci = [AgentAnt(p, world.nest.pos) for p in self.profile]
        self.do_odrodzenia = []  # (czas symulacji, profil)
        self.pokolenie = {p["imie"]: 1 for p in self.profile}
        self.dziennik = deque(maxlen=C.AGENT_LOG_LINES)  # (kolor, tekst) - panel boczny
        self.pokaz_panel = True
        self.ksiega = KsiegaMrowiska()
        self.kolonia = f"{world.cfg['biome']}, {world.cfg['season']}"
        self.spuscizna = {}  # imię -> notatki zmarłej agentki dla następczyni
        self.potwierdzenia = set()  # (imię, tekst lekcji) - jedno potwierdzenie na agentkę

        self.zapytania = 0
        self.tokeny_we = 0
        self.tokeny_wy = 0
        self.bledy = 0
        self.status = ""
        self.klient = None
        self.wykonawca = None

        if anthropic is None:
            self.status = "brak pakietu anthropic - agenci na autopilocie"
        elif sys.platform == "emscripten":
            self.status = "wersja przeglądarkowa - agenci na autopilocie"
        else:
            klucz = czytaj_klucz()
            try:
                self.klient = anthropic.Anthropic(api_key=klucz) if klucz else anthropic.Anthropic()
                self.wykonawca = ThreadPoolExecutor(max_workers=max(1, liczba), thread_name_prefix="mrowka")
                self.status = f"model {C.AGENT_MODEL}"
            except Exception as e:  # brak danych logowania itp.
                self.status = f"brak klucza API ({type(e).__name__}) - agenci na autopilocie"
        self.loguj((200, 200, 200), f"Agenci: {', '.join(a.imie for a in self.agenci)}. {self.status}")

    def loguj(self, kolor, tekst):
        self.dziennik.append((kolor, tekst))

    def zamknij(self):
        if self.wykonawca is not None:
            self.wykonawca.shutdown(wait=False, cancel_futures=True)
            self.wykonawca = None

    # --- pętla --------------------------------------------------------------
    def update(self, dt, world):
        teraz = time.monotonic()
        for a in self.agenci:
            a.update(dt, world)
            if not a.alive:
                continue
            if a.zapytanie is not None and a.zapytanie.done():
                self._zastosuj(a, a.zapytanie)
                a.zapytanie = None
            if self.wykonawca is not None and a.zapytanie is None:
                odstep = teraz - a.ostatnie_zapytanie
                if (a.potrzebna_decyzja and odstep >= C.AGENT_MIN_GAP) or odstep >= C.AGENT_DECISION_INTERVAL:
                    self._zapytaj(a, world, teraz)

        for a in [a for a in self.agenci if not a.alive]:
            self.loguj(a.kolor, f"+ {a.imie} nie żyje ({a.przyczyna}).")
            for inny in self.agenci:
                if inny.alive:
                    inny.zdarzenie(world.time / C.DAY_LENGTH_SECONDS, f"{a.imie} ({a.rola}) zginęła: {a.przyczyna}.")
                    inny.okazja = f"{a.imie} ({a.rola}) zginęła: {a.przyczyna}. Ostatnio robiła: {a.akcja}."
                    inny.potrzebna_decyzja = True
            self.spuscizna[a.imie] = list(a.notatki)
            profil = next(p for p in self.profile if p["imie"] == a.imie)
            self.do_odrodzenia.append((world.time + C.AGENT_RESPAWN_TIME, profil))
        self.agenci = [a for a in self.agenci if a.alive]

        for kiedy, profil in list(self.do_odrodzenia):
            if world.time >= kiedy and world.nest.food >= C.AGENT_RESPAWN_FOOD:
                world.nest.food -= C.AGENT_RESPAWN_FOOD
                self.do_odrodzenia.remove((kiedy, profil))
                self.pokolenie[profil["imie"]] += 1
                nowa = AgentAnt(profil, world.nest.pos)
                # następczyni dostaje notatki poprzedniczki - wiedza o tej mapie nie ginie
                for n in self.spuscizna.pop(profil["imie"], [])[-(C.AGENT_MEMORY_NOTES - 1):]:
                    nowa.notatki.append(n)
                nowa.notatki.append(
                    f"Jesteś {self.pokolenie[profil['imie']]}. pokoleniem tej mrówki - poprzedniczka zginęła; "
                    "notatki wyżej to jej wiedza."
                )
                self.agenci.append(nowa)
                self.loguj(profil["kolor"], f"W gnieździe wykluła się nowa {profil['imie']}.")

    # --- Claude -------------------------------------------------------------
    def _zapytaj(self, a, world, teraz):
        a.ostatnie_zapytanie = teraz
        a.potrzebna_decyzja = False
        system = (
            SYSTEM_WSPOLNY
            + f"\n\nNazywasz się {a.imie}. Twoja rola: {a.rola}. {a.charakter}"
        )
        opis = self._opis_sytuacji(a, world)
        a.skrzynka.clear()
        a.okazja = None
        self.zapytania += 1
        a.zapytanie = self.wykonawca.submit(self._wywolaj_claude, system, opis)

    def _wywolaj_claude(self, system, opis):
        """Działa w wątku roboczym - nie dotyka stanu symulacji."""
        kwargs = dict(
            model=C.AGENT_MODEL,
            max_tokens=C.AGENT_MAX_TOKENS,
            system=system,
            tools=[NARZEDZIE],
            output_config={"effort": C.AGENT_EFFORT},
            messages=[{"role": "user", "content": opis}],
        )
        # Haiku pozwala wymusić wywołanie narzędzia; nowsze Opus/Sonnet zwracają
        # na to błąd 400, więc dla nich zostaje "auto" + polecenie w prompcie
        if C.AGENT_MODEL.startswith("claude-haiku"):
            kwargs["tool_choice"] = {"type": "tool", "name": "dzialaj"}
        odp = self.klient.messages.create(**kwargs)
        return odp

    def _zastosuj(self, a, przyszlosc):
        dzien = self.world.time / C.DAY_LENGTH_SECONDS
        try:
            odp = przyszlosc.result()
        except Exception as e:
            self.bledy += 1
            self.status = f"błąd API: {type(e).__name__}"
            if anthropic is not None and isinstance(e, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
                self.status = "zły klucz API - agenci na autopilocie"
                self.zamknij()
            elif anthropic is not None and isinstance(e, anthropic.BadRequestError):
                self.status = f"błąd zapytania: {getattr(e, 'message', e)}"[:120]
            return
        self.tokeny_we += odp.usage.input_tokens
        self.tokeny_wy += odp.usage.output_tokens
        if odp.stop_reason == "refusal":
            self.loguj(a.kolor, f"{a.imie}: (Claude odmówił odpowiedzi)")
            return
        decyzja = next((b.input for b in odp.content if b.type == "tool_use" and b.name == "dzialaj"), None)
        if not isinstance(decyzja, dict) or decyzja.get("akcja") not in AKCJE:
            self.bledy += 1
            return
        self.status = f"model {C.AGENT_MODEL}"

        lekcja = (decyzja.get("lekcja") or "").strip()
        if lekcja:
            dodana = self.ksiega.dodaj(lekcja, a.imie, self.kolonia)
            if dodana:
                self.loguj((255, 230, 150), f"[Księga] {a.imie} zapisuje: {dodana}")
        numer = decyzja.get("potwierdz_lekcje")
        lista = self.ksiega.posortowane()[: C.BOOK_SHOWN]
        potwierdzona = None
        if isinstance(numer, int) and 1 <= numer <= len(lista) and (a.imie, lista[numer - 1]["tekst"]) not in self.potwierdzenia:
            self.potwierdzenia.add((a.imie, lista[numer - 1]["tekst"]))
            potwierdzona = self.ksiega.potwierdz(numer)
        if potwierdzona:
            self.loguj((255, 230, 150), f"[Księga] {a.imie} potwierdza: {potwierdzona}")

        cel = None
        if decyzja.get("cel_x") is not None and decyzja.get("cel_y") is not None:
            cel = Vector2(
                min(max(int(decyzja["cel_x"]), 10), C.WIDTH - 10),
                min(max(int(decyzja["cel_y"]), 10), C.HEIGHT - 10),
            )
        a.ustaw_akcje(decyzja["akcja"], cel, bool(decyzja.get("zostawiaj_feromon")))
        a.mysl = (decyzja.get("mysl") or "").strip()[:140]
        a.mysl_czas = time.monotonic()
        if a.mysl:
            self.loguj(a.kolor, f"{a.imie} [{decyzja['akcja']}]: {a.mysl}")

        notatka = (decyzja.get("notatka") or "").strip()
        if notatka:
            a.notatki.append(f"[dzień {dzien:.1f}] {notatka[:160]}")

        tresc = (decyzja.get("wiadomosc") or "").strip()[:200]
        adresat = (decyzja.get("wiadomosc_do") or "").strip()
        if tresc and adresat:
            odbiorcy = [b for b in self.agenci if b is not a and b.alive
                        and (adresat.lower() in ("wszystkie", "wszyscy") or b.imie.lower() == adresat.lower())]
            for b in odbiorcy:
                b.skrzynka.append(f"{a.imie} ({a.rola}) mówi: {tresc}")
                b.potrzebna_decyzja = True
            if odbiorcy:
                do = "wszystkich" if len(odbiorcy) > 1 else odbiorcy[0].imie
                self.loguj(a.kolor, f"{a.imie} -> {do}: {tresc}")

    def _opis_sytuacji(self, a, w):
        dzien = w.time / C.DAY_LENGTH_SECONDS
        pora = "dzień" if w.daylight >= 0.5 else "noc"
        pogoda = {"clear": "pogodnie", "rain": "deszcz", "snow": "śnieg", "drought": "susza"}.get(w.weather, w.weather)
        L = [
            f"Czas: dzień {dzien:.1f}, {pora}. Pora roku: {w.cfg['season']}. Pogoda: {pogoda}, {w.temperature:.0f}°C.",
            f"Ty: {a.imie} ({a.rola}). Pozycja ({int(a.pos.x)}, {int(a.pos.y)}). Energia {a._procent()}%. "
            f"Niesiesz jedzenie: {'tak, ' + str(int(a.niesie)) if a.niesie > 0 else 'nie'}.",
            f"Gniazdo: {_opis_miejsca(a.pos, w.nest.pos)}. Zapas jedzenia w gnieździe: {int(w.nest.food)}. "
            f"Zwykłych mrówek w kolonii: {w.ant_swarm.n}.",
            f"Ostatnia akcja: {a.akcja}. Wynik: {a.wynik}",
            "",
            f"Co widzisz (do {int(C.AGENT_VIEW_RADIUS)} px):",
        ]
        widok = []
        for t in w.all_forageables():
            d = a.pos.distance_to(t.pos)
            if d <= C.AGENT_VIEW_RADIUS:
                nazwa = getattr(t, "species_name", None) or f"kolonia mszyc ({t.count} szt., spadź)"
                widok.append((d, f"- jedzenie: {nazwa} {_opis_miejsca(a.pos, t.pos)}, ilość {int(t.amount)}"))
        for sp in w.spiders + w.wasps:
            d = a.pos.distance_to(sp.pos)
            if sp.alive and d <= C.AGENT_VIEW_RADIUS:
                rodzaj = "pająk" if sp in w.spiders else "osa"
                widok.append((d - 1000, f"- ZAGROŻENIE: {rodzaj} {_opis_miejsca(a.pos, sp.pos)}, życie {sp.hp}"))
        for co in w.corpses:
            d = a.pos.distance_to(co.pos)
            if d <= C.AGENT_VIEW_RADIUS * 0.6:
                widok.append((d, f"- truchło ({co.kind}) {_opis_miejsca(a.pos, co.pos)}"))
        for fl in w.bird_flocks:
            if fl.alive:
                widok.append((-2000, f"- nad okolicą krąży stado ptaków {_opis_miejsca(a.pos, fl.pos)}"))
        widok.sort(key=lambda x: x[0])
        L += [t for _, t in widok[:10]] or ["- nic ciekawego"]

        inni = [b for b in self.agenci if b is not a and b.alive]
        if inni:
            L += ["", "Inne mrówki-agenci:"]
            for b in inni:
                L.append(f"- {b.imie} ({b.rola}) {_opis_miejsca(a.pos, b.pos)}, robi: {b.akcja}, energia {b._procent()}%")
        if a.skrzynka:
            L += ["", "Wiadomości do ciebie:"] + [f"- {m}" for m in a.skrzynka[-C.AGENT_INBOX_MAX:]]
        if a.notatki:
            L += ["", "Twoje notatki:"] + [f"- {n}" for n in a.notatki]
        if a.zdarzenia:
            L += ["", "Ostatnie zdarzenia:"] + [f"- {z}" for z in list(a.zdarzenia)[-6:]]
        ksiega = self.ksiega.opis()
        if a.okazja:
            L += ["", f"WAŻNE ZDARZENIE: {a.okazja} Zastanów się, czego to uczy kolonię. Jeśli to wiedza, "
                  "której nie ma w Księdze, zapisz ją w polu lekcja."]
        L += ["", "Księga mrowiska (wiedza kolonii, od najważniejszej):"] + (ksiega or ["- jeszcze pusta"])
        L += ["", "Co robisz teraz? Wywołaj narzędzie dzialaj."]
        return "\n".join(L)

    # --- rysowanie ----------------------------------------------------------
    def koszt_usd(self):
        return self.tokeny_we * C.AGENT_PRICE_IN_PER_MTOK / 1e6 + self.tokeny_wy * C.AGENT_PRICE_OUT_PER_MTOK / 1e6

    def linia_hud(self):
        zywe = len(self.agenci)
        return (
            f"Agenci Claude: {zywe}   zapytań: {self.zapytania}   tokeny: {self.tokeny_we}/{self.tokeny_wy}"
            f"   koszt ~${self.koszt_usd():.3f}   {self.status}   TAB=panel"
        )

    def draw(self, surface, font, font_maly):
        teraz = time.monotonic()
        for a in self.agenci:
            x, y = int(a.pos.x), int(a.pos.y)
            pygame.draw.circle(surface, (20, 20, 20), (x, y), 6)
            pygame.draw.circle(surface, a.kolor, (x, y), 5)
            hx = x + int(math.cos(a.angle) * 9)
            hy = y + int(math.sin(a.angle) * 9)
            pygame.draw.line(surface, a.kolor, (x, y), (hx, hy), 2)
            if a.niesie > 0:
                pygame.draw.circle(surface, (255, 215, 60), (x, y), 3)
            if a.feromon:
                pygame.draw.circle(surface, (255, 120, 200), (x, y), 9, width=1)
            napis = a.imie + (" ..." if a.zapytanie is not None else "")
            t = font_maly.render(napis, True, a.kolor)
            surface.blit(t, (x - t.get_width() // 2, y - 20))

            if a.mysl and teraz - a.mysl_czas < C.AGENT_THOUGHT_SECONDS:
                linie = _zawin(a.mysl, 30)[:3]
                obrazy = [font_maly.render(l, True, (25, 25, 25)) for l in linie]
                w = max(o.get_width() for o in obrazy) + 10
                h = 15 * len(obrazy) + 6
                bx = min(max(x - w // 2, 2), C.WIDTH - w - 2)
                by = max(y - 24 - h, 2)
                dymek = pygame.Surface((w, h), pygame.SRCALPHA)
                dymek.fill((255, 255, 245, 215))
                surface.blit(dymek, (bx, by))
                pygame.draw.rect(surface, a.kolor, (bx, by, w, h), width=1, border_radius=4)
                for i, o in enumerate(obrazy):
                    surface.blit(o, (bx + 5, by + 3 + i * 15))

        if self.pokaz_panel:
            self._draw_panel(surface, font_maly)

    def _draw_panel(self, surface, font):
        szer = 340
        x0 = C.WIDTH - szer - 8
        naglowek = [((240, 240, 240), "Mrówki-agenci Claude")]
        for a in self.agenci:
            naglowek.append((a.kolor, f"{a.imie} ({a.rola}) {a._procent()}%  {a.akcja}"
                                      + (f"  niesie {int(a.niesie)}" if a.niesie > 0 else "")))
        for kiedy, profil in self.do_odrodzenia:
            naglowek.append((profil["kolor"], f"{profil['imie']} - czeka na wyklucie"))
        naglowek.append(((255, 230, 150), f"Księga mrowiska: {len(self.ksiega.lekcje)} lekcji"))
        naglowek.append(((160, 160, 160), "-" * 40))
        dziennik = []
        for kolor, tekst in self.dziennik:
            for i, l in enumerate(_zawin(tekst, 52)):
                dziennik.append((kolor, ("  " if i else "") + l))
        linie = naglowek + dziennik[-C.AGENT_PANEL_MAX_LINES:]
        h = 15 * len(linie) + 10
        panel = pygame.Surface((szer, h), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 150))
        surface.blit(panel, (x0, 8))
        for i, (kolor, tekst) in enumerate(linie):
            surface.blit(font.render(tekst, True, kolor), (x0 + 6, 13 + i * 15))
