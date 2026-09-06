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
    ),
    "Las": dict(
        bg=(53, 82, 44),
        bg2=(45, 71, 37),
        obstacle_color=(75, 55, 35),
        obstacle_density=20,
        food_density=0.75,
        food_regen=0.9,
        obstacle_shape="log",
    ),
    "Pustynia": dict(
        bg=(226, 201, 143),
        bg2=(214, 187, 125),
        obstacle_color=(178, 148, 96),
        obstacle_density=6,
        food_density=0.5,
        food_regen=0.6,
        obstacle_shape="rock",
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
}

NEST_RADIUS = 26
SPAWN_FOOD_COST = 12
ANT_FEED_COST = 0.02

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
PLANT_GROWTH_TIME = 25.0  # s do dojrzałości w pełnym świetle dnia
PLANT_SEED_RADIUS = 4
PLANT_MATURE_RADIUS = 15
PLANT_STOCK_MAX = 140.0  # twardy limit zapasu jedzenia na roślinę
PLANT_STOCK_RATE = 3.0  # / s, dojrzała roślina w pełnym świetle dnia
PLANT_REPRO_MIN_STOCK = 45.0
PLANT_REPRO_CHANCE = 0.05  # / s, gdy dojrzała i ma zapas ponad prog
PLANT_SEED_SPREAD = (30, 90)  # promień rozsiewania nasion od rośliny-matki
PLANT_LIFESPAN_RANGE = (500.0, 1400.0)  # s - roślina starzeje się i usycha
PLANT_FROST_TEMP = -8.0  # °C - poniżej tego roślina może przemarznąć
PLANT_FROST_DEATH_CHANCE = 0.005  # / s ekspozycji na mróz poniżej progu (rzadkie przemarznięcia, nie masowa zagłada)

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

DAY_LENGTH_SECONDS = 45.0
