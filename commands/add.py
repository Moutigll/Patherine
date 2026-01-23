
import typing
from datetime import datetime, timezone
import discord
from discord import app_commands
from zoneinfo import ZoneInfo, available_timezones


from commands import addGroup, makeEmbed, OWNER_ID
from commands.populateDb import authorize, batchUpdateStreaks, fetchMessages, fetchReactions, generateSummary
from utils.utils import connectDb, languageAutocomplete,timezoneAutocomplete, safeEmbed

@addGroup.command(name="admin", description="Add a user as admin (only OWNER can do that)")
@app_commands.describe(user="User to add as admin")
async def addAdminCommand(interaction: discord.Interaction, user: discord.User):
	requesterId = str(interaction.user.id)
	targetId = str(user.id)

	if requesterId != OWNER_ID:
		await interaction.response.send_message("❌ You are not authorized to add admins", ephemeral=True)
		return

	conn, cursor = connectDb()
	try:
		cursor.execute("SELECT 1 FROM admins WHERE discord_user_id = ?", (targetId,))
		exists = cursor.fetchone()

		if exists:
			await interaction.response.send_message(f"{user.mention} is already an admin ⚠️", ephemeral=True)
		else:
			cursor.execute("INSERT INTO admins (discord_user_id) VALUES (?)", (targetId,))
			conn.commit()
			await interaction.response.send_message(f"✅ {user.mention} has been added as an admin", ephemeral=True)
	finally:
		conn.close()

@addGroup.command(name="channel", description="Add a channel to the database (only ADMIN can do that)")
@app_commands.describe(
	channel="Channel to add",
	role="(Optional) Role to associate with this channel",
	lang="Language for the channel (default: fr)",
	tz_name="Timezone for message parsing (default: Europe/Paris)",
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

	conn, cursor = connectDb()

	cursor.execute("SELECT id FROM channels WHERE discord_channel_id = ?", (str(channel.id),))
	if cursor.fetchone():
		conn.close()
		await interaction.response.send_message(f"❌ {channel.mention} already in DB, use /update_channel", ephemeral=True)
		return

	await interaction.response.defer()

	if lang not in ["en", "fr"]:
		await interaction.followup.send(f"❌ Unsupported language '{lang}', supported: en, fr", ephemeral=True)
		conn.close()
		return
	
	if tz_name not in available_timezones():
		await interaction.followup.send(f"❌ Invalid timezone '{tz_name}'", ephemeral=True)
		conn.close()
		return
	
	cursor.execute(
		"INSERT INTO channels(discord_channel_id, discord_role_id, timezone, lang) VALUES (?, ?, ?, ?)",
		(str(channel.id), str(role.id) if role else None, tz_name, lang)
	)
	conn.commit()
	internalId = cursor.lastrowid

	embedMsg = await interaction.followup.send(embed=makeEmbed("Fetching activity...", "Looking through message history ⏳"))
	addStart = datetime.now(timezone.utc)

	stored, msgMap = await fetchMessages(channel, internalId, cursor, conn, ZoneInfo(tz_name), embedMsg, addStart)

	(chCurr, chMax), (glCurr, glMax) = batchUpdateStreaks(cursor, conn, internalId, msgMap)

	await safeEmbed(interaction, embed=makeEmbed("Updating reactions...", "Looking through new reactions 💜"), message=embedMsg)

	reacted = await fetchReactions(channel, cursor, conn, msgMap)
	summary = await generateSummary(cursor, internalId, stored, reacted, (chCurr, chMax), (glCurr, glMax))

	await safeEmbed(interaction, embed=makeEmbed("✅ Done", summary), message=embedMsg)
	conn.close()
