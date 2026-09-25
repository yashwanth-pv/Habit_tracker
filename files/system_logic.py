"""
system_logic.py
----------------
Pure game-logic functions for the System: XP curve, ranks, leveling,
quest completion, and penalty handling. No Streamlit or I/O here —
keeps it testable and easy to tweak.
"""

from __future__ import annotations

import datetime as dt
import uuid

RANKS = ["E", "D", "C", "B", "A", "S"]

DEFAULT_STATS = {"STR": 10, "VIT": 10, "AGI": 10, "INT": 10, "PER": 10}

STAT_LABELS = {
    "STR": "Strength",
    "VIT": "Vitality",
    "AGI": "Agility",
    "INT": "Intelligence",
    "PER": "Perception",
}


def xp_to_next_level(level: int) -> int:
    """XP required to go from `level` to `level + 1`. Gentle exponential curve."""
    return int(100 * (1.12 ** (level - 1)))


def rank_for_level(level: int) -> str:
    thresholds = [1, 10, 20, 35, 50, 75]  # level at which each rank begins
    rank = "E"
    for r, t in zip(RANKS, thresholds):
        if level >= t:
            rank = r
    return rank


def new_player(name: str = "Player") -> dict:
    return {
        "name": name,
        "title": "Awakened",
        "level": 1,
        "xp": 0,
        "stat_points": 0,
        "stats": dict(DEFAULT_STATS),
        "created": dt.date.today().isoformat(),
    }


def default_quests() -> list[dict]:
    """A starter daily quest board, in the spirit of a certain iconic system."""
    def q(name, desc, xp, stats, category="daily"):
        return {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "description": desc,
            "xp": xp,
            "stat_rewards": stats,
            "category": category,  # "daily" | "main" | "custom"
            "streak": 0,
            "last_completed": None,  # ISO date string
        }

    return [
        q("Push-Ups", "Complete 100 push-ups.", 20, {"STR": 1}),
        q("Sit-Ups", "Complete 100 sit-ups.", 20, {"VIT": 1}),
        q("Squats", "Complete 100 squats.", 20, {"AGI": 1}),
        q("Run", "Run 10 kilometers.", 30, {"VIT": 1, "AGI": 1}),
        q("Read / Study", "Spend 30 minutes learning something new.", 15, {"INT": 1}),
        q("Focus Block", "One distraction-free 25-minute deep work session.", 15, {"PER": 1}),
    ]


def today_str() -> str:
    return dt.date.today().isoformat()


def is_completed_today(quest: dict) -> bool:
    return quest.get("last_completed") == today_str()


def complete_quest(player: dict, quest: dict) -> list[str]:
    """Mark a quest done for today, grant XP + stat rewards, apply level-ups.
    Returns a list of human-readable event messages (for toasts/log)."""
    events: list[str] = []
    if is_completed_today(quest):
        return events

    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    quest["streak"] = quest["streak"] + 1 if quest.get("last_completed") == yesterday else 1
    quest["last_completed"] = today_str()

    player["xp"] += quest["xp"]
    events.append(f"+{quest['xp']} XP from '{quest['name']}'")

    for stat, amount in quest.get("stat_rewards", {}).items():
        player["stats"][stat] = player["stats"].get(stat, 0) + amount
        events.append(f"+{amount} {STAT_LABELS.get(stat, stat)}")

    events += _apply_level_ups(player)
    return events


def _apply_level_ups(player: dict) -> list[str]:
    events = []
    while player["xp"] >= xp_to_next_level(player["level"]):
        player["xp"] -= xp_to_next_level(player["level"])
        player["level"] += 1
        player["stat_points"] += 3
        new_rank = rank_for_level(player["level"])
        events.append(f"LEVEL UP! You are now Level {player['level']}.")
        if new_rank != player.get("_last_rank"):
            events.append(f"Rank up available: {new_rank}-Rank")
            player["_last_rank"] = new_rank
    return events


def apply_daily_penalty(player: dict, quests: list[dict]) -> list[str]:
    """Called once per day (on first load of a new day) for quests that were
    missed the PREVIOUS day. Docks a small amount of XP and breaks streaks —
    the System is not kind to those who neglect their quests."""
    events = []
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    day_before = (dt.date.today() - dt.timedelta(days=2)).isoformat()

    for quest in quests:
        if quest["category"] != "daily":
            continue
        last = quest.get("last_completed")
        # Missed yesterday if it wasn't completed yesterday AND the quest
        # already existed before yesterday (avoid penalizing brand-new quests).
        if last != yesterday and last is not None and last <= day_before:
            if quest["streak"] > 0:
                quest["streak"] = 0
                events.append(f"Penalty: streak reset for '{quest['name']}' (missed quest)")
            penalty_xp = max(5, quest["xp"] // 4)
            if player["xp"] >= penalty_xp:
                player["xp"] -= penalty_xp
            events.append(f"Penalty: -{penalty_xp} XP for missing '{quest['name']}'")
    return events


def allocate_stat_point(player: dict, stat: str) -> bool:
    if player["stat_points"] <= 0:
        return False
    if stat not in player["stats"]:
        return False
    player["stats"][stat] += 1
    player["stat_points"] -= 1
    return True


def add_custom_quest(quests: list[dict], name: str, description: str, xp: int, stat: str) -> dict:
    quest = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "description": description,
        "xp": xp,
        "stat_rewards": {stat: 1} if stat else {},
        "category": "custom",
        "streak": 0,
        "last_completed": None,
    }
    quests.append(quest)
    return quest
