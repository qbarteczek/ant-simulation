"""Stałe konfiguracyjne i dane scenariuszy symulacji mrowiska."""

WIDTH, HEIGHT = 1200, 800
CELL = 8  # rozmiar komórki siatki feromonów w px
GRID_W, GRID_H = WIDTH // CELL, HEIGHT // CELL

FPS = 60

# --- Biomy (miejsce) ---------------------------------------------------
BIOMES = {
    "Łąka": dict(
        bg=(96, 148, 60),
        bg2=(84, 134, 52),
        obstacle_color=(120, 100, 50),
        obstacle_density=11,
        food_density=1.0,
        food_regen=1.0,
        obstacle_shape="tuft",
        plant_mix={"Trawa łąkowa": 0.75, "Jagodowiec leśny": 0.1, "Sukulent pustynny": 0.15},
    ),
    "Las": dict(
        bg=(53, 82, 44),
        bg2=(45, 71, 37),
        obstacle_color=(75, 55, 35),
        obstacle_density=20,
        food_density=0.75,
        food_regen=0.9,
        obstacle_shape="log",
        plant_mix={"Trawa łąkowa": 0.15, "Jagodowiec leśny": 0.75, "Sukulent pustynny": 0.1},
    ),
    "Pustynia": dict(
        bg=(226, 201, 143),
        bg2=(214, 187, 125),
        obstacle_color=(178, 148, 96),
        obstacle_density=6,
        food_density=0.5,
        food_regen=0.6,
        obstacle_shape="rock",
        plant_mix={"Trawa łąkowa": 0.15, "Jagodowiec leśny": 0.05, "Sukulent pustynny": 0.8},
    ),
}

# --- Pory roku -----------------------------------------------------------
SEASONS = {
    "Wiosna": dict(food_regen=1.2, activity=1.0, spawn=1.3, predator=0.8, tint=None),
    "Lato": dict(food_regen=1.4, activity=1.15, spawn=1.1, predator=1.1, tint=None),
    "Jesień": dict(food_regen=0.7, activity=0.9, spawn=0.8, predator=1.2, tint=(190, 130, 60, 30)),
    "Zima": dict(food_regen=0.22, activity=0.4, spawn=0.15, predator=0.5, tint=(200, 225, 255, 55)),
}

# --- Pogoda: temperatura, opady, wiatr (klimat umiarkowany) -----------------
# średnia dobowa temperatura wg pory roku (°C) - punkt startowy, dalej
# modulowany porą dnia, biomem i losową zmiennością pogodową
SEASON_TEMP_BASE = {"Wiosna": 11.0, "Lato": 23.0, "Jesień": 9.0, "Zima": -1.0}
BIOME_TEMP_OFFSET = {"Łąka": 0.0, "Las": -2.5, "Pustynia": 6.0}
TEMP_DAY_AMPLITUDE = 5.0  # °C - o tyle cieplej w południe niż o północy
TEMP_NOISE_SIGMA = 0.4  # losowy dryf "pogodowy" temperatury (na krok czasowy)
TEMP_NOISE_REVERT = 0.02  # jak szybko dryf wraca do zera (unika trwałych ekstremów)

# szansa na rozpoczęcie opadu (na "sprawdzenie" - patrz WEATHER_CHECK_INTERVAL)
WEATHER_RAIN_CHANCE = {"Wiosna": 0.4, "Lato": 0.2, "Jesień": 0.5, "Zima": 0.0}
WEATHER_SNOW_CHANCE = {"Wiosna": 0.0, "Lato": 0.0, "Jesień": 0.05, "Zima": 0.55}
WEATHER_CHECK_INTERVAL = (60.0, 150.0)  # s - jak często losujemy zmianę pogody
WEATHER_DURATION = (40.0, 180.0)  # s - jak długo trwa epizod opadu

WIND_DRIFT_SIGMA = 0.05
WIND_REVERT = 0.15
WIND_MIN = 0.05
WIND_MAX = 1.0

RAIN_PARTICLE_COUNT = 140
SNOW_PARTICLE_COUNT = 110
DUST_PARTICLE_COUNT = 90

# szansa na rozpoczęcie suszy - trzeci, wykluczający się z deszczem/śniegiem
# stan pogody (patrz WEATHER_CHECK_INTERVAL). Częsta latem i w porze suchej,
# praktycznie nieobecna zimą.
WEATHER_DROUGHT_CHANCE = {"Wiosna": 0.05, "Lato": 0.35, "Jesień": 0.05, "Zima": 0.0}
WEATHER_DROUGHT_DURATION = (90.0, 240.0)  # s - susze trwają dłużej niż epizody opadów

# --- Zmienna jasność/długość dnia wg pory roku --------------------------------
# (średnia, amplituda) krzywej cosinusoidalnej dnia: zima = krótsze, ciemniejsze
# dni (niska średnia i amplituda), lato = dłuższe, jaśniejsze dni. Długość
# cyklu (DAY_LENGTH_SECONDS) zostaje stała - zmienia się tylko jego "kształt",
# żeby nie rozjechać innych stałych liczonych per sekundę.
SEASON_DAYLIGHT_PARAMS = {
    "Wiosna": (0.52, 0.48),
    "Lato": (0.62, 0.42),
    "Jesień": (0.50, 0.46),
    "Zima": (0.34, 0.30),
}

# --- Rodzaje mrówek --------------------------------------------------------
SPECIES = {
    "Rudnica leśna": dict(
        color=(150, 45, 30), speed=1.15, energy_cap=1.0, drain=1.05,
        strength=1.3, sense=1.0, native="Las",
    ),
    "Mrówka łąkowa": dict(
        color=(45, 32, 22), speed=1.0, energy_cap=1.1, drain=1.0,
        strength=1.0, sense=1.1, native="Łąka",
    ),
    "Mrówka pustynna": dict(
        color=(205, 172, 110), speed=1.35, energy_cap=0.85, drain=0.85,
        strength=0.8, sense=0.9, native="Pustynia",
    ),
}

NATIVE_BONUS_SPEED = 1.15
NATIVE_BONUS_DRAIN = 0.9

# --- Ewolucja cech mrówek ---------------------------------------------------
# nowa robotnica dziedziczy cechy losowej "rodzicielki" z obecnej populacji
# z niewielką mutacją - kolonia z czasem adaptuje się do warunków środowiska
EVO_MUTATION_SIGMA = 0.06  # ~6% losowa zmiana cechy na pokolenie
EVO_BOUNDS = {
    "speed_mult": (0.5, 2.2),
    "drain_mult": (0.45, 1.8),  # niżej = wydajniejszy metabolizm (lepiej)
    "strength": (0.3, 2.5),
    "sense_mult": (0.5, 2.0),
}

# --- Domyślne / graniczne wartości konfiguracji startowej -----------------
ANT_COUNT_DEFAULT, ANT_COUNT_MIN, ANT_COUNT_MAX, ANT_COUNT_STEP = 40, 5, 4000, 25
ANT_COUNT_COARSE_STEP = 250
MAX_POPULATION = 5000

COMPANIONS = {
    "Mszyce": dict(default=15, min=0, max=60, step=5),
    # populacja startowa < 4 jest demograficznie krucha (zbyt podatna na
    # przypadkowe wymarcie, zanim zdąży się rozmnożyć) - stąd wyższe minimum
    "Pająki": dict(default=4, min=0, max=8, step=1),
    "Biedronki": dict(default=5, min=0, max=20, step=1),
    "Osy": dict(default=3, min=0, max=10, step=1),
    "Chrząszcze": dict(default=6, min=0, max=20, step=1),
    "Dżdżownice": dict(default=8, min=0, max=25, step=1),
}

NEST_RADIUS = 26
SPAWN_FOOD_COST = 12
ANT_FEED_COST = 0.02
# rezerwa jedzenia (skalowana przez economy_scale) nietykalna przy zakupie
# nowych robotnic - bez niej kolonia potrafi wydać cały zapas na jednorazowy
# "boom" populacji, zostawiając 0 na regenerację energii już żyjących mrówek,
# co prowadzi do cyklu boom-bust i w długim (wielomiesięcznym) horyzoncie
# czasowym do nieodwracalnego wymarcia (wykryte testem balansu)
NEST_FOOD_RESERVE_BASE = 20.0
SPAWN_MAX_PER_TICK_BASE = 3  # maks. robotnic kupowanych jednorazowo, na jednostkę economy_scale

PHEROMONE_DEPOSIT = 255.0
PHEROMONE_EVAPORATION = 0.985  # mnożnik na klatkę
PHEROMONE_MAX = 255.0

ANT_BASE_SPEED = 55.0  # px / s
ANT_SENSOR_DIST = 20.0
ANT_SENSOR_ANGLE = 0.6  # rad
ANT_SIGHT_RADIUS = 42.0
ANT_THREAT_RADIUS = 22.0  # promień, w którym mrówka w ogóle reaguje na pająka (węższy niż wzrok - inaczej każdy przechodzień na szlaku "walczyłby")
ANT_TURN_NOISE = 0.35
ANT_ENERGY_MAX = 100.0
ANT_ENERGY_DRAIN = 3.2  # / s
ANT_ENERGY_REGEN = 18.0  # / s przy gnieździe

ANT_LOAD = 18.0  # jednostki jedzenia zabierane przy jednym kontakcie ze źródłem

# --- Rośliny (jedyne źródło jedzenia - rosną, mają ograniczony zapas) -----
PLANT_COUNT_BASE = 8
MAX_PLANTS = 60
PLANT_SEED_RADIUS = 4
PLANT_MATURE_RADIUS = 15
PLANT_SEED_SPREAD = (30, 90)  # promień rozsiewania nasion od rośliny-matki

# Kilka gatunków roślin o różnych cechach (analogicznie do SPECIES mrówek) -
# każdy biom ma swój preferowany, ale niewyłączny mix (patrz BIOMES[...]["plant_mix"]).
# frost_temp/frost_death_chance jak dawny PLANT_FROST_TEMP/_DEATH_CHANCE, ale per gatunek.
# drought_tolerance mnoży PLANT_DROUGHT_DEATH_CHANCE_BASE (niżej = bardziej odporny).
PLANT_SPECIES = {
    "Trawa łąkowa": dict(
        growth_time=18.0, stock_max=110.0, stock_rate=3.2,
        repro_min_stock=35.0, repro_chance=0.07, lifespan_range=(400.0, 900.0),
        frost_temp=-6.0, frost_death_chance=0.006, drought_tolerance=1.0,
        color=(100, 175, 70),
    ),
    "Jagodowiec leśny": dict(
        growth_time=34.0, stock_max=190.0, stock_rate=2.6,
        repro_min_stock=70.0, repro_chance=0.035, lifespan_range=(700.0, 1600.0),
        frost_temp=-4.0, frost_death_chance=0.009, drought_tolerance=1.3,
        color=(70, 130, 60),
    ),
    "Sukulent pustynny": dict(
        growth_time=50.0, stock_max=130.0, stock_rate=1.8,
        repro_min_stock=55.0, repro_chance=0.02, lifespan_range=(900.0, 2000.0),
        frost_temp=-2.0, frost_death_chance=0.02, drought_tolerance=0.12,
        color=(135, 160, 90),
    ),
}
PLANT_DROUGHT_DEATH_CHANCE_BASE = 0.004  # / s ekspozycji na suszę (mnożone przez drought_tolerance gatunku)

# --- Żyzność gleby: lokalny bonus per roślina, zasilany przez chrząszcze
# i dżdżownice, zanikający w czasie - prostsza alternatywa dla siatki na
# całą mapę, wystarczająca bo działa tylko lokalnie wokół roślin.
PLANT_FERTILITY_MAX = 0.6  # maks. mnożnik tempa wzrostu zapasu (+60%)
PLANT_FERTILITY_DECAY = 0.015  # / s, jak szybko bonus zanika bez podtrzymania

# --- Cykl dnia i nocy --------------------------------------------------------
DAY_NIGHT_MIN_ACTIVITY = 0.7  # mnożnik aktywności mrówek w pełni nocy
NIGHT_OVERLAY_MAX_ALPHA = 130

# --- Sterowanie upływem czasu -------------------------------------------------
SPEED_LEVELS = [1, 2, 5, 10, 20]

APHID_CLUSTER_SIZE = 3
APHID_MAX_PER_CLUSTER_BASE = 8
APHID_HONEYDEW_MAX = 150
APHID_HONEYDEW_RATE = 2.0  # / mrówka / s

SPIDER_HP = 9
SPIDER_SPEED = 70.0
SPIDER_HUNT_RADIUS = 190.0
SPIDER_ATTACK_RADIUS = 16.0
SPIDER_FLEE_ANTS = 3
SPIDER_ATTACK_COOLDOWN = 1.0
SPIDER_KILL_CHANCE = 0.25
# poniżej tej populacji mrówek drapieżnikom coraz trudniej upolować cokolwiek
# (rzadka, rozproszona zdobycz) - to jest to, co chroni kolonię przed
# nieodwracalnym wybiciem do zera
SPIDER_PREY_SATURATION = 90
SPIDER_ENERGY_MAX = 16.0
SPIDER_ENERGY_DRAIN = 0.035  # / s - głoduje bez upolowanej mrówki przez ~7-8 min
SPIDER_ENERGY_PER_KILL = 4.0
SPIDER_REPRO_THRESHOLD = 12.0
SPIDER_REPRO_COST = 7.0
SPIDER_REPRO_CHANCE = 0.04  # / s, gdy najedzony ponad prog
MAX_SPIDERS = 10

LADYBUG_SPEED = 45.0
LADYBUG_HUNT_RADIUS = 150.0
LADYBUG_EAT_COOLDOWN = 1.5
LADYBUG_ENERGY_MAX = 14.0
LADYBUG_ENERGY_DRAIN = 0.08  # / s - głoduje bez mszyc przez ~3 min
LADYBUG_ENERGY_PER_MEAL = 3.0
LADYBUG_REPRO_THRESHOLD = 8.0
LADYBUG_REPRO_COST = 5.0
LADYBUG_REPRO_CHANCE = 0.3  # / s, gdy najedzona ponad prog
MAX_LADYBUGS = 45

# --- Osy: drapieżnik generalistyczny - preferuje mszyce (tani posiłek),
# a gdy głodna i brak mszyc w zasięgu, poluje na pojedyncze mrówki jak pająk,
# tylko ze słabszą skutecznością (mniejszy, mniej wyspecjalizowany łowca) -----
WASP_HP = 5
WASP_SPEED = 85.0
WASP_APHID_HUNT_RADIUS = 220.0
WASP_ANT_HUNT_RADIUS = 90.0
WASP_EAT_COOLDOWN = 1.2
WASP_ATTACK_RADIUS = 14.0
WASP_ATTACK_COOLDOWN = 1.4
WASP_KILL_CHANCE = 0.07
WASP_FLEE_ANTS = 4
WASP_PREY_SATURATION = 90  # jak SPIDER_PREY_SATURATION - chroni kolonię przed wybiciem
WASP_ENERGY_MAX = 10.0
WASP_ENERGY_DRAIN = 0.05  # / s
WASP_ENERGY_PER_APHID = 1.2
WASP_ENERGY_PER_KILL = 3.0
# tylko naprawdę zdesperowana osa (blisko śmierci głodowej) poluje na mrówki -
# klastry mszyc są nieliczne na mapie, więc zbyt wysoki próg czyniłby z os
# w praktyce stałe, wszechobecne zagrożenie zamiast rzadkiego, ostatecznego
WASP_HUNGRY_THRESHOLD = 2.5
WASP_REPRO_THRESHOLD = 7.0
WASP_REPRO_COST = 4.0
WASP_REPRO_CHANCE = 0.05
MAX_WASPS = 12

# --- Chrząszcze padlinożerne: rozkładają truchła, lekko użyźniając okoliczne
# rośliny podczas żerowania - czyszczą mapę i domykają obieg materii -------
BEETLE_SPEED = 26.0
BEETLE_SENSE_RADIUS = 140.0
BEETLE_FEED_RATE = 3.0  # biomasy / s podczas żerowania
BEETLE_FERTILIZE_RADIUS = 50.0
BEETLE_FERTILIZE_AMOUNT = 0.05  # bonus żyzności / s dodawany pobliskim roślinom
BEETLE_ENERGY_MAX = 12.0
BEETLE_ENERGY_DRAIN = 0.025  # / s - wolny metabolizm
BEETLE_ENERGY_PER_BIOMASS = 0.15
BEETLE_REPRO_THRESHOLD = 9.0
BEETLE_REPRO_COST = 5.0
BEETLE_REPRO_CHANCE = 0.02
MAX_BEETLES = 20

# --- Dżdżownice: czysty mutualista, użyźniają glebę wokół rośliny, przy
# której przebywają - brak drapieżników, giną rzadko od mrozu/suszy ---------
EARTHWORM_SPEED = 10.0
EARTHWORM_SENSE_RADIUS = 90.0
EARTHWORM_FERTILIZE_RADIUS = 20.0
EARTHWORM_FERTILIZE_RATE = 0.03  # bonus żyzności / s gdy blisko rośliny
EARTHWORM_FROST_TEMP = -5.0
EARTHWORM_FROST_DEATH_CHANCE = 0.008  # / s ekspozycji
EARTHWORM_DROUGHT_DEATH_CHANCE = 0.01  # / s ekspozycji na suszę
EARTHWORM_REPRO_CHANCE = 0.01  # / s, gdy blisko dojrzałej rośliny
MAX_EARTHWORMS = 30

# --- Ptaki: drapieżnik szczytowy, NIE jest populacją startową z menu -
# pojawia się epizodycznie (jak pogoda), gdy populacja średnich drapieżników
# (pająki+osy+biedronki) urośnie za bardzo, i przerzedza ją, po czym odlatuje.
# To domyka pętlę kontroli populacji "od góry", tak jak SPIDER_PREY_SATURATION
# chroni mrówki "od dołu" ---------------------------------------------------
BIRD_TRIGGER_THRESHOLD = 16  # suma pająków+os+biedronek, powyżej której przylatuje stado
BIRD_COOLDOWN = (120.0, 240.0)  # s między możliwymi wizytami
BIRD_VISIT_DURATION = 30.0  # s - jak długo stado krąży nad mapą
BIRD_FLOCK_SIZE = (2, 5)
BIRD_SPEED = 130.0
BIRD_CATCH_RADIUS = 30.0
BIRD_CULL_CHANCE = 0.35  # szansa / s na upolowanie celu przez pojedynczego ptaka
MAX_CONCURRENT_BIRD_FLOCKS = 1

# --- Truchła: zostają po śmierci zwierzęcia, żywią się nimi chrząszcze,
# znikają same po czasie jeśli nikt ich nie zje -----------------------------
CORPSE_DECAY_TIME = 90.0  # s
CORPSE_BIOMASS = {"spider": 6.0, "wasp": 3.0, "ladybug": 2.5, "beetle": 3.0, "ant": 1.0}
MAX_CORPSES = 60

DAY_LENGTH_SECONDS = 45.0

# --- Mrówki-agenci Claude (agenci.py) -------------------------------------
# Kilka nazwanych mrówek, które co kilka sekund pytają model Claude, co robić.
# Koszt: przy 5 agentach i Haiku 5.5 ok. 1-2 zł za godzinę działania.
AGENT_COUNT_DEFAULT = 5
AGENT_COUNT_MAX = 8
AGENT_MODEL = "claude-haiku-5-5"
AGENT_PRICE_IN_PER_MTOK = 0.10  # USD za 1 mln tokenów wejścia (Haiku 5.5)
AGENT_PRICE_OUT_PER_MTOK = 0.50  # USD za 1 mln tokenów wyjścia
AGENT_EFFORT = "low"
AGENT_MAX_TOKENS = 1024
AGENT_DECISION_INTERVAL = 20.0  # s czasu rzeczywistego - najdłuższa przerwa między decyzjami
AGENT_MIN_GAP = 5.0  # s czasu rzeczywistego - najkrótsza przerwa między zapytaniami jednej mrówki
AGENT_VIEW_RADIUS = 220.0  # px - tyle mrówka "widzi" w opisie sytuacji
AGENT_SPEED_MULT = 1.15
AGENT_LOAD = 36.0  # agentka niesie 2x tyle co zwykła mrówka
AGENT_PHEROMONE = 900.0  # siła feromonu przy znakowaniu szlaku
AGENT_HIT_CHANCE = 1.2  # / s przy ataku (razy siła)
AGENT_DEATH_CHANCE = 0.25  # / s w zasięgu drapieżnika, gdy nie walczy
AGENT_DEATH_CHANCE_FIGHTING = 0.08  # / s w walce (dzielone przez siłę)
AGENT_RESPAWN_TIME = 60.0  # s symulacji do wyklucia następczyni
AGENT_RESPAWN_FOOD = 40.0
AGENT_MEMORY_NOTES = 6
AGENT_MEMORY_EVENTS = 10
AGENT_THOUGHT_SECONDS = 7.0
AGENT_INBOX_MAX = 4
AGENT_LOG_LINES = 40
AGENT_PANEL_MAX_LINES = 22

AGENT_PROFILES = [
    dict(imie="Zosia", rola="zwiadowczyni", kolor=(90, 200, 255), szybkosc=1.3,
         charakter="Jesteś ciekawska i odważna. Szukasz nowych źródeł jedzenia daleko od gniazda, "
                   "znakujesz do nich szlaki feromonem i mówisz innym, co znalazłaś."),
    dict(imie="Bogna", rola="żołnierka", kolor=(255, 95, 75), sila=2.5,
         charakter="Jesteś dzielna i opiekuńcza. Bronisz zbieraczek i gniazda przed pająkami i osami. "
                   "Atakujesz, gdy wróg jest blisko innych mrówek, ale nie szarżujesz na ślepo z małą energią."),
    dict(imie="Hela", rola="zbieraczka", kolor=(255, 210, 80),
         charakter="Jesteś pracowita i praktyczna. Nosisz jedzenie do gniazda, wybierasz bliskie, "
                   "obfite źródła i zostawiasz feromon, żeby rój poszedł za tobą."),
    dict(imie="Tekla", rola="opiekunka gniazda", kolor=(200, 140, 255),
         charakter="Jesteś rozważna i lubisz planować. Pilnujesz zapasów, trzymasz się blisko gniazda, "
                   "a gdy zapas maleje albo zbliża się zima, organizujesz innych wiadomościami."),
    dict(imie="Mela", rola="zwiadowczyni", kolor=(120, 255, 150), szybkosc=1.3,
         charakter="Jesteś ostrożna i spostrzegawcza. Badasz rzadko odwiedzane krańce mapy, "
                   "omijasz drapieżniki i ostrzegasz przed nimi innych."),
    dict(imie="Kinga", rola="żołnierka", kolor=(255, 150, 60), sila=2.5,
         charakter="Jesteś porywcza, ale lojalna. Patrolujesz okolice szlaków i odpowiadasz na wezwania o pomoc."),
    dict(imie="Ola", rola="zbieraczka", kolor=(255, 240, 140),
         charakter="Jesteś wesoła i gadatliwa. Zbierasz jedzenie i chętnie dzielisz się wieściami z innymi."),
    dict(imie="Frania", rola="zbieraczka", kolor=(170, 230, 255),
         charakter="Jesteś spokojna i wytrwała. Wolisz pewne, znane źródła jedzenia niż ryzyko."),
]

# --- Księga mrowiska (wspólna wiedza agentek, ksiega_mrowiska.json) ---------
BOOK_MAX_LESSONS = 25  # tyle lekcji trzyma plik; przy przepełnieniu wypada najsłabsza
BOOK_SHOWN = 12  # tyle najważniejszych lekcji trafia do opisu sytuacji agentki
