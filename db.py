import os
import sqlite3
from contextlib import closing

DB_PATH = os.getenv("DB_PATH", "coinflip.db")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(_conn()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id            INTEGER PRIMARY KEY,
                chat_id            INTEGER NOT NULL,
                wins               INTEGER NOT NULL DEFAULT 0,
                losses             INTEGER NOT NULL DEFAULT 0,
                streak             INTEGER NOT NULL DEFAULT 0,
                best_streak        INTEGER NOT NULL DEFAULT 0,
                day_streak         INTEGER NOT NULL DEFAULT 0,
                last_play_date     TEXT,
                reminders_on       INTEGER NOT NULL DEFAULT 1,
                last_reminded_date TEXT
            )
            """
        )


def get_user(user_id: int, chat_id: int) -> dict:
    """Return the user row as a dict, creating it on first contact."""
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, chat_id) VALUES (?, ?)",
            (user_id, chat_id),
        )
        conn.execute(
            "UPDATE users SET chat_id = ? WHERE user_id = ?", (chat_id, user_id)
        )
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row)


def save_game_state(user: dict) -> None:
    with closing(_conn()) as conn, conn:
        conn.execute(
            """
            UPDATE users
            SET wins = ?, losses = ?, streak = ?, best_streak = ?,
                day_streak = ?, last_play_date = ?
            WHERE user_id = ?
            """,
            (
                user["wins"],
                user["losses"],
                user["streak"],
                user["best_streak"],
                user["day_streak"],
                user["last_play_date"],
                user["user_id"],
            ),
        )


def reset_stats(user_id: int) -> None:
    with closing(_conn()) as conn, conn:
        conn.execute(
            """
            UPDATE users
            SET wins = 0, losses = 0, streak = 0, best_streak = 0,
                day_streak = 0, last_play_date = NULL
            WHERE user_id = ?
            """,
            (user_id,),
        )


def set_reminders(user_id: int, on: bool) -> None:
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE users SET reminders_on = ? WHERE user_id = ?",
            (1 if on else 0, user_id),
        )


def users_to_remind(today: str) -> list[dict]:
    """Users with reminders on who haven't played or been reminded today."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            """
            SELECT * FROM users
            WHERE reminders_on = 1
              AND (last_play_date IS NULL OR last_play_date != ?)
              AND (last_reminded_date IS NULL OR last_reminded_date != ?)
            """,
            (today, today),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_reminded(user_id: int, today: str) -> None:
    with closing(_conn()) as conn, conn:
        conn.execute(
            "UPDATE users SET last_reminded_date = ? WHERE user_id = ?",
            (today, user_id),
        )
