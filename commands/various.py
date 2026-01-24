import discord
from discord import app_commands
from commands import bot, makeEmbed
import commands
from database import db

from utils.i18n import i18n, locale_str
from utils.utils import connectDb

INVITE_PERMISSIONS = discord.Permissions()
INVITE_PERMISSIONS.update(
	send_messages=True,
	read_message_history=True,
	embed_links=True,
	add_reactions=True,
	manage_roles=True
)


@bot.tree.command(
	name="invite",
	description=locale_str("commands.invite.description")
)
async def inviteCommand(interaction: discord.Interaction):
	locale = i18n.getLocale(interaction)
	client_id = bot.user.id
	invite_url = discord.utils.oauth_url(client_id, permissions=INVITE_PERMISSIONS)
	await interaction.response.send_message(f"[{i18n.t(locale, "commands.invite.text")}]({invite_url}) Patherine 💜", ephemeral=True)

@bot.tree.command(
	name="help",
	description=locale_str("commands.help.description")
)
async def helpCommand(interaction: discord.Interaction):
	l = i18n.getLocale(interaction)
	embed = discord.Embed(
		title=f"🤖 {i18n.t(l, "commands.help.embed.title")}",
		description=i18n.t(l, "commands.help.embed.description"),
		color=discord.Color.purple()
	)
	
	embed.add_field(
		name=f"🎉 {i18n.t(l, "commands.help.embed.field1.name")}",
		value=f"{i18n.t(l, "commands.help.embed.field1.value1")}\n"
		      f"{i18n.t(l, "commands.help.embed.field1.value2")}",
		inline=False
	)
	
	embed.add_field(
		name=f"📚 {i18n.t(l, "commands.help.embed.field2.name")}",
		value=(
			f"```/help``` {i18n.t(l, "commands.help.embed.field2.value1")}\n"
			f"```/invite``` {i18n.t(l, "commands.help.embed.field2.value2")}\n"
			f"```/timezone``` {i18n.t(l, "commands.help.embed.field2.value3")}\n"
			f"```/untrack``` {i18n.t(l, "commands.help.embed.field2.value4")}"
		),
		inline=False
	)
	
	embed.add_field(
		name=f"📊 {i18n.t(l, "commands.help.embed.field3.name")}",
		value=(
			f"```/stat global``` {i18n.t(l, "commands.help.embed.field3.value1")}\n"
			f"```/stat channel [{i18n.t(l, "commands.help.argChannel")}]``` {i18n.t(l, "commands.help.embed.field3.value2")}\n"
			f"```/stat me``` {i18n.t(l, "commands.help.embed.field3.value3")}\n"
			f"```/stat user [{i18n.t(l, "commands.help.argUser")}]``` {i18n.t(l, "commands.help.embed.field3.value4")}"
		),
		inline=False
	)
	
	embed.add_field(
		name=f"🏆 {i18n.t(l, "commands.help.embed.field4.name")}",
		value=(
			f"```/leaderboard messages [{i18n.t(l, "commands.help.argChannel")}]```\n"
			f"  - {i18n.t(l, "commands.help.embed.field4.value1")}\n\n"
			f"```/leaderboard reactions [{i18n.t(l, "commands.help.argChannel")}]```\n"
			f"  - {i18n.t(l, "commands.help.embed.field4.value2")}\n\n"
			f"```/leaderboard delays [{i18n.t(l, "commands.help.argChannel")}] [worst:True/False] [avg:True/False]```\n"
			f"  - `worst` : {i18n.t(l, "commands.help.embed.field4.value3")}\n"
			f"  - `avg` : {i18n.t(l, "commands.help.embed.field4.value4")}\n\n"
			f"```/leaderboard streaks [{i18n.t(l, "commands.help.argChannel")}] [current:True/False]```\n"
			f"  - `current` : {i18n.t(l, "commands.help.embed.field4.value5")}\n"
			f"```/leaderboard days [{i18n.t(l, "commands.help.argChannel")}]```\n"
			f"  - {i18n.t(l, "commands.help.embed.field4.value6")}\n"
		),
		inline=False
	)

	embed.add_field(
		name=f"📈 {i18n.t(l, "commands.help.embed.field5.name")}",
		value=(
			"```/graph users [total:True/False] [points:int]```\n"
			f"  - {i18n.t(l, "commands.help.embed.field5.value1")}\n"
			f"  - `total` : {i18n.t(l, "commands.help.embed.field5.value2")}\n"
			f"  - `points` : {i18n.t(l, "commands.help.embed.field5.value3")}\n\n"
			"```/graph messages [total:True/False] [points:int]```\n"
			f"  - {i18n.t(l, "commands.help.embed.field5.value4")}\n"
			f"  - `total` : {i18n.t(l, "commands.help.embed.field5.value5")}\n"
			f"  - `points` : {i18n.t(l, "commands.help.embed.field5.value6")}\n\n"
			"```/graph streaks```\n"
			f"  - {i18n.t(l, "commands.help.embed.field5.value7")}\n"
		),
		inline=False
	)

	embed.add_field(
		name=f"⚙️ {i18n.t(l, "commands.help.embed.field6.name")}",
		value=(
			f"```/add admin [{i18n.t(l, "commands.help.argUser")}]```\n"
			f"  - {i18n.t(l, "commands.help.embed.field6.value1")}\n\n"
			f"```/update all [from_date:<date>]```\n"
			f"  - {i18n.t(l, "commands.help.embed.field6.value2")}\n\n"
			f"  - `from_date` : {i18n.t(l, "commands.help.embed.field6.value3")}\n\n"
			f"```/add channel [{i18n.t(l, "commands.help.argChannel")}] [role:@role] [tz_name:fuseau]```\n"
			f"  - {i18n.t(l, "commands.help.embed.field6.value4")}\n"
			f"  - `role` : {i18n.t(l, "commands.help.embed.field6.value5")}\n"
			f"  - `lang` : {i18n.t(l, "commands.help.embed.field6.value6")}\n"
			f"  - `tz_name` : {i18n.t(l, "commands.help.embed.field6.value7")}\n\n"
			f"```/update channel [{i18n.t(l, "commands.help.argChannel")}] [from_date:<date>]```\n"
			f"  - {i18n.t(l, "commands.help.embed.field6.value8")}\n\n"
			f"  - `from_date` : {i18n.t(l, "commands.help.embed.field6.value3")}"
		),
		inline=False
	)
	
	embed.add_field(
		name=i18n.t(l, "commands.help.embed.field7.name"),
		value=(
			f"{i18n.t(l, "commands.help.embed.field7.value1")} [GitHub](https://github.com/Moutigll/Patherine)\n"
			f"{i18n.t(l, "commands.help.embed.field7.value2")}: [patherine@moutig.sh](mailto:patherine@moutig.sh)"
		),
		inline=False
	)
	
	await interaction.response.send_message(embed=embed)


class UntrackConfirm(discord.ui.View):
	def __init__(self, discordUserId, locale="fr"):
		super().__init__(timeout=60)
		self.discordUserId = discordUserId
		self.locale = locale
		self.add_item(discord.ui.Button(label=i18n.t(locale, "commands.untrack.confirmView.button"), style=discord.ButtonStyle.danger, callback=self.confirm))

	async def confirm(self, interaction: discord.Interaction):
		conn, cursor = connectDb()

		cursor.execute("SELECT 1 FROM untracked_users WHERE discord_user_id=?", (str(self.discordUserId),))
		if cursor.fetchone():
			await interaction.response.edit_message(
				content=f"⚠️ {i18n.t(self.locale, 'commands.untrack.error1')}.", view=None
			)
			conn.close()
			return

		cursor.execute("SELECT id FROM users WHERE discord_user_id=?", (str(self.discordUserId),))
		userRow = cursor.fetchone()
		if not userRow:
			await interaction.response.edit_message(
				content=f"⚠️ {i18n.t(self.locale, 'commands.untrack.error2')}.", view=None
			)
			conn.close()
			return
		userId = userRow[0]

		cursor.execute("SELECT COUNT(*) FROM messages WHERE user_id=?", (userId,))
		messageCount = cursor.fetchone()[0]
		cursor.execute("SELECT COUNT(*) FROM reactions WHERE user_id=?", (userId,))
		reactionCount = cursor.fetchone()[0]

		cursor.execute("DELETE FROM messages WHERE user_id=?", (userId,))
		cursor.execute("DELETE FROM reactions WHERE user_id=?", (userId,))
		cursor.execute("DELETE FROM users WHERE id=?", (userId,))

		cursor.execute(
			"INSERT OR IGNORE INTO untracked_users (discord_user_id) VALUES (?)",
			(str(self.discordUserId),)
		)

		conn.commit()
		conn.close()

		await interaction.response.edit_message(
			content=f"✅ {i18n.t(self.locale, 'commands.untrack.success.part1')}.\n**{messageCount} {i18n.t(self.locale, 'commands.untrack.success.part2')}** and **{reactionCount} {i18n.t(self.locale, 'commands.untrack.success.part3')}.",
			view=None
		)

@bot.tree.command(
	name="untrack",
	description=locale_str("commands.untrack.description")
)
async def untrackCommand(interaction: discord.Interaction):
	locale = i18n.getLocale(interaction)
	view = UntrackConfirm(interaction.user.id, locale=locale)
	await interaction.response.send_message(
		f"⚠️ {i18n.t(locale, 'commands.untrack.confirmView.warning')}.\n"
		f"{i18n.t(locale, 'commands.untrack.confirmView.explanation')}.\n"
		f"{i18n.t(locale, 'commands.untrack.confirmView.confirm')} ?",
		ephemeral=True,
		view=view
	)
