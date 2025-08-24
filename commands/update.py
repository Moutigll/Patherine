from datetime import datetime, timezone
import discord
from discord import app_commands
from zoneinfo import ZoneInfo

from commands import makeEmbed, updateGroup
from commands.populateDb import authorize, fetchMessages, fetchReactions, generateSummary
from utils.utils import connectDb, timezoneAutocomplete, safeEmbed

@updateGroup.command(name="channel", description="Update a channel with new messages and reactions")
@app_commands.describe(channel="Channel to update")
async def updateChannelCommand(interaction: discord.Interaction, channel: discord.TextChannel):
	if not await authorize(interaction):
		return

	conn, cursor = connectDb()
	cursor.execute("SELECT id, timezone FROM channels WHERE discord_channel_id = ?", (str(channel.id),))
	row = cursor.fetchone()
	if not row:
		await interaction.response.send_message("❌ Channel not found, use /add_channel first", ephemeral=True)
		conn.close()
		return

	internalId, tzName = row

	await interaction.response.defer()
	embedMsg = await interaction.followup.send(embed=makeEmbed("Updating activity...", "Fetching new messages ⏳"))
	addStart = datetime.now(timezone.utc)

	stored, msgMap = await fetchMessages(channel, internalId, cursor, conn, ZoneInfo(tzName), embedMsg, addStart)

	await safeEmbed(interaction, embed=makeEmbed("Updating reactions...", "Looking through new reactions 💜"), message=embedMsg)
	reacted = await fetchReactions(channel, cursor, conn, msgMap)

	summary = await generateSummary(cursor, internalId, stored, reacted)
	await safeEmbed(interaction, embed=makeEmbed("✅ Done", summary), message=embedMsg)

	conn.close()


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
