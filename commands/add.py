from discord import app_commands
import discord
from commands import bot, OWNER_ID
from utils import connectDb

@bot.tree.command(name="add_admin", description="Add a user as admin (only OWNER can do that)")
@app_commands.describe(user="User to add as admin")
async def addAdminCommand(interaction: discord.Interaction, user: discord.User):
	requesterId = str(interaction.user.id)
	targetId = str(user.id)

	if requesterId != OWNER_ID:
		await interaction.response.send_message("You are not authorized to add admins ❌", ephemeral=True)
		return

	conn, cursor = connectDb()
	cursor.execute("SELECT 1 FROM admins WHERE discord_user_id = ?", (targetId,))
	exists = cursor.fetchone()

	if exists:
		await interaction.response.send_message(f"{user.mention} is already an admin ⚠️", ephemeral=True)
	else:
		cursor.execute("INSERT INTO admins (discord_user_id) VALUES (?)", (targetId,))
		conn.commit()
		await interaction.response.send_message(f"{user.mention} has been added as an admin ✅", ephemeral=True)

	conn.close()

@bot.tree.command(name="add_channel", description="Add a channel to the database (only ADMIN can do that)")
@app_commands.describe(channel="Channel to add")
async def addChannelCommand(interaction: discord.Interaction, channel: discord.TextChannel):
	requesterId = str(interaction.user.id)

	conn, cursor = connectDb()
	cursor.execute("SELECT 1 FROM admins WHERE discord_user_id = ?", (requesterId,))
	isAdmin = cursor.fetchone() is not None

	if not isAdmin and requesterId != OWNER_ID:
		await interaction.response.send_message("You are not authorized to add channels ❌", ephemeral=True)
	else:
		cursor.execute("SELECT 1 FROM channels WHERE discord_channel_id = ?", (channel.id,))
		exists = cursor.fetchone()
		if exists:
			await interaction.response.send_message(f"{channel.mention} is already in the database ⚠️", ephemeral=True)
		else:
			cursor.execute("INSERT INTO channels (discord_channel_id) VALUES (?)", (channel.id,))
			conn.commit()
			await interaction.response.send_message(f"{channel.mention} has been added to the database ✅", ephemeral=True)

	conn.close()
