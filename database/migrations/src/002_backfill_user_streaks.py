from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from utils.utils import connectDb

CHANNEL_DEFAULT_TZ = ZoneInfo("Europe/Paris")  # fallback if channel tz not found
CUTOFF_TIME = time(12, 7) 

def up(cursor):
	"""Backfill user_streaks table from messages with correct current streaks."""
	cursor.execute("SELECT id, timezone FROM users")
	users = cursor.fetchall()

	for user_id, tz_str in users:
		userTz = ZoneInfo(tz_str) if tz_str else CHANNEL_DEFAULT_TZ

		# Get all success message dates for this user
		cursor.execute("""
			SELECT DISTINCT DATE(timestamp)
			FROM messages
			WHERE user_id = ? AND category = 'success'
			ORDER BY DATE(timestamp) ASC
		""", (user_id,))
		rows = cursor.fetchall()
		if not rows:
			continue

		dates = [datetime.fromisoformat(r[0]).date() for r in rows]

		# Max streak
		max_streak = 1
		running = 1
		for i in range(1, len(dates)):
			if dates[i] == dates[i-1] + timedelta(days=1):
				running += 1
				max_streak = max(max_streak, running)
			else:
				running = 1

		# Current streak
		now = datetime.now(userTz)
		today = now.date()
		last_date = dates[-1]
		current_streak = 0

		if last_date == today or (last_date == today - timedelta(days=1) and now.time() < CUTOFF_TIME):
			streak = 1
			for i in range(len(dates)-2, -1, -1):
				if dates[i+1] == dates[i] + timedelta(days=1):
					streak += 1
				else:
					break
			current_streak = streak

		# Insert or update
		cursor.execute("""
			INSERT INTO user_streaks(user_id, current_streak, max_streak, last_success_date)
			VALUES (?, ?, ?, ?)
			ON CONFLICT(user_id) DO UPDATE SET
				current_streak=excluded.current_streak,
				max_streak=excluded.max_streak,
				last_success_date=excluded.last_success_date
		""", (user_id, current_streak, max_streak, last_date.isoformat()))
