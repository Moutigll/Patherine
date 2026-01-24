from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from utils.utils import connectDb

CHANNEL_DEFAULT_TZ = ZoneInfo("Europe/Paris")
CUTOFF_TIME = time(12, 7)

def calculateStreak(dates, now):
	if not dates:
		return 0, 0, None

	max_streak = running = 1
	for i in range(1, len(dates)):
		if dates[i] == dates[i-1] + timedelta(days=1):
			running += 1
			max_streak = max(max_streak, running)
		else:
			running = 1

	current_streak = 0
	last_date = dates[-1]
	today = now.date()
	if last_date == today or (last_date == today - timedelta(days=1) and now.time() < CUTOFF_TIME):
		streak = 1
		for i in range(len(dates)-2, -1, -1):
			if dates[i+1] == dates[i] + timedelta(days=1):
				streak += 1
			else:
				break
		current_streak = streak

	return max_streak, current_streak, last_date

def up(cursor):
	# -------------------
	# Keep only the most recent row
	# -------------------
	cursor.execute("""
		DELETE FROM global_streak
		WHERE rowid NOT IN (
			SELECT rowid FROM global_streak
			ORDER BY last_success_date DESC
			LIMIT 1
		)
	""")

	# -------------------
	# Add id column if missing and set it to 1
	# -------------------
	cursor.execute("PRAGMA table_info(global_streak)")
	columns = [row[1] for row in cursor.fetchall()]
	if "id" not in columns:
		cursor.execute("ALTER TABLE global_streak ADD COLUMN id INTEGER DEFAULT 1")

	# Make sure the single remaining row has id = 1
	cursor.execute("UPDATE global_streak SET id = 1")

	# Create unique index now
	cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_global_streak_id ON global_streak(id)")

	# -------------------
	# Recompute global streak from messages
	# -------------------
	cursor.execute("""
		SELECT DISTINCT DATE(timestamp)
		FROM messages
		WHERE category = 'success'
		ORDER BY DATE(timestamp)
	""")
	rows = cursor.fetchall()
	dates = [datetime.fromisoformat(r[0]).date() for r in rows]
	now = datetime.now(CHANNEL_DEFAULT_TZ)
	max_streak, current_streak, last_date = calculateStreak(dates, now)

	if last_date:
		cursor.execute("""
			INSERT INTO global_streak(id, current_streak, max_streak, last_success_date)
			VALUES (1, ?, ?, ?)
			ON CONFLICT(id) DO UPDATE SET
				current_streak = excluded.current_streak,
				max_streak = excluded.max_streak,
				last_success_date = excluded.last_success_date
		""", (current_streak, max_streak, last_date.isoformat()))
