"""SQLite-based data layer for Chainlit thread persistence.

Implements BaseDataLayer to store users, threads, steps, elements,
and feedback in a local SQLite database.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import aiosqlite
import chainlit as cl
from chainlit.data import BaseDataLayer
from chainlit.element import ElementDict
from chainlit.step import StepDict
from chainlit.types import (
    Feedback,
    PageInfo,
    PaginatedResponse,
    Pagination,
    ThreadDict,
    ThreadFilter,
)
from chainlit.user import PersistedUser, User

DB_PATH = "chainlit_data.sqlite"

_STEP_DEFAULTS = {
    "input": "",
    "output": "",
    "name": "",
    "type": "undefined",
    "id": "",
    "threadId": "",
    "parentId": None,
    "streaming": False,
    "metadata": {},
    "tags": None,
    "isError": False,
    "waitForAnswer": False,
    "createdAt": None,
    "start": None,
    "end": None,
}

# Status messages injected by the UI that shouldn't appear on resume
_STATUS_KEYWORDS = ("Nghiên cứu hoàn tất", "Đang nghiên cứu")


class SQLiteDataLayer(BaseDataLayer):
    """Lightweight SQLite data layer for persisting threads & messages."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def _get_db(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db = await aiosqlite.connect(self.db_path)
            self._db.row_factory = aiosqlite.Row
            await self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    identifier TEXT UNIQUE NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    user_id TEXT,
                    metadata TEXT DEFAULT '{}',
                    tags TEXT DEFAULT '[]',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS steps (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT,
                    data TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS elements (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feedbacks (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                );
                """
            )
            await self._db.commit()
        return self._db

    def build_debug_url(self) -> str:
        return ""

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    # ── Helpers ──────────────────────────────────────────────────────

    async def _resolve_user_identifier(self, user_id: str) -> str:
        """Resolve a user UUID to their identifier string."""
        if not user_id:
            return ""
        db = await self._get_db()
        rows = await db.execute_fetchall(
            "SELECT identifier FROM users WHERE id = ?", (user_id,)
        )
        return rows[0]["identifier"] if rows else user_id

    @staticmethod
    def _normalize_step(step: dict) -> dict:
        """Ensure step dict has all required StepDict fields."""
        for key, default in _STEP_DEFAULTS.items():
            if key not in step:
                step[key] = default
        # Messages and tool steps must be top-level for the frontend to render
        # them on resume.  Tool steps are streamed with parent_id=status_msg.id;
        # that parent is gone by the time the thread is loaded again, so clear it
        # so they appear at the root level.
        step_type = step.get("type", "")
        if "message" in step_type or step_type == "tool":
            step["parentId"] = None
        return step

    @staticmethod
    def _filter_steps_for_resume(steps: list) -> list:
        """Keep renderable steps for thread resume (messages + tool steps)."""
        result = []
        for s in steps:
            step_type = s.get("type", "")
            # Keep messages and tool steps (tool calls, sub-agent responses)
            if "message" not in step_type and step_type != "tool":
                continue
            output = s.get("output", "")
            # Filter out status container messages (empty or status-keyword content)
            if not output.strip() and "message" in step_type:
                continue
            if any(kw in output for kw in _STATUS_KEYWORDS):
                continue
            result.append(s)
        return result

    async def _load_thread_steps(self, thread_id: str) -> list:
        """Load, normalize, and filter steps for a thread."""
        db = await self._get_db()
        step_rows = await db.execute_fetchall(
            "SELECT data FROM steps WHERE thread_id = ? ORDER BY created_at",
            (thread_id,),
        )
        raw = [self._normalize_step(json.loads(r["data"])) for r in step_rows]
        return self._filter_steps_for_resume(raw)

    async def _load_thread_elements(self, thread_id: str) -> list:
        """Load persisted elements for a thread."""
        db = await self._get_db()
        rows = await db.execute_fetchall(
            "SELECT data FROM elements WHERE thread_id = ?", (thread_id,)
        )
        elements = []
        for r in rows:
            el = json.loads(r["data"])
            # For local paths, verify file still exists
            if el.get("path") and not el.get("url"):
                import os
                if not os.path.isfile(el["path"]):
                    continue
            elements.append(el)
        return elements

    async def _build_thread_dict(self, row) -> ThreadDict:
        """Build a ThreadDict from a DB row."""
        steps = await self._load_thread_steps(row["id"])
        elements = await self._load_thread_elements(row["id"])
        user_identifier = await self._resolve_user_identifier(row["user_id"])
        return ThreadDict(
            id=row["id"],
            name=row["name"] or "New Chat",
            metadata=json.loads(row["metadata"] or "{}"),
            tags=json.loads(row["tags"] or "[]"),
            createdAt=row["created_at"],
            userId=row["user_id"],
            userIdentifier=user_identifier,
            steps=steps,
            elements=elements,
        )

    # ── Users ────────────────────────────────────────────────────────

    async def create_user(self, user: User) -> Optional[PersistedUser]:
        db = await self._get_db()
        user_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        await db.execute(
            "INSERT OR IGNORE INTO users (id, identifier, metadata, created_at) VALUES (?, ?, ?, ?)",
            (user_id, user.identifier, json.dumps(user.metadata or {}), now),
        )
        await db.commit()
        return await self.get_user(user.identifier)

    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        db = await self._get_db()
        rows = await db.execute_fetchall(
            "SELECT * FROM users WHERE identifier = ?", (identifier,)
        )
        if rows:
            r = rows[0]
            return PersistedUser(
                id=r["id"],
                identifier=r["identifier"],
                metadata=json.loads(r["metadata"]),
                createdAt=r["created_at"],
            )
        return None

    # ── Threads ──────────────────────────────────────────────────────

    async def list_threads(
        self, pagination: Pagination, filters: ThreadFilter
    ) -> PaginatedResponse[ThreadDict]:
        db = await self._get_db()
        query = "SELECT * FROM threads"
        params: list = []

        if filters.userId:
            query += " WHERE user_id = ?"
            params.append(filters.userId)

        query += " ORDER BY updated_at DESC"

        page_size = 20
        offset = int(pagination.cursor) if pagination.cursor else 0
        query += " LIMIT ? OFFSET ?"
        params.extend([page_size + 1, offset])

        rows = await db.execute_fetchall(query, params)
        threads = [await self._build_thread_dict(r) for r in rows[:page_size]]

        has_next = len(rows) > page_size
        return PaginatedResponse(
            data=threads,
            pageInfo=PageInfo(
                hasNextPage=has_next,
                startCursor="0",
                endCursor=str(offset + page_size) if has_next else None,
            ),
        )

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        db = await self._get_db()
        rows = await db.execute_fetchall(
            "SELECT * FROM threads WHERE id = ?", (thread_id,)
        )
        if not rows:
            return None
        return await self._build_thread_dict(rows[0])

    async def get_thread_author(self, thread_id: str) -> str:
        db = await self._get_db()
        rows = await db.execute_fetchall(
            "SELECT user_id FROM threads WHERE id = ?", (thread_id,)
        )
        if not rows or not rows[0]["user_id"]:
            return "anonymous"
        return await self._resolve_user_identifier(rows[0]["user_id"])

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ):
        db = await self._get_db()
        now = datetime.now().isoformat()
        existing = await db.execute_fetchall(
            "SELECT id FROM threads WHERE id = ?", (thread_id,)
        )
        if existing:
            updates = ["updated_at = ?"]
            params: list = [now]
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if user_id is not None:
                updates.append("user_id = ?")
                params.append(user_id)
            if metadata is not None:
                updates.append("metadata = ?")
                params.append(json.dumps(metadata))
            if tags is not None:
                updates.append("tags = ?")
                params.append(json.dumps(tags))
            params.append(thread_id)
            await db.execute(
                f"UPDATE threads SET {', '.join(updates)} WHERE id = ?", params
            )
        else:
            await db.execute(
                "INSERT INTO threads (id, name, user_id, metadata, tags, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    thread_id,
                    name or "New Chat",
                    user_id or "",
                    json.dumps(metadata or {}),
                    json.dumps(tags or []),
                    now,
                    now,
                ),
            )
        await db.commit()

    async def delete_thread(self, thread_id: str):
        db = await self._get_db()
        await db.execute("DELETE FROM steps WHERE thread_id = ?", (thread_id,))
        await db.execute("DELETE FROM elements WHERE thread_id = ?", (thread_id,))
        await db.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
        await db.commit()

    # ── Steps ────────────────────────────────────────────────────────

    async def create_step(self, step_dict: StepDict):
        db = await self._get_db()
        await db.execute(
            "INSERT OR REPLACE INTO steps (id, thread_id, data) VALUES (?, ?, ?)",
            (
                step_dict["id"],
                step_dict.get("threadId", ""),
                json.dumps(step_dict, default=str),
            ),
        )
        await db.commit()

    async def update_step(self, step_dict: StepDict):
        await self.create_step(step_dict)

    async def delete_step(self, step_id: str):
        db = await self._get_db()
        await db.execute("DELETE FROM steps WHERE id = ?", (step_id,))
        await db.commit()

    async def get_favorite_steps(self, user_id: str) -> List[StepDict]:
        return []

    # ── Elements ─────────────────────────────────────────────────────

    async def create_element(self, element: "cl.Element"):
        db = await self._get_db()
        # Convert local chart paths to /public/charts/ URL for persistence on resume
        element_url = getattr(element, "url", None)
        element_path = getattr(element, "path", None)
        if element_path and not element_url and element.type == "image":
            import os as _os
            name = _os.path.basename(element_path)
            if _os.path.isfile(element_path):
                element_url = f"/public/charts/{name}"
        data = {
            "id": element.id,
            "threadId": getattr(element, "thread_id", ""),
            "type": element.type,
            "name": element.name,
            "url": element_url,
            "path": element_path,
            "display": getattr(element, "display", "inline"),
            "size": getattr(element, "size", None),
            "mime": getattr(element, "mime", None),
            "forId": getattr(element, "for_id", None),
            "chainlitKey": getattr(element, "chainlit_key", None),
            "objectKey": getattr(element, "object_key", None),
        }
        await db.execute(
            "INSERT OR REPLACE INTO elements (id, thread_id, data) VALUES (?, ?, ?)",
            (element.id, getattr(element, "thread_id", ""), json.dumps(data)),
        )
        await db.commit()

    async def get_element(
        self, thread_id: str, element_id: str
    ) -> Optional[ElementDict]:
        db = await self._get_db()
        rows = await db.execute_fetchall(
            "SELECT data FROM elements WHERE id = ? AND thread_id = ?",
            (element_id, thread_id),
        )
        if rows:
            return json.loads(rows[0]["data"])
        return None

    async def delete_element(self, element_id: str, thread_id: Optional[str] = None):
        db = await self._get_db()
        await db.execute("DELETE FROM elements WHERE id = ?", (element_id,))
        await db.commit()

    # ── Feedback ─────────────────────────────────────────────────────

    async def upsert_feedback(self, feedback: Feedback) -> str:
        db = await self._get_db()
        fid = feedback.id or str(uuid.uuid4())
        await db.execute(
            "INSERT OR REPLACE INTO feedbacks (id, data) VALUES (?, ?)",
            (
                fid,
                json.dumps(
                    {
                        "id": fid,
                        "forId": feedback.forId,
                        "value": feedback.value,
                        "comment": feedback.comment,
                    }
                ),
            ),
        )
        await db.commit()
        return fid

    async def delete_feedback(self, feedback_id: str) -> bool:
        db = await self._get_db()
        await db.execute("DELETE FROM feedbacks WHERE id = ?", (feedback_id,))
        await db.commit()
        return True
