"""Игровая логика Pocket RPG. Не зависит от Kivy, поэтому её легко тестировать."""

import json
import os
import random
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

SAVE_FILENAME = "pocket_rpg_save.json"
SAVE_VERSION = 1

XP_PER_LEVEL = 40
POTION_PRICE = 10
POTION_HEAL = 35
INN_PRICE = 8
QUEST_TARGET = 3
SPECIAL_COOLDOWN = 2
FLEE_CHANCE = 0.55
PLAYER_INITIATIVE = 0.65
POISON_DAMAGE = 5

CLASSES: Dict[str, dict] = {
    "warrior": {"name": "Воин", "max_hp": 120, "attack": 16, "defense": 7,
                "special": "Мощный удар", "multiplier": 1.8, "crit": 0.10},
    "mage": {"name": "Маг", "max_hp": 85, "attack": 21, "defense": 3,
             "special": "Огненный шар", "multiplier": 1.65, "crit": 0.10},
    "rogue": {"name": "Вор", "max_hp": 100, "attack": 14, "defense": 4,
              "special": "Удар из тени", "multiplier": 1.65, "crit": 0.25},
}

ENEMIES: List[dict] = [
    {"name": "Слизень", "max_hp": 34, "attack": 9, "defense": 1, "xp": 18, "gold": 7,
     "ability": "poison", "chance": 0.25},
    {"name": "Лесной волк", "max_hp": 46, "attack": 12, "defense": 2, "xp": 25, "gold": 10,
     "ability": None, "chance": 0.0},
    {"name": "Разбойник", "max_hp": 58, "attack": 14, "defense": 3, "xp": 32, "gold": 14,
     "ability": "stun", "chance": 0.15},
]

STATUS_NAMES = {"poison": "яд", "stun": "оглушение"}


@dataclass
class Player:
    name: str
    class_id: str
    max_hp: int
    hp: int
    attack: int
    defense: int
    level: int = 1
    xp: int = 0
    gold: int = 0
    potions: int = 2
    statuses: Dict[str, int] = field(default_factory=dict)

    @classmethod
    def create(cls, name: str, class_id: str) -> "Player":
        if class_id not in CLASSES:
            raise ValueError(f"Неизвестный класс: {class_id}")
        data = CLASSES[class_id]
        clean_name = name.strip()[:20] or "Безымянный"
        return cls(clean_name, class_id, data["max_hp"], data["max_hp"],
                   data["attack"], data["defense"])

    @property
    def class_name(self) -> str:
        return CLASSES[self.class_id]["name"]

    @property
    def special_name(self) -> str:
        return CLASSES[self.class_id]["special"]

    @property
    def xp_needed(self) -> int:
        return self.level * XP_PER_LEVEL


@dataclass
class Enemy:
    name: str
    max_hp: int
    hp: int
    attack: int
    defense: int
    xp: int
    gold: int
    ability: Optional[str]
    ability_chance: float
    statuses: Dict[str, int] = field(default_factory=dict)


def tick_statuses(character, label: str) -> Tuple[List[str], bool]:
    """Срабатывает в начале хода: урон от яда и уменьшение длительности эффектов."""
    messages: List[str] = []
    stunned = character.statuses.get("stun", 0) > 0
    if character.statuses.get("poison", 0) > 0:
        damage = min(POISON_DAMAGE, character.hp)
        character.hp -= damage
        messages.append(f"{label} получает {damage} урона от яда.")
    for status in list(character.statuses):
        character.statuses[status] -= 1
        if character.statuses[status] <= 0:
            del character.statuses[status]
    return messages, stunned


class Game:
    def __init__(self, player: Player, quest_status: str = "not_started",
                 quest_progress: int = 0, rng: Optional[random.Random] = None):
        self.player = player
        self.quest_status = quest_status  # not_started / active / done
        self.quest_progress = quest_progress
        self.rng = rng or random.Random()
        self.enemy: Optional[Enemy] = None
        self.special_cooldown = 0
        self.last_result: Optional[str] = None  # win / fled / dead

    # ---------- сохранение ----------
    def to_dict(self) -> dict:
        return {"version": SAVE_VERSION, "player": asdict(self.player),
                "quest_status": self.quest_status, "quest_progress": self.quest_progress}

    @classmethod
    def from_dict(cls, data: dict, rng: Optional[random.Random] = None) -> "Game":
        p = data["player"]
        if p["class_id"] not in CLASSES:
            raise ValueError("Неизвестный класс в сохранении")
        player = Player(
            name=str(p["name"]), class_id=p["class_id"],
            max_hp=int(p["max_hp"]), hp=int(p["hp"]), attack=int(p["attack"]),
            defense=int(p["defense"]), level=int(p.get("level", 1)), xp=int(p.get("xp", 0)),
            gold=int(p.get("gold", 0)), potions=int(p.get("potions", 0)),
            statuses={str(k): int(v) for k, v in dict(p.get("statuses", {})).items()},
        )
        player.hp = max(1, min(player.hp, player.max_hp))
        quest_status = data.get("quest_status", "not_started")
        if quest_status not in ("not_started", "active", "done"):
            quest_status = "not_started"
        return cls(player, quest_status, int(data.get("quest_progress", 0)), rng)

    def save(self, path: str) -> None:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        temp_path = path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)  # атомарно: сохранение не побьётся при вылете

    @classmethod
    def load(cls, path: str, rng: Optional[random.Random] = None) -> Optional["Game"]:
        try:
            with open(path, "r", encoding="utf-8") as file:
                return cls.from_dict(json.load(file), rng)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return None

    # ---------- деревня ----------
    @property
    def in_battle(self) -> bool:
        return self.enemy is not None

    @property
    def quest_offer_available(self) -> bool:
        return self.quest_status == "not_started"

    def status_lines(self) -> List[str]:
        p = self.player
        lines = [
            f"{p.name}, {p.class_name}, уровень {p.level}",
            f"HP {p.hp}/{p.max_hp}, атака {p.attack}, защита {p.defense}",
            f"Опыт {p.xp}/{p.xp_needed}, золото {p.gold}, зелья {p.potions}",
            f"Квест: {self.quest_text()}",
        ]
        if p.statuses:
            lines.append("Эффекты: " + ", ".join(
                f"{STATUS_NAMES.get(k, k)} ({v})" for k, v in p.statuses.items()))
        return lines

    def quest_text(self) -> str:
        if self.quest_status == "active":
            return f"победить врагов {self.quest_progress}/{QUEST_TARGET}"
        if self.quest_status == "done":
            return "выполнен"
        return "не взят"

    def talk(self) -> List[str]:
        if self.quest_status == "not_started":
            return ["Староста: В лесу расплодились чудовища. Победи трёх, и деревня тебя наградит."]
        if self.quest_status == "active":
            return [f"Староста: Побеждено {self.quest_progress}/{QUEST_TARGET}. Не сдавайся!"]
        return ["Староста: Спасибо, герой! Деревня в долгу перед тобой."]

    def accept_quest(self) -> List[str]:
        if self.quest_status != "not_started":
            return ["Этот квест уже взят."]
        self.quest_status = "active"
        self.quest_progress = 0
        return [f"Квест принят: победи {QUEST_TARGET} врагов в лесу."]

    def buy_potion(self) -> List[str]:
        if self.player.gold < POTION_PRICE:
            return [f"Не хватает золота: зелье стоит {POTION_PRICE}."]
        self.player.gold -= POTION_PRICE
        self.player.potions += 1
        return [f"Куплено зелье. Теперь зелий: {self.player.potions}."]

    def rest(self) -> List[str]:
        p = self.player
        if p.hp == p.max_hp and not p.statuses:
            return ["Ты и так полон сил."]
        if p.gold < INN_PRICE:
            return [f"Ночь в таверне стоит {INN_PRICE} золота. Денег не хватает."]
        p.gold -= INN_PRICE
        p.hp = p.max_hp
        p.statuses.clear()
        return ["Ты выспался в таверне. HP полностью восстановлены."]

    # ---------- бой ----------
    def start_battle(self) -> List[str]:
        if self.in_battle:
            return ["Ты уже в бою!"]
        t = self.rng.choice(ENEMIES)
        bonus = self.player.level - 1
        max_hp = int(t["max_hp"] * (1 + 0.15 * bonus))
        self.enemy = Enemy(
            name=t["name"], max_hp=max_hp, hp=max_hp, attack=t["attack"] + 2 * bonus,
            defense=t["defense"] + bonus // 2, xp=t["xp"] + 5 * bonus, gold=t["gold"] + 2 * bonus,
            ability=t["ability"], ability_chance=t["chance"],
        )
        self.special_cooldown = 0
        self.last_result = None
        return [f"Из чащи выходит {self.enemy.name} (HP {max_hp})!"]

    def battle_action(self, action: str) -> List[str]:
        if not self.in_battle:
            return ["Сейчас ты не в бою."]
        if action not in ("attack", "special", "potion", "flee"):
            raise ValueError(f"Неизвестное действие: {action}")
        # Эти проверки не тратят ход.
        if action == "special" and self.special_cooldown > 0:
            return [f"{self.player.special_name} будет готов через {self.special_cooldown} ход."]
        if action == "potion" and self.player.potions <= 0:
            return ["Зелий не осталось."]
        if action == "potion" and self.player.hp == self.player.max_hp:
            return ["HP и так полные."]

        self._special_used = False
        log = ["Раунд"]
        player_first = self.rng.random() < PLAYER_INITIATIVE
        order = ("player", "enemy") if player_first else ("enemy", "player")
        if not player_first:
            log.append(f"{self.enemy.name} оказывается быстрее!")
        for side in order:
            if self._someone_down():
                break
            if side == "player":
                log += self._player_turn(action)
                if not self.in_battle:  # сбежал
                    return log
            else:
                log += self._enemy_turn()
        if self.special_cooldown > 0 and not self._special_used:
            self.special_cooldown -= 1
        log += self._resolve_battle_end()
        return log

    def _someone_down(self) -> bool:
        return self.player.hp <= 0 or (self.enemy is not None and self.enemy.hp <= 0)

    def _hero_damage(self, multiplier: float) -> Tuple[int, bool]:
        p, e = self.player, self.enemy
        damage = max(1, int(p.attack * multiplier) + self.rng.randint(-2, 3) - e.defense)
        critical = self.rng.random() < CLASSES[p.class_id]["crit"]
        return (damage * 2 if critical else damage), critical

    def _player_turn(self, action: str) -> List[str]:
        p, e = self.player, self.enemy
        log, stunned = tick_statuses(p, p.name)
        if p.hp <= 0:
            return log
        if stunned:
            log.append(f"{p.name} оглушён и пропускает ход!")
            return log

        if action in ("attack", "special"):
            multiplier = CLASSES[p.class_id]["multiplier"] if action == "special" else 1.0
            damage, critical = self._hero_damage(multiplier)
            e.hp = max(0, e.hp - damage)
            if critical:
                log.append("Критический удар!")
            if action == "special":
                self.special_cooldown = SPECIAL_COOLDOWN
                self._special_used = True
                log.append(f"{p.special_name}: {damage} урона.")
                if e.hp > 0 and p.class_id == "mage" and self.rng.random() < 0.35:
                    e.statuses["stun"] = 1
                    log.append(f"{e.name} оглушён!")
                elif e.hp > 0 and p.class_id == "rogue" and self.rng.random() < 0.40:
                    e.statuses["poison"] = 3
                    log.append(f"{e.name} отравлен!")
            else:
                log.append(f"Ты бьёшь и наносишь {damage} урона.")
        elif action == "potion":
            p.potions -= 1
            restored = min(POTION_HEAL, p.max_hp - p.hp)
            p.hp += restored
            log.append(f"Зелье восстановило {restored} HP.")
        else:
            if self.rng.random() < FLEE_CHANCE:
                log.append("Ты сбежал обратно в деревню.")
                self.enemy = None
                p.statuses.clear()
                self.last_result = "fled"
            else:
                log.append("Сбежать не вышло!")
        return log

    def _enemy_turn(self) -> List[str]:
        p, e = self.player, self.enemy
        log, stunned = tick_statuses(e, e.name)
        if e.hp <= 0:
            return log
        if stunned:
            log.append(f"{e.name} оглушён и пропускает ход!")
            return log
        damage = max(1, e.attack + self.rng.randint(-2, 2) - p.defense)
        p.hp = max(0, p.hp - damage)
        log.append(f"{e.name} атакует: {damage} урона.")
        if p.hp > 0 and e.ability and self.rng.random() < e.ability_chance:
            if e.ability == "poison":
                p.statuses["poison"] = 3
                log.append("Ты отравлен!")
            elif e.ability == "stun":
                p.statuses["stun"] = 1
                log.append("Тебя оглушили!")
        return log

    def _resolve_battle_end(self) -> List[str]:
        p, e = self.player, self.enemy
        if e is None:
            return []
        if p.hp <= 0:
            lost = p.gold // 2
            p.gold -= lost
            p.hp = p.max_hp
            p.statuses.clear()
            self.enemy = None
            self.last_result = "dead"
            return ["Ты пал в бою...", f"Тебя нашли и выходили в деревне. Потеряно {lost} золота."]
        if e.hp > 0:
            return []

        log = [f"Победа! {e.name} повержен.", f"Добыча: {e.gold} золота."]
        p.gold += e.gold
        p.statuses.clear()
        log += self._gain_xp(e.xp)
        if self.quest_status == "active":
            self.quest_progress += 1
            if self.quest_progress >= QUEST_TARGET:
                self.quest_status = "done"
                p.gold += 30
                p.potions += 2
                log.append("Квест выполнен! Награда: 30 золота и 2 зелья.")
            else:
                log.append(f"Квест: {self.quest_progress}/{QUEST_TARGET}.")
        self.enemy = None
        self.last_result = "win"
        return log

    def _gain_xp(self, amount: int) -> List[str]:
        p = self.player
        p.xp += amount
        log = [f"Опыт +{amount}."]
        while p.xp >= p.xp_needed:
            p.xp -= p.xp_needed
            p.level += 1
            p.max_hp += 12
            p.attack += 3
            p.defense += 1
            p.hp = p.max_hp
            log.append(f"Новый уровень: {p.level}! HP восстановлены.")
        return log
