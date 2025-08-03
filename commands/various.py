from datetime import datetime, timezone
import discord
from discord import app_commands
from zoneinfo import ZoneInfo

from commands import makeEmbed, updateChannelCommand
from commands.populateDb import authorize, fetchMessages, fetchReactions, generateSummary
from utils.utils import connectDb

@updateChannelCommand.command(name="channel", description="Update a channel with new messages and reactions")
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

	await embedMsg.edit(embed=makeEmbed("Updating reactions...", "Looking through new reactions 💜"))
	reacted = await fetchReactions(channel, cursor, conn, msgMap)

	summary = await generateSummary(cursor, internalId, stored, reacted)
	await embedMsg.edit(embed=makeEmbed("✅ Done", summary))

	conn.close()
