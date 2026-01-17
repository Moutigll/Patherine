from utils.utils import connectDb

def createDb():
	conn, cursor = connectDb()

	cursor.execute("""
	CREATE TABLE IF NOT EXISTS channels (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		discord_channel_id TEXT NOT NULL UNIQUE,
		discord_role_id TEXT,
		timezone TEXT DEFAULT 'Europe/Paris'
	);
	""")

	cursor.execute("""
	CREATE TABLE IF NOT EXISTS users (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		discord_user_id TEXT NOT NULL UNIQUE,
		timezone TEXT DEFAULT 'Europe/Paris'
	);
	""")

	cursor.execute("""
	CREATE TABLE IF NOT EXISTS messages (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		message_id TEXT NOT NULL UNIQUE,
		channel_id INTEGER NOT NULL,
		user_id INTEGER NOT NULL,
		timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
		category TEXT DEFAULT 'unknown',
		FOREIGN KEY(channel_id) REFERENCES channels(id) ON DELETE CASCADE,
		FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
		UNIQUE(channel_id, user_id, message_id)
	);
	""")

	cursor.execute("""
	CREATE TABLE IF NOT EXISTS reactions (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		user_id INTEGER NOT NULL,
		message_id INTEGER NOT NULL,
		FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
		FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE,
		UNIQUE(user_id, message_id)
	);
	""")

	cursor.execute("""
	CREATE TABLE IF NOT EXISTS admins (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		discord_user_id TEXT NOT NULL UNIQUE
	);
	""")

	cursor.execute("""
	CREATE TABLE IF NOT EXISTS untracked_users (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		discord_user_id TEXT NOT NULL UNIQUE
	);
	""")

	cursor.execute("""
	CREATE TABLE IF NOT EXISTS user_streaks (
		user_id INTEGER PRIMARY KEY,
		current_streak INTEGER NOT NULL DEFAULT 0,
		max_streak INTEGER NOT NULL DEFAULT 0,
		last_success_date DATE NOT NULL,
		FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
	);
	""")

	conn.commit()
	conn.close()
	print("Database created successfully.")
