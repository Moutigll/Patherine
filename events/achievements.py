from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from commands import bot

from utils.i18n import i18n
from utils.utils import log

# -----------------------------
# Config
# -----------------------------
NOTABLE_THRESHOLDS: list[int] = [10, 25, 42, 50, 69, 420]

# Optional milestone messages (can contain emojis)
MILESTONE_MESSAGES: dict[int, str] = {
	10: "achievements.count.c10",
	42: "achievements.count.c42",
	69: "achievements.count.c69",
	420: "achievements.count.c420"
}

todayMilestoneCache = {}

# -----------------------------
# Count helpers using precomputed tables
# -----------------------------
def getUserSuccessCount(cursor, userId: int) -> int:
	"""Return total 'success' messages sent by a user."""
	cursor.execute(
		"SELECT COUNT(*) FROM messages WHERE user_id = ? AND category = 'success'",
		(userId,)
	)
	row = cursor.fetchone()
	return row[0] if row else 0


def getChannelSuccessCount(cursor, channelId: int) -> int:
	"""Return total 'success' messages in a channel."""
	cursor.execute(
		"SELECT COUNT(*) FROM messages WHERE channel_id = ? AND category = 'success'",
		(channelId,)
	)
	row = cursor.fetchone()
	return row[0] if row else 0


def getTotalSuccessCount(cursor) -> int:
	"""Return global total 'success' messages."""
	cursor.execute("SELECT COUNT(*) FROM messages WHERE category = 'success'")
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
	if (count % 365) == 0 and count != 0:
		return True
	return count in NOTABLE_THRESHOLDS or (count % 100 == 0 and count != 0)

def getMilestoneMessage(count: int, l) -> str:
	"""Return the custom message for a milestone, fallback if none exists."""
	if count % 365 == 0:
		return f"{count // 365} {i18n.t(l, "achievements.count.genY")}"
	return i18n.t(l, MILESTONE_MESSAGES.get(count, "achievements.count.gen"))


# -----------------------------
# Achievement handler
# -----------------------------
async def handleAchievements(conn, cursor, internalId: int, userId: int, tzName: str, message, l):
	"""
	Check notable milestones and send congrats messages.

	Priority:
	1. User milestones (count or streak) → same channel
	2. Channel milestones → same channel
	3. Global milestones → broadcast to all channels
	"""
	global todayMilestoneCache

	# Clean up cache for previous days
	today = datetime.now().date()
	todayMilestoneCache.update({
		key: val for key, val in todayMilestoneCache.items()
		if key[2] == today
	})

	# Fetch counts and streaks
	userCount = getUserSuccessCount(cursor, userId)
	userStreak = getUserCurrentStreak(cursor, userId, tzName)
	channelCount = getChannelSuccessCount(cursor, internalId)
	channelStreak = getChannelCurrentStreak(cursor, internalId)
	totalCount = getTotalSuccessCount(cursor)
	totalStreak = getGlobalCurrentStreak(cursor)

	# --- User milestones ---
	if (isMilestone(userCount) or isMilestone(userStreak)) and (("user", userId, datetime.now().date()) not in todayMilestoneCache):
		parts = []
		if isMilestone(userCount):
			parts.append(f"{i18n.t(l, 'achievements.user.msg.p1')} **{userCount}** {i18n.t(l, 'achievements.user.msg.p2')}")
		if isMilestone(userStreak):
			parts.append(f"🔥 {i18n.t(l, 'achievements.user.streak.p1')} **{userStreak}** {i18n.t(l, 'achievements.user.streak.p2')}\n")
			if not isMilestone(userCount):
				parts.append(getMilestoneMessage(userStreak))

		content = f"{i18n.t(l, 'achievements.user.congrats')} {message.author.mention}! {' — '.join(parts)}"
		todayMilestoneCache[("user", userId, datetime.now().date())] = True
		try:
			await message.channel.send(content)
		except Exception as e:
			log(f"Failed to send congrats in channel {message.channel.id}: {e}")
		return

	# --- Channel milestones (send only in this channel) ---
	if (isMilestone(channelCount) or isMilestone(channelStreak)) and (("channel", internalId, datetime.now().date()) not in todayMilestoneCache):
		parts = []
		if isMilestone(channelCount):
			parts.append(f"{i18n.t(l, 'achievements.channel.msg.p1')} **{channelCount}** 🎊\n{getMilestoneMessage(channelCount)}")
		if isMilestone(channelStreak):
			parts.append(f"🔥 {i18n.t(l, 'achievements.channel.streak.p1')} **{channelStreak}** {i18n.t(l, 'achievements.channel.streak.p2')}\n")
			if not isMilestone(channelCount):
				parts.append(getMilestoneMessage(channelStreak))

		content = " / ".join(parts)
		todayMilestoneCache[("channel", internalId, datetime.now().date())] = True
		try:
			await message.channel.send(content)
		except Exception as e:
			log(f"Failed to send channel milestone in {message.channel.id}: {e}")
		return

	# --- Global milestones (broadcast) ---
	if (isMilestone(totalCount) or isMilestone(totalStreak)) and (("global", 0, datetime.now().date()) not in todayMilestoneCache):
		parts = []
		if isMilestone(totalCount):
			parts.append(f"{i18n.t(l, 'achievements.global.msg.p1')} **{totalCount}** 🎊\n{getMilestoneMessage(totalCount)}")
		if isMilestone(totalStreak):
			parts.append(f"🔥 {i18n.t(l, 'achievements.global.streak.p1')} **{totalStreak}** {i18n.t(l, 'achievements.channel.streak.p2')}\n")
			if not isMilestone(totalCount):
				parts.append(getMilestoneMessage(totalStreak))

		content = " / ".join(parts)

		todayMilestoneCache[("global", 0, datetime.now().date())] = True
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
