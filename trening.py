"""Trening mrowiska: seria gier bez okna, w których mrówki-agenci Claude
zbierają doświadczenie i zapisują lekcje w Księdze mrowiska.

Gry idą w różnych biomach i porach roku, żeby lekcje były ogólne. Na koniec
Claude porządkuje Księgę (scala powtórzone lekcje, sumuje ich wagi).

Użycie:
    python trening.py                    # 6 gier po 4 minuty, ok. 0,5 USD
    python trening.py --gier 12 --minut 5
    python trening.py --tylko-porzadkuj  # samo uporządkowanie Księgi

Koszt zależy od liczby zapytań (licznik na końcu każdej gry). Decyzje agentek
są liczone w czasie rzeczywistym, więc symulacja idzie tylko --predkosc razy
szybciej niż normalnie - inaczej agentki nie nadążałyby z myśleniem.
"""
import argparse
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

import config as C  # noqa: E402
from agenci import KsiegaMrowiska  # noqa: E402
from simulation import Simulation  # noqa: E402

SCENARIUSZE = [
    ("Łąka", "Lato", "Mrówka łąkowa"),
    ("Las", "Jesień", "Rudnica leśna"),
    ("Pustynia", "Lato", "Mrówka pustynna"),
    ("Łąka", "Zima", "Mrówka łąkowa"),
    ("Las", "Wiosna", "Rudnica leśna"),
    ("Pustynia", "Jesień", "Mrówka pustynna"),
]


def jedna_gra(nr, biom, pora, gatunek, args):
    cfg = dict(
        biome=biom, season=pora, species=gatunek, ant_count=args.mrowek, agents=args.agentki,
        companions={n: d["default"] for n, d in C.COMPANIONS.items()},
    )
    sim = Simulation(cfg)
    ag = sim.agents
    zgony = 0
    start = time.monotonic()
    koniec = start + args.minut * 60
    dt = 0.05
    while time.monotonic() < koniec:
        # symulacja ma iść "predkosc" razy szybciej niż czas rzeczywisty
        cel = (time.monotonic() - start) * args.predkosc
        while sim.time < cel:
            zywe = len(ag.agenci)
            sim._update_once(dt)
            zgony += max(0, zywe - len(ag.agenci))
        if sim.ant_swarm.n == 0 and not ag.agenci:
            break
        time.sleep(0.01)
    sim.close()
    dni = sim.time / C.DAY_LENGTH_SECONDS
    print(
        f"Gra {nr} ({biom}, {pora}): {dni:.1f} dni, kolonia {sim.ant_swarm.n} mrówek, "
        f"jedzenie {int(sim.nest.food)}, zgony agentek {zgony}, "
        f"nowe lekcje {ag.nowe_lekcje}, zapytań {ag.zapytania}, ~${ag.koszt_usd():.3f}",
        flush=True,
    )
    if ag.przyczyny_zgonow:
        print("    zgony:", ", ".join(f"{k} x{v}" for k, v in ag.przyczyny_zgonow.items()), flush=True)
    for kolor, tekst in ag.dziennik:
        if tekst.startswith("[Księga]"):
            print("   ", tekst, flush=True)
    return ag.koszt_usd(), ag.klient


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--gier", type=int, default=6)
    p.add_argument("--minut", type=float, default=4.0, help="czas rzeczywisty jednej gry")
    p.add_argument("--predkosc", type=float, default=3.0)
    p.add_argument("--agentki", type=int, default=C.AGENT_COUNT_DEFAULT)
    p.add_argument("--mrowek", type=int, default=200)
    p.add_argument("--tylko-porzadkuj", action="store_true")
    args = p.parse_args()

    pygame.init()
    pygame.display.set_mode((10, 10))

    koszt, klient = 0.0, None
    if not args.tylko_porzadkuj:
        for i in range(args.gier):
            biom, pora, gatunek = SCENARIUSZE[i % len(SCENARIUSZE)]
            k, klient = jedna_gra(i + 1, biom, pora, gatunek, args)
            koszt += k
        print(f"\nTrening: {args.gier} gier, razem ~${koszt:.2f}", flush=True)

    if klient is None:
        import anthropic
        from agenci import czytaj_klucz
        klucz = czytaj_klucz()
        klient = anthropic.Anthropic(api_key=klucz) if klucz else anthropic.Anthropic()
    ksiega = KsiegaMrowiska()
    wynik = ksiega.uporzadkuj(klient)
    if wynik:
        print(f"Księga uporządkowana: {wynik[0]} -> {wynik[1]} lekcji")
    print("\nKsięga mrowiska:")
    for linia in ksiega.opis() + [
        f"{i}. {l['tekst']} (waga {l['waga']})"
        for i, l in enumerate(ksiega.posortowane()[C.BOOK_SHOWN:], start=C.BOOK_SHOWN + 1)
    ]:
        print(" ", linia)


if __name__ == "__main__":
    main()
