import discord
from discord import app_commands
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from commands import FOOTER_TEXT, statGroup
from utils.utils import connectDb, escapeMarkdown


DEFAULT_CUTOFF = time(12, 7)


# -----------------------------
# Helpers
# -----------------------------
def addCondition(baseWhere, newCond):
	"""Combine WHERE conditions safely."""
	return f"{baseWhere} AND {newCond}" if baseWhere else f"WHERE {newCond}"


def getUserTimezone(cursor, userId: str) -> timezone:
	cursor.execute("SELECT timezone FROM users WHERE discord_user_id = ?", (userId,))
	row = cursor.fetchone()
	if row and row[0]:
		try:
			return ZoneInfo(row[0])
		except Exception:
			pass
	return timezone.utc


def fetchStreak(cursor, table: str, whereClause: str = "", params=()) -> tuple[int, int, date | None]:
	"""
	Fetch current_streak, max_streak, last_success_date from the precomputed streak tables.
	Supports: user_streaks, channel_streaks, global_streak
	"""
	if table == "user_streaks" and "user_id" in whereClause:
		cursor.execute("""
			SELECT current_streak, max_streak, last_success_date
			  FROM user_streaks
			 WHERE user_id = (SELECT id FROM users WHERE discord_user_id = ?)
		""", params)
	elif table == "channel_streaks" and "channel_id" in whereClause:
		cursor.execute("""
			SELECT current_streak, max_streak, last_success_date
			  FROM channel_streaks
			 WHERE channel_id = (SELECT id FROM channels WHERE discord_channel_id = ?)
		""", params)
	else:
		cursor.execute("SELECT current_streak, max_streak, last_success_date FROM global_streak LIMIT 1")
	row = cursor.fetchone()
	if row:
		current, best, lastDateIso = row[0], row[1], row[2]
		lastDay = datetime.fromisoformat(lastDateIso).date() if lastDateIso else None
		return current, best, lastDay
	return 0, 0, None


def computeStreakString(current: int, best: int, lastDay: date | None, tz: timezone) -> str:
	"""Compute streak string, flame only if current == max, same logic as before."""
	now = datetime.now(tz)
	today = now.date()
	if lastDay and (today == lastDay or (today == lastDay + timedelta(days=1) and now.time() < DEFAULT_CUTOFF)):
		currentStreak = current
	else:
		currentStreak = 0
	if currentStreak == best and best > 0:
		return f"🔥 {best} days"
	return f"{best} days (current: {currentStreak})"


def calculateDelays(timestamps):
	"""Returns the delay in seconds from the start of the minute for each timestamp."""
	delays = [ts.second + ts.microsecond / 1_000_000 for ts in timestamps]
	if not delays:
		return 0, 0, 0
	return min(delays), sum(delays) / len(delays), max(delays)


# -----------------------------
# Stats Embed
# -----------------------------
async def sendStatsEmbed(interaction, title, whereClause="", params=(), isUser=False):
	conn, cursor = connectDb()
	try:
		# --- Messages counts ---
		cursor.execute(f"""
			SELECT category, COUNT(*) 
			FROM messages m
			{whereClause}
			GROUP BY category
		""", params)
		categoryCounts = {row[0]: row[1] for row in cursor.fetchall()}

		# --- Reactions counts ---
		cursor.execute(f"""
			SELECT COUNT(*)
			FROM reactions r
			JOIN messages m ON r.message_id = m.id
			{whereClause.replace("m.", "m.")}
		""", params)
		totalReceived = cursor.fetchone()[0]

		totalGiven = None
		if isUser:
			cursor.execute("""
				SELECT COUNT(*)
				  FROM reactions r
				 WHERE r.user_id = (
				   SELECT id FROM users WHERE discord_user_id = ?
				 )
			""", params)
			totalGiven = cursor.fetchone()[0]
			reactionsStr = f"Received: {totalReceived} 💜\nGiven: {totalGiven} 💜"
			userTz = getUserTimezone(cursor, params[0])
		else:
			reactionsStr = f"{totalReceived} 💜"
			userTz = timezone.utc

		# --- Streaks ---
		if isUser:
			current, best, lastDay = fetchStreak(cursor, "user_streaks", whereClause, params)
		elif "channel_id" in whereClause:
			current, best, lastDay = fetchStreak(cursor, "channel_streaks", whereClause, params)
		else:
			current, best, lastDay = fetchStreak(cursor, "global_streak")

		streakStr = computeStreakString(current, best, lastDay, userTz)

		# --- Success delays ---
		streakWhere = addCondition(whereClause, "m.category = 'success'")
		cursor.execute(f"""
			SELECT m.timestamp
			FROM messages m
			{streakWhere}
		""", params)
		timestamps = [datetime.fromisoformat(r[0]) for r in cursor.fetchall()]
		minD, avgD, maxD = calculateDelays(timestamps)

	finally:
		conn.close()

	embed = discord.Embed(title=title, color=discord.Color.purple())
	embed.add_field(
		name="📥 Messages",
		value=(
			f"• Fail:	{categoryCounts.get('fail', 0)}\n"
			f"• Success: {categoryCounts.get('success', 0)}\n"
			f"• Choke:   {categoryCounts.get('choke', 0)}"
		),
		inline=False
	)
	embed.add_field(name="💜 Reactions", value=reactionsStr, inline=False)
	embed.add_field(name="🔥 Streak", value=streakStr, inline=False)
	embed.add_field(
		name="⏱️ Success delay (sec)",
		value=(
			f"min: {minD:.3f}\n"
			f"avg: {avgD:.3f}\n"
			f"max: {maxD:.3f}"
		),
		inline=False
	)
	embed.add_field(name="", value=FOOTER_TEXT)

	await interaction.response.send_message(embed=embed, ephemeral=True)


# -----------------------------
# Commands
# -----------------------------
@statGroup.command(name="global", description="Global stats across all channels")
async def globalStats(interaction: discord.Interaction):
	await sendStatsEmbed(interaction, "📊 Global statistics")

@statGroup.command(name="channel", description="Stats for a specific channel")
@app_commands.describe(channel="The channel to analyze")
async def channelStats(interaction: discord.Interaction, channel: discord.TextChannel):
	where = "WHERE m.channel_id = (SELECT id FROM channels WHERE discord_channel_id = ?)"
	params = (str(channel.id),)
	await sendStatsEmbed(interaction, f"📊 Stats for {channel.mention}", where, params)

@statGroup.command(name="me", description="Your personal stats")
async def myStats(interaction: discord.Interaction):
	userId = str(interaction.user.id)
	where = "WHERE m.user_id = (SELECT id FROM users WHERE discord_user_id = ?)"
	params = (userId,)
	await sendStatsEmbed(interaction, "📊 My statistics", where, params, isUser=True)

@statGroup.command(name="user", description="Stats for a specific user")
@app_commands.describe(user="The user to analyze")
async def userStats(interaction: discord.Interaction, user: discord.User):
	where = "WHERE m.user_id = (SELECT id FROM users WHERE discord_user_id = ?)"
	params = (str(user.id),)
	await sendStatsEmbed(interaction, f"📊 Stats for {escapeMarkdown(user.name)}", where, params, isUser=True)
