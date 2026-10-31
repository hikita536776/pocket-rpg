import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import QUEST_TARGET, Game, Player  # noqa: E402


def make_game(class_id="warrior", seed=1):
    return Game(Player.create("Тест", class_id), rng=random.Random(seed))


class EngineTests(unittest.TestCase):
    def test_save_and_load(self):
        game = make_game("mage")
        game.player.gold = 42
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "save.json")
            game.save(path)
            loaded = Game.load(path)
        self.assertEqual(loaded.player.class_name, "Маг")
        self.assertEqual(loaded.player.gold, 42)

    def test_broken_save_returns_none(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "save.json")
            with open(path, "w", encoding="utf-8") as file:
                file.write("{not json")
            self.assertIsNone(Game.load(path))
            self.assertIsNone(Game.load(os.path.join(folder, "missing.json")))

    def test_battles_always_finish(self):
        for class_id in ("warrior", "mage", "rogue"):
            for seed in range(30):
                game = make_game(class_id, seed)
                game.start_battle()
                for _ in range(200):
                    if not game.in_battle:
                        break
                    action = "special" if game.special_cooldown == 0 else "attack"
                    game.battle_action(action)
                self.assertFalse(game.in_battle)
                self.assertIn(game.last_result, ("win", "dead"))
                self.assertGreater(game.player.hp, 0)

    def test_empty_potion_does_not_spend_turn(self):
        game = make_game()
        game.player.potions = 0
        game.start_battle()
        hp_before = game.enemy.hp
        self.assertEqual(game.battle_action("potion"), ["Зелий не осталось."])
        self.assertEqual(game.enemy.hp, hp_before)

    def test_special_cooldown(self):
        game = make_game()
        game.start_battle()
        game.enemy.hp = game.enemy.max_hp = 10_000
        game.battle_action("special")
        self.assertIn("будет готов", game.battle_action("special")[0])

    def test_quest_completes_after_wins(self):
        game = make_game()
        game.accept_quest()
        for _ in range(QUEST_TARGET):
            game.start_battle()
            game.enemy.hp = 1
            game.enemy.defense = 0
            while game.in_battle:
                game.battle_action("attack")
            game.player.hp = game.player.max_hp
        self.assertEqual(game.quest_status, "done")

    def test_death_penalty(self):
        game = make_game()
        game.player.gold = 20
        game.start_battle()
        game.player.hp = 1
        game.enemy.attack = 500
        game.enemy.hp = game.enemy.max_hp = 10_000
        while game.in_battle:
            game.battle_action("attack")
        self.assertEqual(game.last_result, "dead")
        self.assertEqual(game.player.gold, 10)
        self.assertEqual(game.player.hp, game.player.max_hp)


if __name__ == "__main__":
    unittest.main()
