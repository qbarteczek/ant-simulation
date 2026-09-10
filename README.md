# Symulacja mrowiska

Wektorowa (numpy) symulacja życia kolonii mrówek: szukanie jedzenia po śladach
feromonowych, ograniczone rośliny jako jedyne źródło pożywienia, prosty łańcuch
pokarmowy (mszyce / pająki / biedronki), pogoda (deszcz, śnieg, wiatr, cykl
dnia i nocy) oraz ewolucja cech mrówek w kolejnych pokoleniach.

## ▶ Zagraj w przeglądarce

**[qbarteczek.github.io/ant-simulation](https://qbarteczek.github.io/ant-simulation/)**

Działa od razu w przeglądarce (desktop i mobile), bez instalowania czegokolwiek —
niezależnie od systemu operacyjnego. Strona buduje się automatycznie z gałęzi
`master` (patrz `.github/workflows/deploy-web.yml`), więc zawsze odpowiada
najnowszej wersji w repozytorium.

Wersja przeglądarkowa bywa wolniejsza niż lokalna (WebAssembly), zwłaszcza przy
bardzo dużych koloniach — do intensywnego eksperymentowania lepsza jest wersja
lokalna poniżej.

## Sterowanie

| Klawisz / mysz | Akcja |
|---|---|
| Spacja | pauza |
| `+` / `-` | prędkość symulacji (x1…x20) |
| Esc | powrót do menu |
| `R` | restart z tym samym ustawieniem |
| LPM | zasadź roślinę w danym miejscu |
| PPM | postaw przeszkodę |

## Uruchomienie lokalne

Wymaga Pythona 3.10+, `pygame` (lub `pygame-ce`) i `numpy`.

**Linux/macOS:**
```sh
./uruchom.sh
```
(sam tworzy `venv` i instaluje zależności przy pierwszym uruchomieniu)

**Windows / ręcznie:**
```
pip install pygame numpy
python main.py
```

## Rozwój

Pętla główna (`main.py`) jest asynchroniczna (`async`/`await`), żeby ten sam
kod działał natywnie i w przeglądarce przez [pygbag](https://github.com/pygame-web/pygbag)
(kompilacja do WebAssembly). Build lokalny bez wypychania na Pages:

```
pip install pygbag
python -m pygbag --build .
```
Wynik trafia do `build/web/index.html`.
