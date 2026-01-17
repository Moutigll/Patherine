from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from utils.utils import connectDb, log

# -----------------------------
# Config
# -----------------------------
NOTABLE_THRESHOLDS: list[int] = [10, 25, 42, 50, 69, 365, 420]

# Optional milestone messages (can contain emojis)
MILESTONE_MESSAGES: dict[int, str] = {
	10: "Keep going!",
	42: "You found the answer in Catherine!",
	69: "Nice!",
	365: "One whole year of caths, impressive!",
	420: "Keep cool man!"
}

FALLBACK_MESSAGE = "🎉 Congrats on hitting this milestone!"

# -----------------------------
# Count helpers using precomputed tables
# -----------------------------
def getUserSuccessCount(cursor, userId: int) -> int:
	"""Return total 'success' messages sent by a user from user_streaks."""
	cursor.execute(
		"SELECT current_streak + max_streak - current_streak FROM user_streaks WHERE user_id = ?",
		(userId,)
	)
	row = cursor.fetchone()
	return row[0] if row else 0


def getChannelSuccessCount(cursor, channelId: int) -> int:
	"""Return total 'success' messages in a channel from channel_streaks."""
	cursor.execute(
		"SELECT current_streak + max_streak - current_streak FROM channel_streaks WHERE channel_id = ?",
		(channelId,)
	)
	row = cursor.fetchone()
	return row[0] if row else 0


def getTotalSuccessCount(cursor) -> int:
	"""Return global total 'success' messages from global_streak."""
	cursor.execute("SELECT current_streak + max_streak - current_streak FROM global_streak LIMIT 1")
	row = cursor.fetchone()
	return row[0] if row else 0


def getUserCurrentStreak(cursor, userId: int, tzName: str) -> int:
	"""Return user's current consecutive-day streak from user_streaks."""
	cursor.execute(
		"SELECT current_streak, last_success_date FROM user_streaks WHERE user_id = ?",
		(userId,)
	)
	row = cursor.fetchone()
	if not row:
		return 0

	current, lastDateIso = row
	lastDay = datetime.fromisoformat(lastDateIso).date() if lastDateIso else None
	tz = ZoneInfo(tzName)
	today = datetime.now(tz).date()

	if lastDay and (today == lastDay or today == lastDay + timedelta(days=1)):
		return current
	return 0

def getChannelCurrentStreak(cursor, channelId: int) -> int:
	"""Return channel's current consecutive-day streak from channel_streaks."""
	cursor.execute(
		"SELECT current_streak, last_success_date FROM channel_streaks WHERE channel_id = ?",
		(channelId,)
	)
	row = cursor.fetchone()
	if not row:
		return 0

	current, lastDateIso = row
	lastDay = datetime.fromisoformat(lastDateIso).date() if lastDateIso else None
	today = datetime.now().date()

	if lastDay and (today == lastDay or today == lastDay + timedelta(days=1)):
		return current
	return 0

def getGlobalCurrentStreak(cursor) -> int:
	"""Return global current consecutive-day streak from global_streak."""
	cursor.execute("SELECT current_streak, last_success_date FROM global_streak LIMIT 1")
	row = cursor.fetchone()
	if not row:
		return 0

	current, lastDateIso = row
	lastDay = datetime.fromisoformat(lastDateIso).date() if lastDateIso else None
	today = datetime.now().date()

	if lastDay and (today == lastDay or today == lastDay + timedelta(days=1)):
		return current
	return 0

def isMilestone(count: int) -> bool:
	"""Return True if the count is a notable milestone."""
	return count in NOTABLE_THRESHOLDS or count % 100 == 0


def getMilestoneMessage(count: int) -> str:
	"""Return the custom message for a milestone, fallback if none exists."""
	return MILESTONE_MESSAGES.get(count, FALLBACK_MESSAGE)


# -----------------------------
# Achievement handler
# -----------------------------
async def handleAchievements(conn, cursor, internalId: int, userId: int, tzName: str, message):
	"""
	Check notable milestones and send congrats messages.

	Priority:
	1. User milestones (count or streak) → same channel
	2. Channel milestones → same channel
	3. Global milestones → broadcast to all channels
	"""

	# Fetch counts and streaks
	userCount = getUserSuccessCount(cursor, userId)
	userStreak = getUserCurrentStreak(cursor, userId, tzName)
	channelCount = getChannelSuccessCount(cursor, internalId)
	channelStreak = getChannelCurrentStreak(cursor, internalId)
	totalCount = getTotalSuccessCount(cursor)
	totalStreak = getGlobalCurrentStreak(cursor)  # idem, similaire pour global

	# --- User milestones ---
	if isMilestone(userCount) or isMilestone(userStreak):
		parts = []
		if isMilestone(userCount):
			parts.append(f"You've sent cath **{userCount}** times!\n{getMilestoneMessage(userCount)}")
		if isMilestone(userStreak):
			parts.append(f"🔥 Your streak reached **{userStreak}** consecutive days!\n")
			if not isMilestone(userCount):
				parts.append(getMilestoneMessage(userStreak))

		content = f"Congratulations {message.author.mention}! {' — '.join(parts)}"
		try:
			await message.channel.send(content)
		except Exception as e:
			log(f"Failed to send congrats in channel {message.channel.id}: {e}")
		return

	# --- Channel milestones (send only in this channel) ---
	if isMilestone(channelCount) or isMilestone(channelStreak):
		parts = []
		if isMilestone(channelCount):
			parts.append(f"Channel total of cath messages reached **{channelCount}** 🎊\n{getMilestoneMessage(channelCount)}")
		if isMilestone(channelStreak):
			parts.append(f"🔥 Channel streak reached **{channelStreak}** consecutive days!\n")
			if not isMilestone(channelCount):
				parts.append(getMilestoneMessage(channelStreak))

		content = " / ".join(parts)
		try:
			await message.channel.send(content)
		except Exception as e:
			log(f"Failed to send channel milestone in {message.channel.id}: {e}")
		return

	# --- Global milestones (broadcast) ---
	if isMilestone(totalCount) or isMilestone(totalStreak):
		parts = []
		if isMilestone(totalCount):
			parts.append(f"Global total of cath messages reached **{totalCount}** 🎊\n{getMilestoneMessage(totalCount)}")
		if isMilestone(totalStreak):
			parts.append(f"🔥 Global streak reached **{totalStreak}** consecutive days!\n")
			if not isMilestone(totalCount):
				parts.append(getMilestoneMessage(totalStreak))

		content = " / ".join(parts)

		cursor.execute("SELECT discord_channel_id FROM channels WHERE discord_channel_id IS NOT NULL")
		rows = cursor.fetchall()

		for (discordChannelId,) in rows:
			try:
				ch = bot.get_channel(int(discordChannelId))
				if ch:
					await ch.send(content)
			except Exception:
				try:
					ch = await bot.fetch_channel(int(discordChannelId))
					if ch:
						await ch.send(content)
				except Exception as e2:
					log(f"Failed to broadcast global milestone to channel {discordChannelId}: {e2}")
		return

	# No milestone reached → nothing to do
	return
