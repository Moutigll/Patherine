from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from utils.utils import connectDb

CHANNEL_DEFAULT_TZ = ZoneInfo("Europe/Paris")
CUTOFF_TIME = time(12, 7)

def calculateStreak(dates, now):
	"""Calculates max streak and current streak from a sorted list of dates."""
	if not dates:
		return 0, 0, None

	max_streak = running = 1
	for i in range(1, len(dates)):
		if dates[i] == dates[i-1] + timedelta(days=1):
			running += 1
			max_streak = max(max_streak, running)
		else:
			running = 1

	# Current streak
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
	conn, _ = connectDb()

	# -------------------
	# Channel streaks
	# -------------------
	cursor.execute("SELECT id, timezone FROM channels")
	channels = cursor.fetchall()

	for channel_id, tz_str in channels:
		channel_tz = ZoneInfo(tz_str) if tz_str else CHANNEL_DEFAULT_TZ

		cursor.execute("""
			SELECT DISTINCT DATE(timestamp)
			FROM messages
			WHERE channel_id = ? AND category = 'success'
			ORDER BY DATE(timestamp)
		""", (channel_id,))
		rows = cursor.fetchall()
		dates = [datetime.fromisoformat(r[0]).date() for r in rows]

		max_streak, current_streak, last_date = calculateStreak(dates, datetime.now(channel_tz))
		if last_date is None:
			continue

		cursor.execute("""
			INSERT INTO channel_streaks(channel_id, current_streak, max_streak, last_success_date)
			VALUES (?, ?, ?, ?)
			ON CONFLICT(channel_id) DO UPDATE SET
				current_streak = excluded.current_streak,
				max_streak = excluded.max_streak,
				last_success_date = excluded.last_success_date
		""", (channel_id, current_streak, max_streak, last_date.isoformat()))

	# -------------------
	# Global streak
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
		# Global streak: table with single row
		cursor.execute("""
			INSERT INTO global_streak(id, current_streak, max_streak, last_success_date)
			VALUES (1, ?, ?, ?)
			ON CONFLICT(id) DO UPDATE SET
				current_streak = excluded.current_streak,
				max_streak = excluded.max_streak,
				last_success_date = excluded.last_success_date
		""", (current_streak, max_streak, last_date.isoformat()))
