from datetime import datetime, timezone
import discord
from discord import app_commands
from zoneinfo import ZoneInfo

from commands import makeEmbed, updateGroup, OWNER_ID
from commands.populateDb import authorize, batchUpdateStreaks, fetchMessages, fetchReactions, generateSummary
from utils.i18n import i18n, locale_str
from utils.utils import connectDb, timezoneAutocomplete, safeEmbed

@updateGroup.command(
	name="channel",
	description=locale_str("commands.update.channel.description")
)
@app_commands.describe(
	channel=locale_str("commands.update.channel.arg.channel"),
	from_date=locale_str("commands.update.arg.date")
)
async def updateChannelCommand(
	interaction: discord.Interaction,
	channel: discord.TextChannel,
	from_date: str = None
):
	if not await authorize(interaction):
		return

	l = i18n.getLocale(interaction)

	conn, cursor = connectDb()
	cursor.execute(
		"SELECT id, timezone FROM channels WHERE discord_channel_id = ?",
		(str(channel.id),)
	)
	row = cursor.fetchone()
	if not row:
		await interaction.response.send_message(
			f"❌ {i18n.t(l, 'commands.update.errors.notFound')}",
			ephemeral=True
		)
		conn.close()
		return

	internalId, tzName = row

	await interaction.response.defer()
	embedMsg = await interaction.followup.send(
		embed=makeEmbed(f"{i18n.t(l, 'commands.update.channel.embed1.title')}...", f"{i18n.t(l, 'commands.update.channel.embed1.desc')} ⏳")
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
			await interaction.followup.send(f"❌ {i18n.t(l, 'commands.update.errors.date')}: {e}", ephemeral=True)
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
		embed=makeEmbed(f"{i18n.t(l, 'commands.update.channel.embed2.title')}...", f"{i18n.t(l, 'commands.update.channel.embed2.desc')} 💜"),
		message=embedMsg
	)
	reacted = await fetchReactions(channel, cursor, conn, msgMap)

	summary = await generateSummary(cursor, internalId, stored, reacted, l, (chCurr, chMax), (glCurr, glMax))
	await safeEmbed(interaction, embed=makeEmbed(f"✅ {i18n.t(l, 'commands.add.channel.Done')}", summary), message=embedMsg)

	conn.close()


@updateGroup.command(
	name="all",
	description=locale_str("commands.update.all.description")
)
@app_commands.describe(
	from_date=locale_str("commands.update.arg.date")
)
async def updateAllChannelsCommand(interaction: discord.Interaction, from_date: str):
	l = i18n.getLocale(interaction)
	# Check owner
	if str(interaction.user.id) != OWNER_ID:
		await interaction.response.send_message(f"❌ {i18n.t(l, 'commands.update.all.errors.notOwner')}", ephemeral=True)
		return

	# Parse from_date
	try:
		fetchFrom = datetime.strptime(from_date, "%Y-%m-%d %H:%M")
		fetchFrom = fetchFrom.replace(tzinfo=timezone.utc)
	except Exception as e:
		await interaction.response.send_message(f"❌ {i18n.t(l, 'commands.update.errors.date')}: {e}", ephemeral=True)
		return

	# Limit: max 10 days ago
	if (datetime.now(timezone.utc) - fetchFrom).days > 10:
		await interaction.response.send_message(f"❌ {i18n.t(l, 'commands.update.all.errors.dateLimit')}", ephemeral=True)
		return

	await interaction.response.defer()
	conn, cursor = connectDb()

	cursor.execute("SELECT id, discord_channel_id, timezone FROM channels")
	channels = cursor.fetchall()
	if not channels:
		await interaction.followup.send(f"❌ {i18n.t(l, 'commands.update.all.errors.noChannels')}", ephemeral=True)
		conn.close()
		return

	embedMsg = await interaction.followup.send(embed=makeEmbed(f"{i18n.t(l, 'commands.update.all.embed.title')}...", f"{i18n.t(l, 'commands.update.all.embed.desc')} {from_date}⏳"))

	totalStored = 0
	totalReacted = 0
	summaryLines = []

	for internalId, discordId, tzName in channels:
		ch = interaction.client.get_channel(int(discordId))
		if not ch:
			try:
				ch = await interaction.client.fetch_channel(int(discordId))
			except Exception:
				summaryLines.append(f"⚠️ {i18n.t(l, 'commands.update.all.errors.noChId')} {discordId}")
				continue


		stored, msgMap = await fetchMessages(ch, internalId, cursor, conn, ZoneInfo(tzName), embedMsg, datetime.now(timezone.utc), fromDate=fetchFrom)
		(chCurr, chMax), (glCurr, glMax) = batchUpdateStreaks(cursor, conn, internalId, msgMap)
		reacted = await fetchReactions(ch, cursor, conn, msgMap)

		totalStored += stored
		totalReacted += reacted
		summaryLines.append(
			f"📌 {ch.guild.name if ch.guild else i18n.t(l, 'commands.update.all.guildSummary.unknown')} - [{ch.name}]:\n    {i18n.t(l, 'commands.update.all.guildSummary.p1')} {stored}, {i18n.t(l, 'commands.update.all.guildSummary.p2')} {reacted}, {i18n.t(l, 'commands.update.all.guildSummary.p3')} ({chCurr}/{chMax}), {i18n.t(l, 'commands.update.all.guildSummary.p4')} ({glCurr}/{glMax})"
		)

	conn.close()
	await safeEmbed(interaction, embed=makeEmbed(f"✅ {i18n.t(l, 'commands.update.all.success')}", "\n".join(summaryLines)), message=embedMsg)


@updateGroup.command(
	name="timezone",
	description=locale_str("commands.update.timezone.description")
)
@app_commands.describe(
	tz=locale_str("commands.update.timezone.arg.timezone")
)
@app_commands.autocomplete(tz=timezoneAutocomplete)
async def updateTimezoneCommand(interaction: discord.Interaction, tz: str):
	l = i18n.getLocale(interaction)
	# Validate timezone
	try:
		zoneinfo = ZoneInfo(tz)
	except Exception:
		await interaction.response.send_message(f"❌ {i18n.t(l, 'commands.update.timezone.errors.invalid')}: `{tz}`", ephemeral=True)
		return

	conn, cursor = connectDb()
	discordUserId = str(interaction.user.id)

	cursor.execute("SELECT id FROM users WHERE discord_user_id = ?", (discordUserId,))
	row = cursor.fetchone()

	if row:
		cursor.execute("UPDATE users SET timezone = ? WHERE discord_user_id = ?", (tz, discordUserId))
		msg = f"✅ {i18n.t(l, 'commands.update.timezone.success')} `{tz}`"
	else:
		cursor.execute("INSERT INTO users (discord_user_id, timezone) VALUES (?, ?)", (discordUserId, tz))
		msg = f"✅ {i18n.t(l, 'commands.update.timezone.created')} `{tz}`"

	conn.commit()
	conn.close()

	await interaction.response.send_message(msg, ephemeral=True)
