
import discord
from discord import app_commands
from zoneinfo import ZoneInfo


from commands import bot, makeEmbed, OWNER_ID
from commands.populateDb import authorize, fetchMessages, fetchReactions, generateSummary
from utils import connectDb, timezoneAutocomplete


@bot.tree.command(name="add_admin", description="Add a user as admin (only OWNER can do that)")
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

@bot.tree.command(name="add_channel", description="Add a channel to the database (only ADMIN can do that)")
@app_commands.describe(channel="Channel to add", tz_name="Timezone for message parsing (default: Europe/Paris)")
@app_commands.autocomplete(tz_name=timezoneAutocomplete)
async def addChannelCommand(interaction: discord.Interaction, channel: discord.TextChannel, tz_name: str = "Europe/Paris"):
	if not await authorize(interaction):
		return

	conn, cursor = connectDb()

	cursor.execute("SELECT id FROM channels WHERE discord_channel_id = ?", (str(channel.id),))
	if cursor.fetchone():
		conn.close()
		await interaction.response.send_message(f"❌ {channel.mention} already in DB, use /update_channel", ephemeral=True)
		return

	cursor.execute("INSERT INTO channels(discord_channel_id, timezone) VALUES (?, ?)", (str(channel.id), tz_name))
	conn.commit()
	internalId = cursor.lastrowid

	await interaction.response.defer()
	embedMsg = await interaction.followup.send(embed=makeEmbed("Fetching activity...", "Looking through message history ⏳"))

	stored, msgMap = await fetchMessages(channel, internalId, cursor, conn, ZoneInfo(tz_name))

	await embedMsg.edit(embed=makeEmbed("Fetching reactions...", "Looking through reactions 💜"))

	reacted = await fetchReactions(channel, cursor, conn, msgMap)
	summary = await generateSummary(cursor, internalId, stored, reacted)

	await embedMsg.edit(embed=makeEmbed("✅ Done", summary))
	conn.close()
