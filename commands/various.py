import datetime
import discord
from discord import app_commands
from zoneinfo import ZoneInfo

from commands import bot, makeEmbed
from commands.populateDb import authorize, fetchMessages, fetchReactions, generateSummary
from utils import connectDb

@bot.tree.command(name="update_channel", description="Update a channel with new messages and reactions")
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

	cursor.execute("SELECT MAX(timestamp) FROM messages WHERE channel_id = ?", (internalId,))
	lastTs = cursor.fetchone()[0]
	afterParam = datetime.datetime.fromisoformat(lastTs) if lastTs else None

	stored, msgMap = await fetchMessages(channel, internalId, cursor, conn, ZoneInfo(tzName), afterParam)

	await embedMsg.edit(embed=makeEmbed("Updating reactions...", "Looking through new reactions 💜"))
	reacted = await fetchReactions(channel, cursor, conn, msgMap)

	summary = await generateSummary(cursor, internalId, stored, reacted)
	await embedMsg.edit(embed=makeEmbed("✅ Done", summary))

	conn.close()
