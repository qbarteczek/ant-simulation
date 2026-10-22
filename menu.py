"""Ekran konfiguracji warunków początkowych symulacji."""
import pygame

import config as C

PANEL_CENTER_X = C.WIDTH // 2
ROW_LABEL_X = PANEL_CENTER_X - 260
ROW_CTRL_X = PANEL_CENTER_X + 20

# Towarzyszące istoty: sześć gatunków nie mieści się w jednej kolumnie -
# układ dwukolumnowy, lewa i prawa kolumna lustrzane względem środka.
LEFT_LABEL_X, LEFT_CTRL_X = 60, 340
RIGHT_LABEL_X, RIGHT_CTRL_X = 620, 900


class Menu:
    def __init__(self):
        self.font_title = pygame.font.Font(None, 46)
        self.font_label = pygame.font.Font(None, 26)
        self.font_btn = pygame.font.Font(None, 22)
        self.font_small = pygame.font.Font(None, 20)

        self.biome = "Łąka"
        self.season = "Lato"
        self.species = "Mrówka łąkowa"
        self.ant_count = C.ANT_COUNT_DEFAULT
        self.companions = {name: d["default"] for name, d in C.COMPANIONS.items()}
        self.agents = C.AGENT_COUNT_DEFAULT

        self.biome_buttons = self._row_buttons(list(C.BIOMES.keys()), y=112, width=190)
        self.season_buttons = self._row_buttons(list(C.SEASONS.keys()), y=206, width=190)
        self.species_buttons = self._row_buttons(list(C.SPECIES.keys()), y=300, width=220)

        (
            self.ant_coarse_minus,
            self.ant_minus,
            self.ant_value,
            self.ant_plus,
            self.ant_coarse_plus,
        ) = self._ant_counter_rects(y=396)
        self.agent_minus, self.agent_value, self.agent_plus = self._counter_row_rects(396, ctrl_x=1010)

        names = list(C.COMPANIONS.keys())
        half = (len(names) + 1) // 2
        left_names, right_names = names[:half], names[half:]
        self.companion_rows = {}
        self.companion_label_x = {}
        row_y = 486
        for i in range(max(len(left_names), len(right_names))):
            y = row_y + i * 64
            if i < len(left_names):
                name = left_names[i]
                self.companion_rows[name] = (self._counter_row_rects(y, ctrl_x=LEFT_CTRL_X), y)
                self.companion_label_x[name] = LEFT_LABEL_X
            if i < len(right_names):
                name = right_names[i]
                self.companion_rows[name] = (self._counter_row_rects(y, ctrl_x=RIGHT_CTRL_X), y)
                self.companion_label_x[name] = RIGHT_LABEL_X

        self.start_button = pygame.Rect(0, 0, 300, 58)
        self.start_button.center = (C.WIDTH // 2, C.HEIGHT - 55)

    def _row_buttons(self, labels, y, width=190, height=42, gap=16):
        n = len(labels)
        total_w = n * width + (n - 1) * gap
        start_x = (C.WIDTH - total_w) // 2
        rects = []
        for i, label in enumerate(labels):
            r = pygame.Rect(start_x + i * (width + gap), y, width, height)
            rects.append((r, label))
        return rects

    def _ant_counter_rects(self, y):
        # [-250] [-25] [ wartosc ] [+25] [+250], wysrodkowane
        btn_w, coarse_w, box_w, gap = 46, 62, 100, 10
        total_w = coarse_w + gap + btn_w + gap + box_w + gap + btn_w + gap + coarse_w
        start_x = (C.WIDTH - total_w) // 2
        coarse_minus = pygame.Rect(start_x, y, coarse_w, 36)
        minus = pygame.Rect(coarse_minus.right + gap, y, btn_w, 36)
        value = pygame.Rect(minus.right + gap, y, box_w, 36)
        plus = pygame.Rect(value.right + gap, y, btn_w, 36)
        coarse_plus = pygame.Rect(plus.right + gap, y, coarse_w, 36)
        return coarse_minus, minus, value, plus, coarse_plus

    def _counter_row_rects(self, y, centered=False, ctrl_x=None):
        if centered:
            btn_w, box_w, gap = 44, 90, 12
            total_w = btn_w + gap + box_w + gap + btn_w
            start_x = (C.WIDTH - total_w) // 2
        else:
            btn_w, box_w, gap = 36, 80, 10
            start_x = ROW_CTRL_X if ctrl_x is None else ctrl_x
        minus = pygame.Rect(start_x, y, btn_w, 36)
        value = pygame.Rect(start_x + btn_w + gap, y, box_w, 36)
        plus = pygame.Rect(start_x + btn_w + gap + box_w + gap, y, btn_w, 36)
        return minus, value, plus

    def handle_event(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None
        pos = event.pos

        for rect, label in self.biome_buttons:
            if rect.collidepoint(pos):
                self.biome = label
        for rect, label in self.season_buttons:
            if rect.collidepoint(pos):
                self.season = label
        for rect, label in self.species_buttons:
            if rect.collidepoint(pos):
                self.species = label

        if self.ant_minus.collidepoint(pos):
            self.ant_count = max(C.ANT_COUNT_MIN, self.ant_count - C.ANT_COUNT_STEP)
        elif self.ant_plus.collidepoint(pos):
            self.ant_count = min(C.ANT_COUNT_MAX, self.ant_count + C.ANT_COUNT_STEP)
        elif self.ant_coarse_minus.collidepoint(pos):
            self.ant_count = max(C.ANT_COUNT_MIN, self.ant_count - C.ANT_COUNT_COARSE_STEP)
        elif self.ant_coarse_plus.collidepoint(pos):
            self.ant_count = min(C.ANT_COUNT_MAX, self.ant_count + C.ANT_COUNT_COARSE_STEP)

        if self.agent_minus.collidepoint(pos):
            self.agents = max(0, self.agents - 1)
        elif self.agent_plus.collidepoint(pos):
            self.agents = min(C.AGENT_COUNT_MAX, self.agents + 1)

        for name, ((minus, value, plus), y) in self.companion_rows.items():
            d = C.COMPANIONS[name]
            if minus.collidepoint(pos):
                self.companions[name] = max(d["min"], self.companions[name] - d["step"])
            elif plus.collidepoint(pos):
                self.companions[name] = min(d["max"], self.companions[name] + d["step"])

        if self.start_button.collidepoint(pos):
            return dict(
                biome=self.biome,
                season=self.season,
                species=self.species,
                ant_count=self.ant_count,
                companions=dict(self.companions),
                agents=self.agents,
            )
        return None

    def _draw_button(self, surface, rect, label, selected, font):
        color = (86, 140, 86) if selected else (55, 58, 68)
        border = (235, 235, 225) if selected else (110, 112, 122)
        pygame.draw.rect(surface, color, rect, border_radius=8)
        pygame.draw.rect(surface, border, rect, width=2, border_radius=8)
        txt = font.render(label, True, (245, 245, 245))
        surface.blit(txt, txt.get_rect(center=rect.center))

    def _draw_counter(self, surface, minus, value_rect, plus, value):
        for rect, label in ((minus, "-"), (plus, "+")):
            pygame.draw.rect(surface, (70, 74, 86), rect, border_radius=6)
            pygame.draw.rect(surface, (140, 142, 150), rect, width=2, border_radius=6)
            txt = self.font_btn.render(label, True, (255, 255, 255))
            surface.blit(txt, txt.get_rect(center=rect.center))
        pygame.draw.rect(surface, (25, 27, 33), value_rect, border_radius=6)
        pygame.draw.rect(surface, (140, 142, 150), value_rect, width=2, border_radius=6)
        txt = self.font_btn.render(str(value), True, (255, 255, 255))
        surface.blit(txt, txt.get_rect(center=value_rect.center))

    def draw(self, surface):
        surface.fill((28, 30, 36))
        title = self.font_title.render("Konfiguracja symulacji mrowiska", True, (240, 240, 235))
        surface.blit(title, title.get_rect(center=(C.WIDTH // 2, 46)))

        self._section_label(surface, "Miejsce (biom)", 90)
        for rect, label in self.biome_buttons:
            self._draw_button(surface, rect, label, label == self.biome, self.font_btn)

        self._section_label(surface, "Pora roku", 184)
        for rect, label in self.season_buttons:
            self._draw_button(surface, rect, label, label == self.season, self.font_btn)

        self._section_label(surface, "Rodzaj mrówek", 278)
        for rect, label in self.species_buttons:
            self._draw_button(surface, rect, label, label == self.species, self.font_btn)

        self._section_label(surface, "Liczba mrówek na start", 372)
        self._draw_button(surface, self.ant_coarse_minus, "-250", False, self.font_small)
        self._draw_button(surface, self.ant_coarse_plus, "+250", False, self.font_small)
        self._draw_counter(surface, self.ant_minus, self.ant_value, self.ant_plus, self.ant_count)

        agent_lbl = self.font_label.render("Agenci Claude", True, (150, 200, 255))
        surface.blit(agent_lbl, (self.agent_minus.x - agent_lbl.get_width() - 14, 396 + 4))
        agent_desc = self.font_small.render("(mrówki myślące modelem Claude)", True, (150, 152, 160))
        surface.blit(agent_desc, (C.WIDTH - agent_desc.get_width() - 18, 396 + 40))
        self._draw_counter(surface, self.agent_minus, self.agent_value, self.agent_plus, self.agents)

        self._section_label(surface, "Towarzyszące istoty", 462)
        descs = {
            "Mszyce": "(dają miodową spadź - dodatkowe źródło jedzenia)",
            "Pająki": "(polują na pojedyncze mrówki, uciekają przed grupą)",
            "Biedronki": "(żywią się mszycami, zmniejszając ich populację)",
            "Osy": "(polują na mszyce, głodne - też na mrówki)",
            "Chrząszcze": "(zjadają truchła, użyźniając pobliskie rośliny)",
            "Dżdżownice": "(poprawiają żyzność gleby wokół roślin)",
        }
        for name, ((minus, value, plus), y) in self.companion_rows.items():
            label_x = self.companion_label_x[name]
            label_txt = self.font_label.render(name, True, (230, 230, 225))
            surface.blit(label_txt, (label_x, y + 4))
            desc_txt = self.font_small.render(descs[name], True, (150, 152, 160))
            surface.blit(desc_txt, (label_x, y + 28))
            self._draw_counter(surface, minus, value, plus, self.companions[name])

        pygame.draw.rect(surface, (80, 140, 80), self.start_button, border_radius=10)
        pygame.draw.rect(surface, (230, 240, 225), self.start_button, width=2, border_radius=10)
        start_txt = self.font_title.render("Rozpocznij symulację", True, (255, 255, 255))
        start_txt = pygame.transform.smoothscale(
            start_txt, (int(start_txt.get_width() * 0.62), int(start_txt.get_height() * 0.62))
        )
        surface.blit(start_txt, start_txt.get_rect(center=self.start_button.center))

    def _section_label(self, surface, text, y):
        txt = self.font_label.render(text, True, (200, 205, 215))
        surface.blit(txt, txt.get_rect(center=(C.WIDTH // 2, y)))
