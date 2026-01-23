import importlib
from utils.utils import connectDb, log
import time

MIGRATIONS = [
	"001_create_user_streaks",
	"002_backfill_user_streaks",
	"003_backfill_channel_global_streaks",
	"004_add_lang_channels"
]

def runMigrations():
	conn, cursor = connectDb()

	# Ensure migration table exists
	cursor.execute(
		"""
		CREATE TABLE IF NOT EXISTS schema_migrations (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			name TEXT NOT NULL UNIQUE,
			applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
		);
		"""
	)

	cursor.execute("SELECT name FROM schema_migrations")
	applied = {row[0] for row in cursor.fetchall()}

	for migration in MIGRATIONS:
		if migration in applied:
			log(f"Skipping already applied migration {migration}")
			continue

		module = importlib.import_module(f"database.migrations.src.{migration}")

		log(f"Starting migration {migration}...")
		start_time = time.perf_counter()

		cursor.execute("BEGIN")
		try:
			module.up(cursor)
			cursor.execute(
				"INSERT INTO schema_migrations (name) VALUES (?)",
				(migration,)
			)
			cursor.execute("COMMIT")

			elapsed = time.perf_counter() - start_time
			log(f"Applied migration {migration} in {elapsed:.4f}s")
		except Exception:
			cursor.execute("ROLLBACK")
			log(f"Migration {migration} failed!")
			raise

	conn.close()