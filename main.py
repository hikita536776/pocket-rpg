"""Pocket RPG: Android-интерфейс на Kivy."""

import os
from typing import Callable, List, Optional, Sequence, Union

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import escape_markup

from engine import CLASSES, INN_PRICE, POTION_PRICE, SAVE_FILENAME, Game, Player

BG = (0.09, 0.10, 0.12, 1)
BUTTON = (0.20, 0.42, 0.40, 1)
DANGER = (0.55, 0.22, 0.22, 1)
MAX_LOG_LINES = 150
ROW_HEIGHT = dp(54)

Action = tuple  # (текст, callback) или (текст, callback, цвет)
Row = Sequence[Union[Action, object]]


class RPGRoot(BoxLayout):
    def __init__(self, save_path: str, **kwargs):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(8), **kwargs)
        self.save_path = save_path
        self.game: Optional[Game] = None
        self.screen = "start"
        self.log_lines: List[str] = []

        with self.canvas.before:
            Color(*BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        self.header = Label(size_hint_y=None, height=dp(88), markup=True,
                            halign="left", valign="middle", font_size=sp(15))
        self.header.bind(size=lambda inst, size: setattr(inst, "text_size", size))

        self.scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))
        self.log_label = Label(size_hint_y=None, markup=True, halign="left",
                               valign="top", font_size=sp(16), line_height=1.15)
        self.log_label.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
        self.log_label.bind(texture_size=lambda inst, s: setattr(inst, "height", s[1]))
        self.scroll.add_widget(self.log_label)

        self.controls = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))

        self.add_widget(self.header)
        self.add_widget(self.scroll)
        self.add_widget(self.controls)
        self.show_start()

    # ---------- служебное ----------
    def _update_bg(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def log(self, messages: Sequence[str]) -> None:
        for text in messages:
            safe = escape_markup(text)
            if text == "Раунд":
                safe = "[color=7f8c8d]· · · новый раунд · · ·[/color]"
            elif text.startswith(("Победа", "Квест выполнен", "Новый уровень")):
                safe = f"[color=f4d35e][b]{safe}[/b][/color]"
            elif text.startswith(("Ты пал", "Ты отравлен", "Тебя оглушили")):
                safe = f"[color=ff7b7b]{safe}[/color]"
            self.log_lines.append(safe)
        self.log_lines = self.log_lines[-MAX_LOG_LINES:]
        self.log_label.text = "\n".join(self.log_lines)
        Clock.schedule_once(self._scroll_down, 0.05)

    def _scroll_down(self, *_):
        self.scroll.scroll_y = 0

    def set_controls(self, rows: Sequence[Row]) -> None:
        self.controls.clear_widgets()
        for row in rows:
            line = BoxLayout(spacing=dp(6), size_hint_y=None, height=ROW_HEIGHT)
            for item in row:
                if isinstance(item, tuple):
                    line.add_widget(self._make_button(*item))
                else:
                    line.add_widget(item)
            self.controls.add_widget(line)
        self.controls.height = ROW_HEIGHT * len(rows) + dp(6) * max(0, len(rows) - 1)

    def _make_button(self, text: str, callback: Callable[[], None], color=BUTTON) -> Button:
        button = Button(text=text, font_size=sp(16), halign="center", valign="middle",
                        background_normal="", background_color=color)
        button.bind(size=lambda inst, size: setattr(inst, "text_size", (size[0] - dp(8), None)))
        button.bind(on_release=lambda *_: callback())
        return button

    def update_header(self) -> None:
        if not self.game:
            self.header.text = "[b][size=22sp]Pocket RPG[/size][/b]\nТекстовое приключение"
            return
        p = self.game.player
        text = (f"[b]{escape_markup(p.name)}[/b]  {p.class_name}, ур. {p.level}\n"
                f"HP {p.hp}/{p.max_hp}   опыт {p.xp}/{p.xp_needed}\n"
                f"золото {p.gold}   зелья {p.potions}")
        enemy = self.game.enemy
        if enemy:
            text += f"\n[color=ff9f9f]{escape_markup(enemy.name)}: HP {enemy.hp}/{enemy.max_hp}[/color]"
        self.header.text = text

    def autosave(self) -> None:
        if self.game:
            try:
                self.game.save(self.save_path)
            except OSError as error:
                self.log([f"Не удалось сохранить: {error}"])

    # ---------- экраны ----------
    def show_start(self) -> None:
        self.screen = "start"
        self.update_header()
        saved = Game.load(self.save_path)
        if saved:
            self.log([f"Найдено сохранение: {saved.player.name}, уровень {saved.player.level}."])
            self.set_controls([
                [("Продолжить", lambda: self.continue_game(saved))],
                [("Новая игра", self.show_create, DANGER)],
            ])
        else:
            self.log(["Добро пожаловать в Pocket RPG!"])
            self.show_create()

    def continue_game(self, game: Game) -> None:
        self.game = game
        self.log([f"С возвращением, {game.player.name}!"])
        self.show_village()

    def show_create(self) -> None:
        self.screen = "create"
        self.log(["Придумай имя и выбери класс:"] + [
            f"{c['name']}: HP {c['max_hp']}, атака {c['attack']}, защита {c['defense']}, "
            f"приём «{c['special']}»" for c in CLASSES.values()])
        self.name_input = TextInput(hint_text="Имя героя", multiline=False, font_size=sp(18),
                                    padding=(dp(10), dp(14)))
        self.set_controls([
            [self.name_input],
            [(c["name"], (lambda cid=cid: self.create_hero(cid))) for cid, c in CLASSES.items()],
        ])

    def create_hero(self, class_id: str) -> None:
        self.game = Game(Player.create(self.name_input.text, class_id))
        self.autosave()
        self.log([f"Герой создан: {self.game.player.name}, {self.game.player.class_name}."])
        self.show_village()

    def show_village(self) -> None:
        self.screen = "village"
        self.update_header()
        self.set_controls([
            [("Статус", self.on_status), ("Староста", self.on_talk)],
            [("В лес", self.on_forest, DANGER), ("Магазин", self.show_shop)],
            [(f"Таверна ({INN_PRICE} з.)", self.on_rest), ("Сохранить", self.on_save)],
        ])

    def on_status(self) -> None:
        self.log(self.game.status_lines())

    def on_talk(self) -> None:
        self.log(self.game.talk())
        if self.game.quest_offer_available:
            self.screen = "talk"
            self.set_controls([[("Взять квест", self.on_accept_quest), ("Не сейчас", self.show_village)]])

    def on_accept_quest(self) -> None:
        self.log(self.game.accept_quest())
        self.autosave()
        self.show_village()

    def show_shop(self) -> None:
        self.screen = "shop"
        self.log([f"Торговец: зелье лечения за {POTION_PRICE} золота."])
        self.set_controls([[(f"Купить зелье ({POTION_PRICE} з.)", self.on_buy), ("Назад", self.show_village)]])

    def on_buy(self) -> None:
        self.log(self.game.buy_potion())
        self.update_header()
        self.autosave()

    def on_rest(self) -> None:
        self.log(self.game.rest())
        self.update_header()
        self.autosave()

    def on_save(self) -> None:
        self.autosave()
        self.log(["Игра сохранена."])

    def on_forest(self) -> None:
        self.log(self.game.start_battle())
        self.show_battle()

    def show_battle(self) -> None:
        self.screen = "battle"
        self.update_header()
        game = self.game
        special = game.player.special_name
        if game.special_cooldown:
            special += f" ({game.special_cooldown})"
        self.set_controls([
            [("Атака", lambda: self.on_battle("attack")), (special, lambda: self.on_battle("special"))],
            [(f"Зелье ({game.player.potions})", lambda: self.on_battle("potion")),
             ("Сбежать", lambda: self.on_battle("flee"), DANGER)],
        ])

    def on_battle(self, action: str) -> None:
        self.log(self.game.battle_action(action))
        if self.game.in_battle:
            self.show_battle()
        else:
            self.autosave()
            self.show_village()

    def handle_back(self) -> bool:
        """Кнопка «Назад» на Android. True значит, что событие обработано."""
        if self.screen in ("shop", "talk"):
            self.show_village()
            return True
        if self.screen == "battle":
            self.log(["Из боя так не уйти: жми «Сбежать»."])
            return True
        return False


class PocketRPGApp(App):
    title = "Pocket RPG"

    def build(self):
        Window.clearcolor = BG
        Window.softinput_mode = "below_target"
        Window.bind(on_keyboard=self._on_keyboard)
        return RPGRoot(os.path.join(self.user_data_dir, SAVE_FILENAME))

    def _on_keyboard(self, _window, key, *_args):
        if key == 27:  # Esc на ПК, «Назад» на Android
            return self.root.handle_back()
        return False

    def on_pause(self):
        self.root.autosave()
        return True

    def on_stop(self):
        self.root.autosave()


if __name__ == "__main__":
    PocketRPGApp().run()
