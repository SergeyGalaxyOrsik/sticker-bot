import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class Storage:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_packs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  title TEXT NOT NULL,
                  short_name TEXT NOT NULL,
                  format TEXT NOT NULL CHECK (format IN ('static','video')),
                  created_on_telegram INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE(user_id, title),
                  UNIQUE(short_name)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS active_pack (
                  user_id INTEGER PRIMARY KEY,
                  pack_id INTEGER NOT NULL,
                  FOREIGN KEY(pack_id) REFERENCES user_packs(id) ON DELETE CASCADE
                )
                """
            )
            conn.commit()

    def _now(self) -> str:
        return datetime.utcnow().isoformat()

    def create_pack_record(self, user_id: int, title: str, short_name: str, fmt: str) -> Dict[str, Any]:
        with self._connect() as conn:
            now = self._now()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO user_packs (user_id, title, short_name, format, created_on_telegram, created_at, updated_at)
                VALUES (?, ?, ?, ?, 0, ?, ?)
                """,
                (user_id, title, short_name, fmt, now, now),
            )
            pack_id = cur.lastrowid
            conn.commit()
            return self.get_pack_by_id(pack_id)  # type: ignore[return-value]

    def ensure_pack_record(self, user_id: int, title: str, short_name: str, fmt: str) -> Dict[str, Any]:
        pack = self.get_pack_by_user_and_title(user_id, title)
        if pack is not None:
            return pack
        return self.create_pack_record(user_id, title, short_name, fmt)

    def get_pack_by_id(self, pack_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM user_packs WHERE id = ?", (pack_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_pack_by_user_and_title(self, user_id: int, title: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM user_packs WHERE user_id = ? AND title = ?",
                (user_id, title),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_pack_by_short_name(self, short_name: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM user_packs WHERE short_name = ?", (short_name,))
            row = cur.fetchone()
            return dict(row) if row else None

    def find_pack_by_title_or_short(self, user_id: int, query: str) -> Optional[Dict[str, Any]]:
        pack = self.get_pack_by_user_and_title(user_id, query)
        if pack is not None:
            return pack
        return self.get_pack_by_short_name(query)

    def set_active_pack(self, user_id: int, pack_id: int) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO active_pack (user_id, pack_id) VALUES (?, ?)\n"
                "ON CONFLICT(user_id) DO UPDATE SET pack_id=excluded.pack_id",
                (user_id, pack_id),
            )
            conn.commit()

    def get_active_pack(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT p.* FROM user_packs p JOIN active_pack a ON p.id = a.pack_id WHERE a.user_id = ?",
                (user_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_packs(self, user_id: int) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM user_packs WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def mark_created_on_telegram(self, pack_id: int, short_name: Optional[str] = None) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            params: Tuple[Any, ...]
            if short_name is not None:
                cur.execute(
                    "UPDATE user_packs SET created_on_telegram=1, short_name=?, updated_at=? WHERE id=?",
                    (short_name, self._now(), pack_id),
                )
            else:
                cur.execute(
                    "UPDATE user_packs SET created_on_telegram=1, updated_at=? WHERE id=?",
                    (self._now(), pack_id),
                )
            conn.commit()

    def update_title(self, pack_id: int, new_title: str) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE user_packs SET title=?, updated_at=? WHERE id=?",
                (new_title, self._now(), pack_id),
            )
            conn.commit()

    def update_format(self, pack_id: int, fmt: str) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE user_packs SET format=?, updated_at=? WHERE id=?",
                (fmt, self._now(), pack_id),
            )
            conn.commit()

