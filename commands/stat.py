import discord
from discord import app_commands
from datetime import datetime, timedelta

from commands import FOOTER_TEXT, statGroup
from utils.utils import connectDb


def addCondition(baseWhere, newCond):
	"""Combine WHERE conditions safely."""
	if baseWhere:
		return f"{baseWhere} AND {newCond}"
	return f"WHERE {newCond}"


def calculateStreak(dateStrings):
	"""Returns the longest streak (in days) of consecutive success dates."""
	if not dateStrings:
		return 0

	uniqueDays = sorted({datetime.fromisoformat(d).date() for d in dateStrings})
	maxStreak = currentStreak = 1

	for previous, current in zip(uniqueDays, uniqueDays[1:]):
		if current - previous == timedelta(days=1):
			currentStreak += 1
			maxStreak = max(maxStreak, currentStreak)
		else:
			currentStreak = 1

	return maxStreak


def calculateDelays(timestamps):
	"""Returns the delay in seconds from the start of the minute for each timestamp."""
	delays = [ts.second + ts.microsecond / 1_000_000 for ts in timestamps]
	if not delays:
		return 0, 0, 0
	return min(delays), sum(delays) / len(delays), max(delays)


async def sendStatsEmbed(interaction, title, whereClause="", params=()):
	conn, cursor = connectDb()

	cursor.execute(f"""
		SELECT category, COUNT(*) 
		FROM messages m
		{whereClause}
		GROUP BY category
	""", params)
	categoryCounts = {row[0]: row[1] for row in cursor.fetchall()}

	cursor.execute(f"""
		SELECT COUNT(*)
		FROM reactions r
		JOIN messages m ON r.message_id = m.id
		{whereClause.replace("m.", "m.")}
	""", params)
	totalReactions = cursor.fetchone()[0]

	streakWhere = addCondition(whereClause, "m.category = 'success'")
	cursor.execute(f"""
		SELECT DATE(m.timestamp)
		FROM messages m
		{streakWhere}
		ORDER BY DATE(m.timestamp)
	""", params)
	successDates = [row[0] for row in cursor.fetchall()]
	streak = calculateStreak(successDates)

	# Success delays
	cursor.execute(f"""
		SELECT m.timestamp
		FROM messages m
		{streakWhere}
	""", params)
	timestamps = [datetime.fromisoformat(row[0]) for row in cursor.fetchall()]
	minDelay, avgDelay, maxDelay = calculateDelays(timestamps)

	conn.close()

	embed = discord.Embed(title=title, color=discord.Color.purple())
	embed.add_field(
		name="📥 Messages",
		value=(
			f"• Fail: {categoryCounts.get('fail', 0)}\n"
			f"• Success: {categoryCounts.get('success', 0)}\n"
			f"• Choke: {categoryCounts.get('choke', 0)}"
		),
		inline=False
	)
	embed.add_field(name="💜 Reactions", value=str(totalReactions), inline=False)
	embed.add_field(name="🔥 Best streak", value=f"{streak} days", inline=False)
	embed.add_field(
		name="⏱️ Success delay (sec)",
		value=f"min: {minDelay:.3f}\n"
			  f"avg: {avgDelay:.3f}\n"
			  f"max: {maxDelay:.3f}",
		inline=False
	)

	embed.add_field(name="", value=FOOTER_TEXT)

	await interaction.response.send_message(embed=embed, ephemeral=True)


@statGroup.command(name="global", description="Global stats across all channels")
async def globalStats(interaction: discord.Interaction):
	"""Stats for all messages in all channels."""
	await sendStatsEmbed(interaction, "📊 Global statistics")


@statGroup.command(name="channel", description="Stats for a specific channel")
@app_commands.describe(channel="The channel to analyze")
async def channelStats(interaction: discord.Interaction, channel: discord.TextChannel):
	"""Stats for a specific Discord channel."""
	where = "WHERE m.channel_id = (SELECT id FROM channels WHERE discord_channel_id = ?)"
	params = (str(channel.id),)
	await sendStatsEmbed(interaction, f"📊 Stats for {channel.mention}", where, params)


@statGroup.command(name="me", description="Your personal stats")
async def myStats(interaction: discord.Interaction):
	"""Stats for the user who invoked the command."""
	userId = str(interaction.user.id)
	where = "WHERE m.user_id = (SELECT id FROM users WHERE discord_user_id = ?)"
	params = (userId,)
	await sendStatsEmbed(interaction, "📊 My statistics", where, params)


@statGroup.command(name="user", description="Stats for a specific user")
@app_commands.describe(user="The user to analyze")
async def userStats(interaction: discord.Interaction, user: discord.User):
	"""Stats for a specific Discord user."""
	where = "WHERE m.user_id = (SELECT id FROM users WHERE discord_user_id = ?)"
	params = (str(user.id),)
	await sendStatsEmbed(interaction, f"📊 Stats for {user.name}", where, params)
