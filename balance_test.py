"""Headless test długoterminowej stabilności ekosystemu (bez okna/rysowania).

Napędza Simulation bezpośrednio przez _update_once(dt) w pętli, pomijając
pygame/rendering i sterowanie prędkością z main.py - dzięki temu symulacja
wielu "lat kolonii" trwa sekundy/minuty zamiast godzin.

Użycie:
    python balance_test.py                      # domyślny przebieg (szybki)
    python balance_test.py --years 50            # dłuższy, pełne "dekady"
    python balance_test.py --scenario "Las (ciepły start)"
    python balance_test.py --seeds 3              # kilka ziaren losowości na scenariusz

Kryterium niepowodzenia scenariusza:
    - populacja mrówek == 0 po okresie rozruchu (GRACE_YEARS) -> wymarcie kolonii
    - populacja mrówek na końcu runu < 10% szczytowej populacji w tym runie
      -> trwały, niewyleczony zapaść (możliwa "pułapka wymarcia")
Wymarcie pojedynczego gatunku towarzyszącego (mszyce/pająki/osy/biedronki/
chrząszcze/dżdżownice/rośliny) na koniec runu jest tylko ostrzeżeniem - nie
wywala scenariusza, bo lokalne wahania/wymarcia są częścią zdrowej dynamiki
(np. epizod ptaków przerzedzający drapieżniki).
"""
import argparse
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

import config as C  # noqa: E402
from simulation import Simulation  # noqa: E402

GRACE_YEARS = 2.0
SAMPLE_DAYS = 30.0  # co ile symulowanych dni logujemy metryki

DEFAULT_SCENARIOS = [
    dict(name="Łąka (ciepły start)", biome="Łąka", season="Lato", species="Mrówka łąkowa", ant_count=200),
    dict(name="Las (ciepły start)", biome="Las", season="Lato", species="Rudnica leśna", ant_count=200),
    dict(name="Pustynia (ciepły start)", biome="Pustynia", season="Lato", species="Mrówka pustynna", ant_count=200),
    dict(name="Łąka (zimny start)", biome="Łąka", season="Zima", species="Mrówka łąkowa", ant_count=150),
    dict(
        name="Niedopasowanie (leśna mrówka w zimowej pustyni)",
        biome="Pustynia", season="Zima", species="Rudnica leśna", ant_count=150,
    ),
    dict(
        name="Wysoka presja drapieżników",
        biome="Łąka", season="Lato", species="Mrówka łąkowa", ant_count=250,
        companions_overrides=dict(Mszyce=60, Pająki=8, Osy=10, Biedronki=20, Chrząszcze=20, Dżdżownice=25),
    ),
]


def make_cfg(scenario):
    companions = {name: d["default"] for name, d in C.COMPANIONS.items()}
    companions.update(scenario.get("companions_overrides", {}))
    return dict(
        biome=scenario["biome"],
        season=scenario["season"],
        species=scenario["species"],
        ant_count=scenario["ant_count"],
        companions=companions,
    )


def run_scenario(scenario, years, dt, seed):
    import random

    import numpy as np

    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))

    sim = Simulation(make_cfg(scenario))
    total_seconds = years * 365.0 * C.DAY_LENGTH_SECONDS
    grace_seconds = GRACE_YEARS * 365.0 * C.DAY_LENGTH_SECONDS
    sample_interval = SAMPLE_DAYS * C.DAY_LENGTH_SECONDS
    next_sample = 0.0

    samples = []
    steps = int(total_seconds / dt)
    for _ in range(steps):
        sim._update_once(dt)
        if sim.time >= next_sample:
            next_sample += sample_interval
            samples.append(
                dict(
                    t=sim.time,
                    ants=sim.ant_swarm.n,
                    food=sim.nest.food,
                    plants=len(sim.plants),
                    aphids=sum(c.count for c in sim.aphids),
                    spiders=len(sim.spiders),
                    wasps=len(sim.wasps),
                    ladybugs=len(sim.ladybugs),
                    beetles=len(sim.beetles),
                    earthworms=len(sim.earthworms),
                )
            )

    post_grace = [s for s in samples if s["t"] >= grace_seconds]
    check_samples = post_grace if post_grace else samples
    peak_ants = max((s["ants"] for s in samples), default=0)
    final = samples[-1] if samples else None

    extinct = any(s["ants"] == 0 for s in check_samples)
    collapsed = final is not None and peak_ants > 0 and final["ants"] < 0.10 * peak_ants
    failed = extinct or collapsed

    warnings = []
    if final is not None:
        for key in ("plants", "aphids", "spiders", "wasps", "ladybugs", "beetles", "earthworms"):
            if final[key] == 0:
                warnings.append(key)

    return dict(
        samples=samples, failed=failed, extinct=extinct, collapsed=collapsed,
        peak_ants=peak_ants, final=final, warnings=warnings,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=float, default=5.0)
    # dt MUSI byc <= 0.05s (C.SPEED... clamp w main.py) - przy wiekszym kroku
    # mrowki "przeskakuja" cele i tracą orientację (pogoń za feromonem,
    # unikanie przeszkód), co daje fałszywy obraz masowego wymierania,
    # niezwiązany z rzeczywistym balansem gry (zweryfikowane empirycznie).
    parser.add_argument("--dt", type=float, default=0.05)
    parser.add_argument("--seeds", type=int, default=1)
    parser.add_argument("--scenario", type=str, default=None, help="uruchom tylko scenariusz o tej nazwie")
    args = parser.parse_args()

    pygame.init()
    pygame.display.set_mode((1, 1))

    scenarios = DEFAULT_SCENARIOS
    if args.scenario:
        scenarios = [s for s in scenarios if s["name"] == args.scenario]
        if not scenarios:
            print(f"Nieznany scenariusz: {args.scenario}")
            sys.exit(2)

    any_failed = False
    print(f"Test balansu: {args.years:.1f} lat kolonii, dt={args.dt}s, {args.seeds} ziaren losowości\n")

    for scenario in scenarios:
        seed_results = [run_scenario(scenario, args.years, args.dt, seed=1000 * (i + 1)) for i in range(args.seeds)]
        scenario_failed = any(r["failed"] for r in seed_results)
        any_failed = any_failed or scenario_failed

        status = "PADŁ" if scenario_failed else "OK"
        print(f"=== {scenario['name']} -> {status} ===")
        for i, r in enumerate(seed_results):
            final = r["final"]
            final_ants = final["ants"] if final else 0
            reason = ""
            if r["extinct"]:
                reason = " [WYMARCIE KOLONII]"
            elif r["collapsed"]:
                reason = f" [ZAPAŚĆ: {final_ants}/{r['peak_ants']} szczytu]"
            print(
                f"  seed#{i}: szczyt mrówek={r['peak_ants']:4d}  koniec={final_ants:4d}"
                f"  rośliny={final['plants'] if final else 0:3d}"
                f"  mszyce={final['aphids'] if final else 0:4d}"
                f"  pająki={final['spiders'] if final else 0:2d}"
                f"  osy={final['wasps'] if final else 0:2d}"
                f"  biedronki={final['ladybugs'] if final else 0:2d}"
                f"  chrząszcze={final['beetles'] if final else 0:2d}"
                f"  dżdżownice={final['earthworms'] if final else 0:2d}"
                f"{reason}"
            )
            if r["warnings"]:
                print(f"    ostrzeżenie: wymarły na koniec runu -> {', '.join(r['warnings'])}")
        print()

    if any_failed:
        print("WYNIK: co najmniej jeden scenariusz wskazuje na wymarcie/zapaść kolonii.")
        sys.exit(1)
    print("WYNIK: wszystkie scenariusze przetrwały bez wymarcia kolonii.")
    sys.exit(0)


if __name__ == "__main__":
    main()
