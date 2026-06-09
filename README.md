# Kalkulator Zaworów Dekompresyjnych — SM

Narzędzie inżynierskie do obliczania wymaganej liczby zaworów dekompresyjnych
w komorach mroźniczych zgodnie z wzorami branżowymi.

## Spis treści

- [Opis działania](#opis-działania)
- [Wzory obliczeniowe](#wzory-obliczeniowe)
- [Struktura projektu](#struktura-projektu)
- [Wymagania](#wymagania)
- [Instalacja](#instalacja)
- [Uruchomienie](#uruchomienie)
- [Interfejs użytkownika](#interfejs-użytkownika)
- [Eksport wyników](#eksport-wyników)
- [Testy](#testy)
- [Zmienne środowiskowe](#zmienne-środowiskowe)
- [Znane ograniczenia](#znane-ograniczenia)

---

## Opis działania

Program oblicza liczbę zaworów dekompresyjnych potrzebnych do wyrównania ciśnienia
w komorze mroźniczej wywołanego gwałtownym spadkiem temperatury (praca agregatu
chłodniczego). Wynik jest zaokrąglany w górę do pełnej liczby całkowitej.

---

## Wzory obliczeniowe

### Dynamika komory (°C/min)

$$
\Delta T = \frac{F}{V} \cdot \frac{T_{przed} - T_{za}}{60}
$$

### Wymagany przepływ powietrza (l/min)

$$
Q = K \cdot V \cdot \Delta T
$$

Gdzie:
| Symbol | Opis | Wartość domyślna |
|--------|------|-----------------|
| `V` | Objętość komory [m³] | — |
| `F` | Całkowity przepływ przez chłodnice [m³/h] | — |
| `T_przed` | Temperatura przed wlotem chłodnicy [°C] | — |
| `T_za` | Temperatura za wlotem chłodnicy [°C] | — |
| `K` | Stała obliczeniowa | `3.66` |

### Liczba zaworów

$$
n = \left\lceil \frac{Q}{Q_{zaworu}} \right\rceil
$$

| Typ zaworu | Przepływ [l/min] |
|-----------|-----------------|
| Maxi Elebar (ścienny) | 4 300 |
| Maxi Elebar EVO-VERTICAL (stropowy) | 1 430 |

---

## Struktura projektu

```
zawory dekompresyjne/
│
├── obliczenia.py          # Rdzeń obliczeń (czysta logika, bez GUI)
├── gui.py                 # Aplikacja GUI (ttkbootstrap/Tkinter)
├── validation.py          # Parsowanie i walidacja danych wejściowych
├── pdf_service.py         # Generowanie i szyfrowanie pliku PDF
├── resources/             # Czcionka i watermark używane w PDF / buildzie
├── test_obliczenia.py     # Testy jednostkowe silnika obliczeń (pytest)
├── test_validation.py     # Testy jednostkowe parsowania wejścia (pytest)
├── test_pdf_service.py    # Testy generowania i szyfrowania PDF
├── requirements.txt       # Zależności Pythona
├── __init__.py            # Marker pakietu (pusty)
└── README.md              # Niniejsza dokumentacja
```

---

## Wymagania

- **Python** 3.10 lub nowszy
- Czcionka **DejaVuSans** (TTF) — domyślnie w `resources/DejaVuSans.ttf`
- *(opcjonalnie)* Logo/watermark TIFF/PNG — domyślnie w `resources/PUCH.TIF`

### Pakiety Python

```
ttkbootstrap>=1.10,<2.0
reportlab>=4.0,<5.0
pypdf[crypto]>=4.0,<6.0   # [crypto] dodaje cryptography dla AES-256
pytest>=7.0,<9.0          # tylko do uruchamiania testów
```

> Uwaga: `pypdf` zastąpił przestarzały `PyPDF2`. Pakiet `cryptography` jest
> wymagany do szyfrowania AES-256 — instaluje się automatycznie z `pypdf[crypto]`.

---

## Instalacja

```bash
# 1. Sklonuj / skopiuj projekt do wybranego katalogu

# 2. Utwórz środowisko wirtualne (zalecane)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# 3. Zainstaluj zależności
pip install -r requirements.txt
```

---

## Uruchomienie

```bash
python gui.py
```

Aplikacja otworzy okno kalkulatora. Wszystkie obliczenia wykonywane są natychmiast
po kliknięciu przycisku „Oblicz" lub wciśnięciu **Enter**.

---

## Interfejs użytkownika

### Skróty klawiszowe

| Skrót | Akcja |
|-------|-------|
| `Enter` / `KP_Enter` | Oblicz |
| `Ctrl+S` | Generuj PDF |
| `Escape` | Wyczyść wyniki |

### Zakładki wyników

- **Bieżące** — wynik ostatniego obliczenia z graficznym wskaźnikiem (Meter)
- **Historia** — tabela wszystkich obliczeń z bieżącej sesji;
  dwukrotne kliknięcie wiersza przywraca wynik

---

## Eksport wyników

| Format | Przycisk | Opis |
|--------|----------|------|
| **PDF** | „Generuj PDF" / `Ctrl+S` | Raport z tytułem, tabelą wyników, numeracją stron i znakiem wodnym. Plik jest chroniony hasłem właściciela (blokada edycji). |
| **CSV** | „Eksport CSV" | Historia wszystkich obliczeń z bieżącej sesji (separator `;`, kodowanie UTF-8 BOM). |

> **Uwaga:** Hasło właściciela PDF jest pobierane ze zmiennej środowiskowej
> `PDF_OWNER_PASSWORD`. Jeśli zmienna nie jest ustawiona, program wyświetli
> ostrzeżenie i umożliwi kontynuację. Nie należy hardkodować hasła w kodzie.

---

## Testy

```bash
python -m pytest -v
```

Testy obejmują:
- Poprawne obliczenia dla obu typów zaworów (w tym skrajne przypadki)
- Błędy walidacji: ujemna lub zerowa objętość, zerowy lub ujemny przepływ, temperatury > 0, równe temperatury
- Nieznany typ zaworu → `KeyError`
- Niemutowalność (`frozen=True`) dataclassy `CalculationResult`
- Parsowanie wejścia: separator przecinkowy, spacje, wartości ujemne, błędne dane (`test_validation.py`)

---

## Zmienne środowiskowe

| Zmienna | Opis | Wymagana |
|---------|------|---------|
| `PDF_OWNER_PASSWORD` | Hasło właściciela generowanego pliku PDF (chroni przed edycją, nie przed otwarciem) | Zalecana — program ostrzega przy braku |

Przykład ustawienia (Windows):
```powershell
$env:PDF_OWNER_PASSWORD = "MojeBezpieczneHaslo2026"
python gui.py
```

---

## Metodologia obliczeń — uwaga bezpieczeństwa

Karta doboru producenta w przykładzie **zaokrągla Δt w dół do 2 miejsc po przecinku**
(np. 0,9778 → 0,97), co systematycznie zaniża wymagany przepływ Q i może dawać
o jeden zawór mniej. Program liczy **bez zaokrąglania pośredniego** — wynik
końcowy `math.ceil()` zapewnia minimalny margines bezpieczeństwa. Dla przykładu
z karty producenta (V=1200, F=32000, DT1=2,2) program poda **4 zawory EVO** zamiast 3.

To świadoma decyzja: w aplikacji wyrównywania ciśnienia lepiej przewymiarować
niż niedomiarować.

## Znane ograniczenia

1. **Czcionka PDF** — program szuka `DejaVuSans.ttf` najpierw w `resources/` obok
   modułu, potem pod oryginalną ścieżką `../TPOF/...`. Brak czcionki → fallback do
   Helvetica (niepełna obsługa polskich znaków).
2. **Historia nietrwała** — lista obliczeń istnieje tylko przez czas sesji; limit
   500 wpisów (FIFO). Ostatnie wejścia są automatycznie zapisywane do `last_inputs.json`
   w katalogu użytkownika (`%APPDATA%/MDPuch/ZaworyDekompresyjne/` na Windows).
3. **Log** — `kalkulator.log` w katalogu danych użytkownika z rotacją (3 × 1 MB).
4. **Temperatury różne i temp_przed > temp_za** — wymagane. Dopuszczalne są
   również temperatury dodatnie (np. chłodnie nabiału/mięsa).

---

*Autor: Sebastian Milczarek
