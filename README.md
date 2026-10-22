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

## Mrówki-agenci Claude

Oprócz zwykłego roju po mapie chodzi kilka nazwanych mrówek (Zosia, Bogna,
Hela, Tekla, Mela...), które myślą modelem Claude. Każda ma rolę
(zwiadowczyni, żołnierka, zbieraczka, opiekunka gniazda), własną pamięć
i co kilka sekund dostaje opis tego, co widzi: jedzenie, pająki i osy,
zapas w gnieździe, inne agentki, wiadomości. Odpowiada decyzją: dokąd iść,
co zrobić (zbierać, wracać, atakować, uciekać, zwiadować, odpoczywać),
czy znakować drogę feromonem, za którym pójdzie rój, co powiedzieć
innym i co zapamiętać. Myśli widać w dymkach, rozmowy w panelu po prawej
(`Tab` go chowa). Zabita agentka po chwili wykluwa się na nowo.

Liczbę agentek (0-8) ustawia się w menu. Do działania potrzebny jest klucz
API Anthropic: zmienna `ANTHROPIC_API_KEY` albo plik `klucz_api.txt` obok
`main.py` (jest w `.gitignore`). Bez klucza i w wersji przeglądarkowej
agentki chodzą na prostym autopilocie.

Model i tempo decyzji ustawia się w `config.py` (`AGENT_*`). Domyślnie
`claude-haiku-5-5`: 5 agentek to ok. 30 zapytań na minutę, czyli ok. 1 USD
na godzinę. Licznik zapytań i kosztu jest w HUD.

### Księga mrowiska

Kolonia się uczy. Po ważnym zdarzeniu (śmierć towarzyszki, pokonany pająk,
pusty spichlerz, wyczerpanie) agentka zastanawia się, czego to uczy, i może
zapisać ogólną lekcję w Księdze mrowiska. Inne agentki ją czytają, a gdy
lekcja się sprawdzi, potwierdzają ją (każda raz na grę) - ważniejsze lekcje
są wyżej. Księga trafia do pliku `ksiega_mrowiska.json` (poza gitem), więc
każda następna kolonia zaczyna z wiedzą poprzednich. Przy pełnej Księdze
(25 lekcji) wypada najsłabsza. Następczyni zabitej agentki dziedziczy też jej
notatki o bieżącej mapie. Usunięcie pliku zaczyna naukę od zera.

## Sterowanie

| Klawisz / mysz | Akcja |
|---|---|
| Spacja | pauza |
| `+` / `-` | prędkość symulacji (x1…x20) |
| Esc | powrót do menu |
| `R` | restart z tym samym ustawieniem |
| `Tab` | pokaż/ukryj panel mrówek-agentów |
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
pip install -r requirements.txt
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
