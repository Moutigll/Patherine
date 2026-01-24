
import typing
from datetime import datetime, timezone
import discord
from discord import app_commands
from zoneinfo import ZoneInfo, available_timezones


from commands import addGroup, makeEmbed, OWNER_ID
from commands.populateDb import authorize, batchUpdateStreaks, fetchMessages, fetchReactions, generateSummary
from utils.i18n import i18n, locale_str
from utils.utils import connectDb, languageAutocomplete,timezoneAutocomplete, safeEmbed

@addGroup.command(
	name="admin",
	description=locale_str("commands.add.admin.description")
)
@app_commands.describe(user=locale_str("commands.add.admin.argUser"))
async def addAdminCommand(interaction: discord.Interaction, user: discord.User):
	requesterId = str(interaction.user.id)
	targetId = str(user.id)
	l = i18n.getLocale(interaction)

	if requesterId != OWNER_ID:
		await interaction.response.send_message(f"❌ {i18n.t(l, 'commands.add.admin.reject')}", ephemeral=True)
		return

	conn, cursor = connectDb()
	try:
		cursor.execute("SELECT 1 FROM admins WHERE discord_user_id = ?", (targetId,))
		exists = cursor.fetchone()

		if exists:
			await interaction.response.send_message(f"{user.mention} {i18n.t(l, 'commands.add.admin.alreadyAdmin')} ⚠️", ephemeral=True)
		else:
			cursor.execute("INSERT INTO admins (discord_user_id) VALUES (?)", (targetId,))
			conn.commit()
			await interaction.response.send_message(f"✅ {user.mention} {i18n.t(l, 'commands.add.admin.success')}", ephemeral=True)
	finally:
		conn.close()

@addGroup.command(
	name="channel",
	description=locale_str("commands.add.channel.description")
)
@app_commands.describe(
	channel=locale_str("commands.add.channel.arg.channel"),
	role=locale_str("commands.add.channel.arg.role"),
	lang=locale_str("commands.add.channel.arg.language"),
	tz_name=locale_str("commands.add.channel.arg.timezone"),
	)
@app_commands.autocomplete(
	lang=languageAutocomplete,
	tz_name=timezoneAutocomplete
	)
async def addChannelCommand(
	interaction: discord.Interaction,
	channel: discord.TextChannel,
	role: typing.Optional[discord.Role] = None,
	lang: str = "fr",
	tz_name: str = "Europe/Paris"
):
	if not await authorize(interaction):
		return

	l = i18n.getLocale(interaction)	
	conn, cursor = connectDb()

	cursor.execute("SELECT id FROM channels WHERE discord_channel_id = ?", (str(channel.id),))
	if cursor.fetchone():
		conn.close()
		await interaction.response.send_message(f"❌ {channel.mention} {i18n.t(l, 'commands.add.channel.errors.alreadyExists')} /update_channel", ephemeral=True)
		return

	await interaction.response.defer()

	if lang not in ["en", "fr"]:
		await interaction.followup.send(f"❌ {i18n.t(l, 'commands.add.channel.errors.lang1')} '{lang}', {i18n.t(l, 'commands.add.channel.errors.lang2')} en, fr", ephemeral=True)
		conn.close()
		return
	
	if tz_name not in available_timezones():
		await interaction.followup.send(f"❌ {i18n.t(l, 'commands.add.channel.errors.tz')} '{tz_name}'", ephemeral=True)
		conn.close()
		return
	
	cursor.execute(
		"INSERT INTO channels(discord_channel_id, discord_role_id, timezone, lang) VALUES (?, ?, ?, ?)",
		(str(channel.id), str(role.id) if role else None, tz_name, lang)
	)
	conn.commit()
	internalId = cursor.lastrowid

	embedMsg = await interaction.followup.send(embed=makeEmbed(f"{i18n.t(l, 'commands.add.channel.embed1.title')}...", f" {i18n.t(l, 'commands.add.channel.embed1.desc')} ⏳"))
	addStart = datetime.now(timezone.utc)

	stored, msgMap = await fetchMessages(channel, internalId, cursor, conn, ZoneInfo(tz_name), embedMsg, addStart)

	(chCurr, chMax), (glCurr, glMax) = batchUpdateStreaks(cursor, conn, internalId, msgMap)

	await safeEmbed(interaction, embed=makeEmbed(f"{i18n.t(l, 'commands.add.channel.embed2.title')}...", f" {i18n.t(l, 'commands.add.channel.embed2.desc')} 💜"), message=embedMsg)

	reacted = await fetchReactions(channel, cursor, conn, msgMap)
	summary = await generateSummary(cursor, internalId, stored, reacted, l, (chCurr, chMax), (glCurr, glMax))

	await safeEmbed(interaction, embed=makeEmbed(f"✅ {i18n.t(l, 'commands.add.channel.Done')}", summary), message=embedMsg)
	conn.close()
