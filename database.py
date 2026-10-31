import aiosqlite

DB_PATH = "game.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                total_spins INTEGER DEFAULT 0,
                referrer_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS spins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_name TEXT,
                item_amount TEXT,
                rarity TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
                await db.commit()
                return {"user_id": user_id, "balance": 0, "total_spins": 0, "referrer_id": None}
            return dict(row)

async def add_balance(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        await db.commit()

async def save_spin(user_id: int, name: str, amount: str, rarity: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO spins (user_id, item_name, item_amount, rarity) VALUES (?,?,?,?)", (user_id, name, amount, rarity))
        await db.execute("UPDATE users SET total_spins = total_spins + 1 WHERE user_id=?", (user_id,))
        await db.commit()

async def set_referrer(user_id: int, referrer_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET referrer_id = ? WHERE user_id = ? AND referrer_id IS NULL", (referrer_id, user_id))
        await db.commit()