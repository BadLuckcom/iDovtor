import aiosqlite
import datetime

DB_FILE = 'managers.db'

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS managers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            photo_id TEXT,
            rating REAL DEFAULT 0,
            total_votes INTEGER DEFAULT 0
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manager_id INTEGER NOT NULL,
            stars INTEGER NOT NULL,
            comment TEXT,
            timestamp TEXT
        )
        """)
        await db.commit()

async def get_managers():
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT id, name, photo_id, rating, total_votes FROM managers")
        rows = await cursor.fetchall()
        await cursor.close()
        return rows

async def add_manager(name, photo_id):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO managers (name, photo_id, rating, total_votes) VALUES (?, ?, 0, 0)",
            (name, photo_id)
        )
        await db.commit()

async def delete_manager(manager_id):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM ratings WHERE manager_id = ?", (manager_id,))
        await db.execute("DELETE FROM managers WHERE id = ?", (manager_id,))
        await db.commit()

async def add_rating(manager_id, stars):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "INSERT INTO ratings (manager_id, stars, comment, timestamp) VALUES (?, ?, ?, ?)",
            (manager_id, stars, "", timestamp)
        )
        rating_id = cursor.lastrowid
        await cursor.close()
        await db.commit()

        cursor = await db.execute(
            "SELECT rating, total_votes FROM managers WHERE id = ?",
            (manager_id,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row:
            current_rating, total_votes = row
            new_total = total_votes + 1
            new_rating = stars if total_votes == 0 else (current_rating * total_votes + stars) / new_total
            await db.execute(
                "UPDATE managers SET rating = ?, total_votes = ? WHERE id = ?",
                (new_rating, new_total, manager_id)
            )
            await db.commit()
        return rating_id

async def update_rating_comment(rating_id, comment):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE ratings SET comment = ? WHERE id = ?",
            (comment, rating_id)
        )
        await db.commit()

async def get_all_ratings():
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT id, manager_id, stars, comment, timestamp FROM ratings")
        rows = await cursor.fetchall()
        await cursor.close()
        return rows