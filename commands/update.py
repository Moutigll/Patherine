from datetime import datetime, timezone
import discord
from discord import app_commands
from zoneinfo import ZoneInfo

from commands import makeEmbed, updateGroup, OWNER_ID
from commands.populateDb import authorize, batchUpdateStreaks, fetchMessages, fetchReactions, generateSummary
from utils.utils import connectDb, timezoneAutocomplete, safeEmbed

@updateGroup.command(
	name="channel",
	description="Update a channel with new messages and reactions"
)
@app_commands.describe(
	channel="Channel to update",
	from_date="Optional: fetch messages starting from this date (YYYY-MM-DD HH:MM UTC)"
)
async def updateChannelCommand(
	interaction: discord.Interaction,
	channel: discord.TextChannel,
	from_date: str = None
):
	if not await authorize(interaction):
		return

	conn, cursor = connectDb()
	cursor.execute(
		"SELECT id, timezone FROM channels WHERE discord_channel_id = ?",
		(str(channel.id),)
	)
	row = cursor.fetchone()
	if not row:
		await interaction.response.send_message(
			"❌ Channel not found, use /add_channel first",
			ephemeral=True
		)
		conn.close()
		return

	internalId, tzName = row

	await interaction.response.defer()
	embedMsg = await interaction.followup.send(
		embed=makeEmbed("Updating activity...", "Fetching new messages ⏳")
	)
	addStart = datetime.now(timezone.utc)

	# Convert from_date string to datetime if provided
	fetchFrom = None
	if from_date:
		try:
			# expect format "YYYY-MM-DD HH:MM"
			fetchFrom = datetime.strptime(from_date, "%Y-%m-%d %H:%M")
			# convert to UTC
			fetchFrom = fetchFrom.replace(tzinfo=ZoneInfo(tzName)).astimezone(timezone.utc)
		except Exception as e:
			await interaction.followup.send(f"❌ Invalid from_date format: {e}", ephemeral=True)
			conn.close()
			return

	stored, msgMap = await fetchMessages(
		channel,
		internalId,
		cursor,
		conn,
		ZoneInfo(tzName),
		embedMsg,
		addStart,
		fromDate=fetchFrom
	)

	(chCurr, chMax), (glCurr, glMax) = batchUpdateStreaks(cursor, conn, internalId, msgMap)

	await safeEmbed(
		interaction,
		embed=makeEmbed("Updating reactions...", "Looking through new reactions 💜"),
		message=embedMsg
	)
	reacted = await fetchReactions(channel, cursor, conn, msgMap)

	summary = await generateSummary(cursor, internalId, stored, reacted, (chCurr, chMax), (glCurr, glMax))
	await safeEmbed(interaction, embed=makeEmbed("✅ Done", summary), message=embedMsg)

	conn.close()


@updateGroup.command(
	name="all",
	description="Update all channels with new messages and reactions (OWNER only)"
)
@app_commands.describe(
	from_date="Fetch messages starting from this date (YYYY-MM-DD HH:MM UTC, max 10 days ago)"
)
async def updateAllChannelsCommand(interaction: discord.Interaction, from_date: str):
	# Check owner
	if str(interaction.user.id) != OWNER_ID:
		await interaction.response.send_message("❌ Only the bot owner can execute this command", ephemeral=True)
		return

	# Parse from_date
	try:
		fetchFrom = datetime.strptime(from_date, "%Y-%m-%d %H:%M")
		fetchFrom = fetchFrom.replace(tzinfo=timezone.utc)
	except Exception as e:
		await interaction.response.send_message(f"❌ Invalid from_date format: {e}", ephemeral=True)
		return

	# Limit: max 10 days ago
	if (datetime.now(timezone.utc) - fetchFrom).days > 10:
		await interaction.response.send_message("❌ from_date cannot be more than 10 days ago", ephemeral=True)
		return

	await interaction.response.defer()
	conn, cursor = connectDb()

	cursor.execute("SELECT id, discord_channel_id, timezone FROM channels")
	channels = cursor.fetchall()
	if not channels:
		await interaction.followup.send("❌ No channels registered", ephemeral=True)
		conn.close()
		return

	embedMsg = await interaction.followup.send(embed=makeEmbed("Updating all channels...", f"Fetching messages since {from_date} ⏳"))

	totalStored = 0
	totalReacted = 0
	summaryLines = []

	for internalId, discordId, tzName in channels:
		ch = interaction.client.get_channel(int(discordId))
		if not ch:
			try:
				ch = await interaction.client.fetch_channel(int(discordId))
			except Exception:
				summaryLines.append(f"⚠️ Failed to fetch channel ID {discordId}")
				continue


		stored, msgMap = await fetchMessages(ch, internalId, cursor, conn, ZoneInfo(tzName), embedMsg, datetime.now(timezone.utc), fromDate=fetchFrom)
		(chCurr, chMax), (glCurr, glMax) = batchUpdateStreaks(cursor, conn, internalId, msgMap)
		reacted = await fetchReactions(ch, cursor, conn, msgMap)

		totalStored += stored
		totalReacted += reacted
		summaryLines.append(
			f"📌 {ch.guild.name if ch.guild else 'Unknown server'} - [{ch.name}]:\n\tstored {stored}, reacted {reacted}, channel streak ({chCurr}/{chMax}), global streak ({glCurr}/{glMax})"
		)

	conn.close()
	await safeEmbed(interaction, embed=makeEmbed("✅ All channels updated", "\n".join(summaryLines)), message=embedMsg)


@updateGroup.command(name="timezone", description="Update your timezone or create your user entry if missing")
@app_commands.describe(tz="Timezone like Europe/Paris")
@app_commands.autocomplete(tz=timezoneAutocomplete)
async def updateTimezoneCommand(interaction: discord.Interaction, tz: str):
	try:
		zoneinfo = ZoneInfo(tz)
	except Exception:
		await interaction.response.send_message(f"❌ Invalid timezone: `{tz}`", ephemeral=True)
		return

	conn, cursor = connectDb()
	discordUserId = str(interaction.user.id)

	cursor.execute("SELECT id FROM users WHERE discord_user_id = ?", (discordUserId,))
	row = cursor.fetchone()

	if row:
		cursor.execute("UPDATE users SET timezone = ? WHERE discord_user_id = ?", (tz, discordUserId))
		msg = f"✅ Timezone updated to `{tz}`"
	else:
		cursor.execute("INSERT INTO users (discord_user_id, timezone) VALUES (?, ?)", (discordUserId, tz))
		msg = f"✅ User created with timezone `{tz}`"

	conn.commit()
	conn.close()

	await interaction.response.send_message(msg, ephemeral=True)
