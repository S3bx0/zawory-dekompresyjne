import ttkbootstrap as ttk
from ttkbootstrap.constants import INFO, INVERSE, SUCCESS
from ttkbootstrap.widgets import ToolTip, ToastNotification
from tkinter import messagebox, filedialog
import obliczenia
import pdf_service
import validation
import csv
import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import pathlib
import tkinter as tk
import subprocess
import sys


def _user_data_dir() -> pathlib.Path:
    """Zwraca katalog danych użytkownika (Windows: %APPDATA%, inne: ~/.config)."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    path = pathlib.Path(base) / "MDPuch" / "ZaworyDekompresyjne"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        path = pathlib.Path(__file__).resolve().parent  # fallback
    return path


# ── Logger (rotacja do 3 × 1 MB) ───────────────────────────────────────────
_BASE_DIR = pathlib.Path(__file__).resolve().parent
_USER_DIR = _user_data_dir()
_LOG_FILE = _USER_DIR / "kalkulator.log"
_logger = logging.getLogger(__name__)
_fh = RotatingFileHandler(
    str(_LOG_FILE), encoding="utf-8",
    maxBytes=1_000_000, backupCount=3,
)
_fh.setLevel(logging.ERROR)
_fh.setFormatter(logging.Formatter(
    "%(asctime)s  %(levelname)-8s  %(name)s: %(message)s"
))
_logger.addHandler(_fh)
_logger.setLevel(logging.ERROR)
_logger.propagate = False

# Plik z ostatnio użytymi danymi wejściowymi (katalog danych użytkownika)
_LAST_INPUTS_FILE = _USER_DIR / "last_inputs.json"
# Limit sesji historii (zapobiega nieograniczonemu wzrostowi pamięci)
_HISTORY_LIMIT = 500


class DecompressionValveCalculatorApp:
    # ── Stałe kolorów ──────────────────────────────────────
    _CLR_HEADER_BG = "#2c3e50"
    _CLR_HEADER_FG = "#ecf0f1"
    _CLR_FOOTER_BG = "#ecf0f1"
    _CLR_FOOTER_FG = "#7f8c8d"
    _CLR_RESULT_BG = "#f0faf0"
    _CLR_RESULT_FG = "#2c3e50"
    _CLR_ACCENT = "#27ae60"

    def __init__(self, master):
        self.master = master
        self._history: list[dict] = []
        # Snapshot ostatniego poprawnego wyniku — używany przy eksporcie PDF
        self._last_result_text: str = ""
        # Pełny snapshot (CalculationResult + wejścia) do generatora PDF
        self._last_snapshot: dict | None = None

        # ── Zmienne ────────────────────────────────────────
        self.wybor_kubatury_var = tk.StringVar(value="K")
        self.objetosc_var = tk.StringVar()
        self.dlugosc_var = tk.StringVar()
        self.szerokosc_var = tk.StringVar()
        self.wysokosc_var = tk.StringVar()
        self.temp_przed_var = tk.StringVar()
        self.temp_za_var = tk.StringVar()
        self.ilosc_chlodnic_var = tk.StringVar()
        self.przeplyw_powietrza_var = tk.StringVar()
        self.typ_zaworu_var = tk.StringVar(value="Maxi Elebar")

        # ── Layout główny ──────────────────────────────────
        master.columnconfigure(0, weight=1)
        master.rowconfigure(1, weight=0)  # inputs
        master.rowconfigure(2, weight=1)  # results (rozciągalne)

        self._create_header()
        self._create_input_frame()
        self._create_output_frame()
        self._create_footer()
        self._bind_shortcuts()
        self._load_last_inputs()

    # ── Nagłówek ───────────────────────────────────────────
    def _create_header(self):
        header = tk.Frame(self.master, bg=self._CLR_HEADER_BG, height=56)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.columnconfigure(0, weight=1)

        title_lbl = tk.Label(
            header,
            text="❄  Kalkulator Zaworów Dekompresyjnych",
            font=("Segoe UI", 14, "bold"),
            bg=self._CLR_HEADER_BG,
            fg=self._CLR_HEADER_FG,
            anchor="center",
        )
        title_lbl.grid(row=0, column=0, pady=12, padx=16, sticky="ew")

    # ── Ramka danych wejściowych ───────────────────────────
    def _create_input_frame(self):
        PAD = {"padx": 8, "pady": 4}

        input_frame = ttk.LabelFrame(self.master, text="  Dane wejściowe  ")
        input_frame.grid(row=1, column=0, padx=12, pady=(8, 4), sticky="new")
        input_frame.columnconfigure(1, weight=1)

        # ─ Radiobuttons kubatura / wymiary ─
        radio_frame = ttk.Frame(input_frame)
        radio_frame.grid(row=0, column=0, columnspan=2, sticky="w", **PAD)

        ttk.Radiobutton(
            radio_frame, text="Kubatura", variable=self.wybor_kubatury_var, value="K",
            bootstyle="info-toolbutton",
        ).pack(side="left", padx=(0, 4))
        ttk.Radiobutton(
            radio_frame, text="Wymiary", variable=self.wybor_kubatury_var, value="W",
            bootstyle="info-toolbutton",
        ).pack(side="left")

        # ─ Pola kubatury / wymiarów ─
        row = 1
        self.objetosc_entry = self._add_field(input_frame, row, "Objętość [m³]:", self.objetosc_var, "Podaj objętość komory w m³")
        row += 1
        self.dlugosc_entry = self._add_field(input_frame, row, "Długość [m]:", self.dlugosc_var, "Podaj długość komory w m")
        row += 1
        self.szerokosc_entry = self._add_field(input_frame, row, "Szerokość [m]:", self.szerokosc_var, "Podaj szerokość komory w m")
        row += 1
        self.wysokosc_entry = self._add_field(input_frame, row, "Wysokość [m]:", self.wysokosc_var, "Podaj wysokość komory w m")

        self.wybor_kubatury_var.trace_add("write", self._toggle_kubatura_fields)
        self._toggle_kubatura_fields()

        # ─ Separator ─
        row += 1
        ttk.Separator(input_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=6, padx=8
        )

        # ─ Temperatury ─
        row += 1
        self.temp_przed_entry = self._add_field(
            input_frame, row, "Temp. przed wlotem [°C]:", self.temp_przed_var,
            "Temperatura powietrza przed wlotem chłodnicy"
        )
        row += 1
        self.temp_za_entry = self._add_field(
            input_frame, row, "Temp. za wlotem [°C]:", self.temp_za_var,
            "Temperatura powietrza za wlotem chłodnicy"
        )

        # ─ Separator ─
        row += 1
        ttk.Separator(input_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=6, padx=8
        )

        # ─ Chłodnice / przepływ ─
        row += 1
        self.ilosc_chlodnic_entry = self._add_field(
            input_frame, row, "Ilość chłodnic:", self.ilosc_chlodnic_var, "Ilość chłodnic w komorze"
        )
        row += 1
        self.przeplyw_powietrza_entry = self._add_field(
            input_frame, row, "Przepływ na 1 chłodnicę [m³/h]:", self.przeplyw_powietrza_var,
            "Przepływ powietrza przez POJEDYNCZĄ chłodnicę.\n"
            "Program pomnoży tę wartość przez liczbę chłodnic (F = przepływ × n)."
        )

        # ─ Typ zaworu ─
        row += 1
        ttk.Label(input_frame, text="Typ zaworu:").grid(row=row, column=0, sticky="w", **PAD)
        self.typ_zaworu_combo = ttk.Combobox(
            input_frame,
            textvariable=self.typ_zaworu_var,
            values=list(obliczenia.ZAWORY.keys()),
            state="readonly",
        )
        self.typ_zaworu_combo.grid(row=row, column=1, sticky="ew", **PAD)
        ToolTip(
            self.typ_zaworu_combo,
            text="Maxi Elebar — stropowy 4300 l/min\n"
                 "Maxi Elebar EVO-VERTICAL — stropowy 1430 l/min",
            bootstyle=(INFO, INVERSE),
        )

        # ─ Przyciski ─
        row += 1
        btn_frame = ttk.Frame(input_frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(10, 8))

        self._btn_oblicz = ttk.Button(
            btn_frame, text="  ▶  Oblicz  ", command=self.calculate,
            bootstyle="success", width=18,
        )
        self._btn_oblicz.pack(side="left", padx=4)

        self._btn_pdf = ttk.Button(
            btn_frame, text="  📄  Generuj PDF  ", command=self.generate_pdf,
            bootstyle="info", width=18,
        )
        self._btn_pdf.pack(side="left", padx=4)

        ToolTip(self._btn_oblicz, text="Wykonaj obliczenia  (Enter)", bootstyle=(SUCCESS, INVERSE))
        ToolTip(self._btn_pdf, text="Zapisz wyniki do pliku PDF", bootstyle=(INFO, INVERSE))

    # ── Ramka wyników ──────────────────────────────────────
    def _create_output_frame(self):
        output_frame = ttk.LabelFrame(self.master, text="  Wyniki  ")
        output_frame.grid(row=2, column=0, padx=12, pady=(4, 4), sticky="nsew")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        # ─ Notebook z zakładkami ─
        self._notebook = ttk.Notebook(output_frame)
        self._notebook.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # ── Tab 1: Bieżące wyniki ─────────────────────────
        current_tab = ttk.Frame(self._notebook)
        self._notebook.add(current_tab, text=" 📊 Bieżące ")
        current_tab.columnconfigure(0, weight=1)
        current_tab.rowconfigure(0, weight=1)

        # ─ Główny kontener wyników (text + meter obok siebie) ─
        result_container = ttk.Frame(current_tab)
        result_container.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        result_container.columnconfigure(0, weight=1)
        result_container.rowconfigure(0, weight=1)

        # ─ Text widget + scrollbar (lewo) ─
        text_frame = ttk.Frame(result_container)
        text_frame.grid(row=0, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.results_text = tk.Text(
            text_frame,
            height=10,
            width=36,
            state="disabled",
            font=("Consolas", 10),
            bg=self._CLR_RESULT_BG,
            fg=self._CLR_RESULT_FG,
            relief="flat",
            wrap="word",
            borderwidth=0,
            highlightthickness=1,
            highlightcolor=self._CLR_ACCENT,
            highlightbackground="#d5d8dc",
        )
        self.results_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.results_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.results_text.config(yscrollcommand=scrollbar.set)

        # ─ Meter (prawo) — wskaźnik ilości zaworów ─
        self.valve_meter = ttk.Meter(
            result_container,
            metersize=160,
            amountused=0,
            amounttotal=20,
            metertype="semi",
            subtext="zaworów",
            textright="szt",
            bootstyle="success",
            meterthickness=12,
            stripethickness=4,
            interactive=False,
            subtextfont="-size 9",
            textfont="-size 22 -weight bold",
        )
        self.valve_meter.grid(row=0, column=1, padx=(10, 4), pady=4, sticky="n")
        ToolTip(self.valve_meter, text="Obliczona ilość zaworów", bootstyle=(SUCCESS, INVERSE))

        # ── Tab 2: Historia ────────────────────────────────
        history_tab = ttk.Frame(self._notebook)
        self._notebook.add(history_tab, text=" 📋 Historia (0) ")
        history_tab.columnconfigure(0, weight=1)
        history_tab.rowconfigure(0, weight=1)

        columns = ("nr", "V", "dT", "Q", "zawory", "typ", "czas")
        self._history_tree = ttk.Treeview(
            history_tab, columns=columns, show="headings", height=8,
        )
        for col, heading, width in [
            ("nr", "#", 30), ("V", "V [m³]", 70), ("dT", "ΔT", 60),
            ("Q", "Q [l/min]", 80), ("zawory", "Szt.", 40),
            ("typ", "Typ zaworu", 140), ("czas", "Czas", 70),
        ]:
            self._history_tree.heading(col, text=heading)
            self._history_tree.column(col, width=width, anchor="center")
        self._history_tree.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        hist_scroll = ttk.Scrollbar(history_tab, orient="vertical", command=self._history_tree.yview)
        hist_scroll.grid(row=0, column=1, sticky="ns")
        self._history_tree.configure(yscrollcommand=hist_scroll.set)
        self._history_tree.bind("<Double-1>", self._on_history_select)
        ToolTip(self._history_tree, text="Kliknij dwukrotnie aby przywrócić wyniki", bootstyle=(INFO, INVERSE))

        # ─ Przyciski pod zakładkami ─
        btn_bar = ttk.Frame(output_frame)
        btn_bar.grid(row=1, column=0, pady=(0, 8))

        copy_btn = ttk.Button(
            btn_bar, text="  📋  Kopiuj wyniki  ", command=self.copy_results,
            bootstyle="secondary-outline", width=18,
        )
        copy_btn.pack(side="left", padx=4)

        self._btn_clear = ttk.Button(
            btn_bar, text="  🗑  Wyczyść  ", command=self._clear_results,
            bootstyle="danger-outline", width=14,
        )
        self._btn_clear.pack(side="left", padx=4)

        self._btn_csv = ttk.Button(
            btn_bar, text="  📊  Eksport CSV  ", command=self._export_csv,
            bootstyle="info-outline", width=16,
        )
        self._btn_csv.pack(side="left", padx=4)
        ToolTip(self._btn_csv, text="Eksportuj historię obliczeń do CSV", bootstyle=(INFO, INVERSE))

    # ── Stopka z autorem + statusbar + sizegrip ────────────
    def _create_footer(self):
        footer = ttk.Frame(self.master)
        footer.grid(row=3, column=0, sticky="ew", padx=0, pady=0)
        footer.columnconfigure(1, weight=1)

        # Status bar (lewo)
        self._status_var = tk.StringVar(value="Gotowy")
        status_lbl = ttk.Label(
            footer,
            textvariable=self._status_var,
            font=("Segoe UI", 8),
            foreground=self._CLR_FOOTER_FG,
            anchor="w",
        )
        status_lbl.grid(row=0, column=0, padx=10, pady=4, sticky="w")

        # Autor (środek)
        ttk.Label(
            footer,
            text="Sebastian Milczarek  ·  MD-Puch Sp. z o.o.",
            font=("Segoe UI", 8),
            foreground=self._CLR_FOOTER_FG,
            anchor="center",
        ).grid(row=0, column=1, pady=4, sticky="ew")

        # Sizegrip (prawy dół)
        ttk.Sizegrip(footer, bootstyle="default").grid(row=0, column=2, sticky="se")

    # ── Helper: dodaj pole z ToolTip ───────────────────────
    def _add_field(self, parent, row, label_text, var, tooltip_text):
        PAD = {"padx": 8, "pady": 4}
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky="w", **PAD)
        entry = ttk.Entry(parent, textvariable=var)
        entry.grid(row=row, column=1, sticky="ew", **PAD)
        ToolTip(entry, text=tooltip_text, bootstyle=(INFO, INVERSE))
        return entry

    # ── Skróty klawiszowe ──────────────────────────────────
    def _bind_shortcuts(self):
        self.master.bind("<Return>", lambda e: self.calculate())
        self.master.bind("<KP_Enter>", lambda e: self.calculate())
        self.master.bind("<Escape>", lambda e: self._clear_results())
        self.master.bind("<Control-s>", lambda e: self.generate_pdf())
        self.master.bind("<Control-S>", lambda e: self.generate_pdf())

    # ── Wyczyść wyniki ─────────────────────────────────────
    def _clear_results(self):
        self.results_text.config(state="normal")
        self.results_text.delete(1.0, tk.END)
        self.results_text.config(state="disabled")
        self.valve_meter.configure(amountused=0)
        self._set_status("Wyczyszczono")

    # ── Statusbar helper ───────────────────────────────────
    def _set_status(self, text):
        self._status_var.set(text)

    # ── Toast helper ───────────────────────────────────────
    def _toast(self, title, message, bootstyle="success", duration=2500):
        toast = ToastNotification(
            title=title,
            message=message,
            duration=duration,
            bootstyle=bootstyle,
            position=(10, 10, "se"),
        )
        toast.show_toast()

    def _toggle_kubatura_fields(self, *args):
        if self.wybor_kubatury_var.get() == "K":
            self.objetosc_entry.config(state="normal")
            self.dlugosc_entry.config(state="disabled")
            self.szerokosc_entry.config(state="disabled")
            self.wysokosc_entry.config(state="disabled")
        else:
            self.objetosc_entry.config(state="disabled")
            self.dlugosc_entry.config(state="normal")
            self.szerokosc_entry.config(state="normal")
            self.wysokosc_entry.config(state="normal")

    @staticmethod
    def _parse_float(value):
        return validation.parse_float(value)

    @staticmethod
    def _parse_int(value):
        return validation.parse_int(value)

    def _require_numeric(self, var, field_name, parser=None, errors=None):
        """Waliduje i parsuje wartość z pola.

        Zwraca liczbę lub None. Komunikaty błędów dopisuje do listy ``errors``
        (jeśli podana), zamiast wyświetlać messagebox natychmiast.
        """
        if parser is None:
            parser = self._parse_float
        val = var.get().strip()
        if not val:
            msg = f"Podaj {field_name}."
            if errors is not None:
                errors.append(msg)
            else:
                messagebox.showerror("Błąd", msg)
            return None
        try:
            return parser(val)
        except ValueError:
            msg = f"{field_name} — nieprawidłowa wartość."
            if errors is not None:
                errors.append(msg)
            else:
                messagebox.showerror("Błąd", msg)
            return None

    def _get_validated_inputs(self):
        """Waliduje pola i zwraca słownik sparsowanych wartości lub None.

        Wszystkie wykryte błędy są kumulowane i prezentowane w jednym dialogu.
        """
        errors: list[str] = []

        if self.wybor_kubatury_var.get() == "K":
            V = self._require_numeric(self.objetosc_var, "objętość", errors=errors)
        else:
            d = self._require_numeric(self.dlugosc_var, "długość", errors=errors)
            s = self._require_numeric(self.szerokosc_var, "szerokość", errors=errors)
            w = self._require_numeric(self.wysokosc_var, "wysokość", errors=errors)
            V = (d * s * w) if None not in (d, s, w) else None

        tp = self._require_numeric(self.temp_przed_var, "temperatura przed wlotem", errors=errors)
        tz = self._require_numeric(self.temp_za_var, "temperatura za wlotem", errors=errors)
        ic = self._require_numeric(
            self.ilosc_chlodnic_var, "ilość chłodnic", self._parse_int, errors=errors
        )
        if ic is not None and ic < 1:
            errors.append("Ilość chłodnic musi być co najmniej 1.")
            ic = None
        F = self._require_numeric(self.przeplyw_powietrza_var, "przepływ powietrza", errors=errors)
        if F is not None and F <= 0:
            errors.append("Przepływ powietrza musi być większy od zera.")
            F = None

        if errors:
            bullets = "\n".join(f"•  {e}" for e in errors)
            messagebox.showerror(
                "Popraw dane wejściowe",
                f"Znaleziono {len(errors)} problem(y/ów):\n\n{bullets}",
            )
            return None

        return {
            "V": V,
            "temp_przed": tp,
            "temp_za": tz,
            "ilosc_chlodnic": ic,
            "F": F,
            "typ_zaworu": self.typ_zaworu_var.get(),
        }

    def calculate(self):
        inputs = self._get_validated_inputs()
        if inputs is None:
            return
        try:
            V = inputs["V"]
            temp_przed = inputs["temp_przed"]
            temp_za = inputs["temp_za"]
            ilosc_chlodnic = inputs["ilosc_chlodnic"]
            F = inputs["F"]
            typ_zaworu = inputs["typ_zaworu"]

            # Poprawka: mnożenie F przez liczbę chłodnic
            F_total = F * ilosc_chlodnic

            # Obliczenia
            result = obliczenia.calculate_decompression_valves(
                V, temp_przed, temp_za, F_total, typ_zaworu
            )

            # Wyświetlenie wyników
            results_str = (
                f"V = {V:.2f} m³\n"
                f"Temperatura przed chłodnicą = {temp_przed:.2f} °C\n"
                f"Temperatura za chłodnicą = {temp_za:.2f} °C\n"
                f"Ilość chłodnic = {ilosc_chlodnic}\n"
                f"F = {F_total:.2f} m³/h (przepływ całkowity)\n"
                f"ΔT = {result.delta_T:.2f} °C/min\n"
                f"Q = {result.Q:.2f} l/min\n"
                f"Zawór: {typ_zaworu} ({result.przeplyw_zaworu} l/min)\n"
                f"Ilość potrzebnych zaworów = {result.ilosc_zaworow} {typ_zaworu}"
            )

            self.results_text.config(state="normal")
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, results_str)
            self.results_text.config(state="disabled")
            self._last_result_text = results_str

            # Aktualizacja Metera
            valve_count = result.ilosc_zaworow
            meter_max = max(20, valve_count + 2)
            self.valve_meter.configure(amounttotal=meter_max, amountused=valve_count)

            if valve_count <= 5:
                self.valve_meter.configure(bootstyle="success")
            elif valve_count <= 12:
                self.valve_meter.configure(bootstyle="warning")
            else:
                self.valve_meter.configure(bootstyle="danger")

            self._set_status(f"Obliczono: {valve_count} zaworów ({typ_zaworu})")
            self._toast("Obliczenia zakończone", f"Potrzeba {valve_count} zaworów {typ_zaworu}", "success")

            # Snapshot dla eksportu PDF (obiekt zamiast parsowania stringa)
            self._last_snapshot = {
                "result": result,
                "V": V,
                "temp_przed": temp_przed,
                "temp_za": temp_za,
                "ilosc_chlodnic": ilosc_chlodnic,
                "F_total": F_total,
            }

            # Historia + auto-zapis (limit z renumeracją)
            self._history.append({
                "nr": len(self._history) + 1,
                "V": V,
                "delta_T": result.delta_T,
                "Q": result.Q,
                "ilosc_zaworow": result.ilosc_zaworow,
                "typ_zaworu": typ_zaworu,
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                "results_str": results_str,
                "snapshot": self._last_snapshot,
            })
            if len(self._history) > _HISTORY_LIMIT:
                self._history = self._history[-_HISTORY_LIMIT:]
                for i, e in enumerate(self._history, 1):
                    e["nr"] = i
            self._update_history_view()
            self._save_last_inputs()

        except (ValueError, KeyError) as e:
            self._set_status("Błąd danych wejściowych")
            messagebox.showerror("Błąd danych", str(e))
        except Exception as e:
            _logger.exception("Nieoczekiwany błąd w calculate()")
            self._set_status("Błąd obliczeń")
            messagebox.showerror("Błąd", f"Wystąpił nieoczekiwany błąd podczas obliczeń:\n{e}")

    def copy_results(self):
        """Kopiuje wyniki do schowka."""
        try:
            self.master.clipboard_clear()
            self.master.clipboard_append(self.results_text.get(1.0, tk.END))
            self._set_status("Skopiowano do schowka")
            self._toast("Skopiowano", "Wyniki skopiowane do schowka", "info", 1800)
        except tk.TclError as e:
            _logger.exception("Błąd schowka w copy_results()")
            messagebox.showerror("Błąd schowka", f"Nie udało się skopiować wyników:\n{e}")

    # ── Historia obliczeń ──────────────────────────────────
    def _update_history_view(self):
        """Odświeża zakładkę historii i Treeview."""
        self._notebook.tab(1, text=f" 📋 Historia ({len(self._history)}) ")
        self._history_tree.delete(*self._history_tree.get_children())
        for entry in self._history:
            self._history_tree.insert("", "end", values=(
                entry["nr"], f"{entry['V']:.1f}", f"{entry['delta_T']:.2f}",
                f"{entry['Q']:.1f}", entry["ilosc_zaworow"],
                entry["typ_zaworu"], entry["timestamp"],
            ))

    def _on_history_select(self, event):
        """Przywraca wyniki z wybranego wpisu historii."""
        selection = self._history_tree.selection()
        if not selection:
            return
        item = self._history_tree.item(selection[0])
        nr = int(item["values"][0])
        # Znajdź wpis po numerze (odporne na przycinanie FIFO historii)
        entry = next((e for e in self._history if e["nr"] == nr), None)
        if entry is None:
            return
        self.results_text.config(state="normal")
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, entry["results_str"])
        self.results_text.config(state="disabled")
        self._last_result_text = entry["results_str"]
        self._last_snapshot = entry.get("snapshot")
        self._notebook.select(0)
        self._set_status(f"Przywrócono wynik #{nr}")

    # ── Eksport CSV ────────────────────────────────────────
    def _export_csv(self):
        """Eksportuje historię obliczeń do pliku CSV."""
        if not self._history:
            messagebox.showinfo("Info", "Brak danych do eksportu. Wykonaj obliczenia.")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            title="Eksportuj historię do CSV",
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(["Nr", "V [m³]", "ΔT [°C/min]", "Q [l/min]",
                                 "Ilość zaworów", "Typ zaworu", "Czas"])
                for entry in self._history:
                    writer.writerow([
                        entry["nr"], f"{entry['V']:.2f}", f"{entry['delta_T']:.2f}",
                        f"{entry['Q']:.2f}", entry["ilosc_zaworow"],
                        entry["typ_zaworu"], entry["timestamp"],
                    ])
            self._set_status(f"CSV zapisany: {os.path.basename(file_path)}")
            self._toast("CSV gotowy", "Historia wyeksportowana do CSV", "info")
        except OSError as e:
            _logger.exception("Błąd I/O przy eksporcie CSV: %s", file_path)
            messagebox.showerror("Błąd", f"Nie udało się zapisać CSV: {e}")

    # ── Auto-zapis / odczyt ostatnich danych wejściowych ──
    def _save_last_inputs(self):
        """Zapisuje bieżące wartości pól do pliku JSON."""
        data = {
            "wybor_kubatury": self.wybor_kubatury_var.get(),
            "objetosc": self.objetosc_var.get(),
            "dlugosc": self.dlugosc_var.get(),
            "szerokosc": self.szerokosc_var.get(),
            "wysokosc": self.wysokosc_var.get(),
            "temp_przed": self.temp_przed_var.get(),
            "temp_za": self.temp_za_var.get(),
            "ilosc_chlodnic": self.ilosc_chlodnic_var.get(),
            "przeplyw_powietrza": self.przeplyw_powietrza_var.get(),
            "typ_zaworu": self.typ_zaworu_var.get(),
        }
        try:
            with open(_LAST_INPUTS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _load_last_inputs(self):
        """Wczytuje ostatnio użyte wartości z pliku JSON (jeśli istnieje)."""
        try:
            with open(_LAST_INPUTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.wybor_kubatury_var.set(data.get("wybor_kubatury", "K"))
            self.objetosc_var.set(data.get("objetosc", ""))
            self.dlugosc_var.set(data.get("dlugosc", ""))
            self.szerokosc_var.set(data.get("szerokosc", ""))
            self.wysokosc_var.set(data.get("wysokosc", ""))
            self.temp_przed_var.set(data.get("temp_przed", ""))
            self.temp_za_var.set(data.get("temp_za", ""))
            self.ilosc_chlodnic_var.set(data.get("ilosc_chlodnic", ""))
            self.przeplyw_powietrza_var.set(data.get("przeplyw_powietrza", ""))
            self.typ_zaworu_var.set(data.get("typ_zaworu", "Maxi Elebar"))
            self._toggle_kubatura_fields()
        except (OSError, json.JSONDecodeError):
            pass

    def generate_pdf(self):
        """
        Generuje plik PDF (tabela wyników, znak wodny, szyfrowanie AES-256 gdy dostępne).
        Używa obiektu CalculationResult — bez parsowania tekstu.
        """
        if not self._last_snapshot:
            messagebox.showerror("Błąd", "Najpierw wykonaj obliczenia.")
            return

        desktop_path = pathlib.Path(os.path.join(os.path.expanduser("~"), "Desktop"))
        file_path = filedialog.asksaveasfilename(
            initialdir=desktop_path,
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            title="Zapisz PDF",
        )
        if not file_path:
            return

        try:
            snap = self._last_snapshot
            final_pdf_path = pdf_service.generate_pdf(
                file_path,
                result=snap["result"],
                V=snap["V"],
                temp_przed=snap["temp_przed"],
                temp_za=snap["temp_za"],
                ilosc_chlodnic=snap["ilosc_chlodnic"],
                F_total=snap["F_total"],
            )

            self._set_status(f"PDF zapisany: {os.path.basename(file_path)}")
            self._toast("PDF gotowy", "Plik PDF wygenerowany", "success")
            self.open_pdf(final_pdf_path)

        except OSError as e:
            _logger.exception("Błąd I/O przy generowaniu PDF: %s", file_path)
            messagebox.showerror("Błąd zapisu", f"Nie można zapisać pliku:\n{e}")
        except Exception as e:
            _logger.exception("Nieoczekiwany błąd w generate_pdf()")
            messagebox.showerror("Błąd PDF", f"Wystąpił nieoczekiwany błąd podczas generowania PDF:\n{e}")
    
    def open_pdf(self, pdf_path):
        """Otwiera wygenerowany plik PDF w domyślnej przeglądarce PDF."""
        try:
            if sys.platform == "win32":
                os.startfile(pdf_path)  # Dla Windows
            elif sys.platform == "darwin":
                subprocess.Popen(["open", pdf_path])  # Dla macOS
            else:
                subprocess.Popen(["xdg-open", pdf_path])  # Dla Linuxa
        except (OSError, subprocess.SubprocessError) as e:
            _logger.exception("Nie można otworzyć PDF: %s", pdf_path)
            messagebox.showerror("Błąd", f"Nie udało się otworzyć pliku PDF:\n{e}")

def main():
    root = ttk.Window(
        title="Kalkulator Zaworów Dekompresyjnych — MD-Puch",
        themename="litera",
        size=(620, 840),
        minsize=(580, 760),
        resizable=(True, True),
    )
    root.place_window_center()
    app = DecompressionValveCalculatorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
