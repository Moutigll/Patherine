import discord
from discord import app_commands, Interaction
from discord.ui import View, button, Button
from math import ceil
from datetime import datetime

from utils.i18n import i18n, locale_str
from utils.utils import connectDb, escapeMarkdown
from commands import FOOTER_TEXT, leaderboardGroup

class Leaderboard(View):
	def __init__(self, interaction: Interaction, title: str, data: list[tuple[str, int]], itemsPerPage: int = 10, timeout: float = 120.0, sortReverse: bool = True):
		super().__init__(timeout=timeout)

		self.interaction = interaction
		self.title = title
		self.itemsPerPage = itemsPerPage

		self.l = i18n.getLocale(interaction)

		self.prevButton.label = f"⬅️ {i18n.t(self.l, 'commands.lb.embed.prev')}"
		self.nextButton.label = f"{i18n.t(self.l, 'commands.lb.embed.next')} ➡️"

		self.entries = sorted(data, key=lambda x: x[1], reverse=sortReverse)
		self.pageCount = max(1, ceil(len(self.entries) / itemsPerPage))
		self.currentPage = 0

		self.prevButton.disabled = True
		if self.pageCount <= 1:
			self.nextButton.disabled = True


	def makeEmbed(self) -> discord.Embed:
		start = self.currentPage * self.itemsPerPage
		end = start + self.itemsPerPage
		slice_ = self.entries[start:end]
		description = ""
		for idx, (name, value) in enumerate(slice_, start=start + 1):
			description += f"`#{idx:<2}` {escapeMarkdown(name)} — **{value}**\n"
		description += f"\n\n{FOOTER_TEXT}"
		embed = discord.Embed(title=self.title, description=description or f"*{i18n.t(self.l, 'commands.lb.embed.noData')}*", color=discord.Color.purple())
		embed.set_footer(text=f"{i18n.t(self.l, 'commands.lb.embed.page')} {self.currentPage+1}/{self.pageCount}")
		return embed

	@button(style=discord.ButtonStyle.gray, custom_id="leaderboard_prev")
	async def prevButton(self, interaction: Interaction, button: Button):
		if self.currentPage > 0:
			self.currentPage -= 1
			self.nextButton.disabled = False
		self.prevButton.disabled = (self.currentPage == 0)
		await interaction.response.edit_message(embed=self.makeEmbed(), view=self)

	@button(style=discord.ButtonStyle.gray, custom_id="leaderboard_next")
	async def nextButton(self, interaction: Interaction, button: Button):
		if self.currentPage < self.pageCount - 1:
			self.currentPage += 1
			self.prevButton.disabled = False
		self.nextButton.disabled = (self.currentPage == self.pageCount - 1)
		await interaction.response.edit_message(embed=self.makeEmbed(), view=self)

	async def start(self):
		await self.interaction.followup.send(embed=self.makeEmbed(), view=self)

async def getUsername(userId: str, interaction: Interaction) -> str:
	member = None

	if interaction.guild:
		try:
			member = interaction.guild.get_member(int(userId))
		except (ValueError, TypeError):
			pass

	if member:
		return member.display_name

	user = interaction.client.get_user(int(userId))
	if user:
		return user.name

	try:
		user = await interaction.client.fetch_user(int(userId))
		if user:
			return user.name
	except Exception:
		pass

	return f"{i18n.t(i18n.getLocale(interaction), 'commands.lb.embed.unknown')} ({userId})"


@leaderboardGroup.command(
	name="messages",
	description=locale_str("commands.lb.messages.description")
)
@app_commands.describe(
	channel=locale_str("commands.lb.arg.channel")
)
async def messagesLeaderboard(interaction: Interaction, channel: discord.TextChannel | None = None):
	await interaction.response.defer()
	conn, cursor = connectDb()
	l = i18n.getChannelLocale(interaction.channel, interaction)
	if channel:
		cursor.execute("SELECT id FROM channels WHERE discord_channel_id = ?", (str(channel.id),))
		row = cursor.fetchone()
		if not row:
			conn.close()
			await interaction.followup.send(f"❌ {channel.mention} {i18n.t(l, 'commands.lb.error')}.", ephemeral=True)
			return
		title = f"🏆 {i18n.t(l, 'commands.lb.messages.title')} #{channel.name}"
		cursor.execute("""
			SELECT users.discord_user_id, COUNT(*) 
			FROM messages
			JOIN users ON users.id = messages.user_id
			WHERE messages.category = 'success' AND messages.channel_id = ?
			GROUP BY users.discord_user_id
		""", (row[0],))
	else:
		title = f"🏆 {i18n.t(l, 'commands.lb.messages.gtitle')}"
		cursor.execute("""
			SELECT users.discord_user_id, COUNT(*) 
			FROM messages
			JOIN users ON users.id = messages.user_id
			WHERE messages.category = 'success'
			GROUP BY users.discord_user_id
		""")
	rows = cursor.fetchall()
	conn.close()
	data = []
	for userId, cnt in rows:
		name = await getUsername(userId, interaction)
		data.append((name, cnt))
	board = Leaderboard(interaction, title, data)
	await board.start()

@leaderboardGroup.command(
	name="reactions",
	description=locale_str("commands.lb.reactions.description")
)
@app_commands.describe(
	channel=locale_str("commands.lb.arg.channel")
)
async def reactionsLeaderboard(interaction: Interaction, channel: discord.TextChannel | None = None):
	await interaction.response.defer()
	l = i18n.getChannelLocale(interaction.channel, interaction)
	conn, cursor = connectDb()
	if channel:
		cursor.execute("SELECT id FROM channels WHERE discord_channel_id = ?", (str(channel.id),))
		row = cursor.fetchone()
		if not row:
			conn.close()
			await interaction.followup.send(f"❌ {channel.mention} {i18n.t(l, 'commands.lb.error')}.", ephemeral=True)
			return
		title = f"💜 {i18n.t(l, 'commands.lb.reactions.title')} #{channel.name}"
		cursor.execute("""
			SELECT users.discord_user_id, COUNT(r.id)
			FROM reactions r
			JOIN messages m ON r.message_id = m.id
			JOIN users ON users.id = r.user_id
			WHERE m.channel_id = ?
			GROUP BY users.discord_user_id
		""", (row[0],))
	else:
		title = f"💜 {i18n.t(l, 'commands.lb.reactions.gtitle')}"
		cursor.execute("""
			SELECT users.discord_user_id, COUNT(r.id)
			FROM reactions r
			JOIN users ON users.id = r.user_id
			GROUP BY users.discord_user_id
		""")
	rows = cursor.fetchall()
	conn.close()
	data = []
	for userId, cnt in rows:
		name = await getUsername(userId, interaction)
		data.append((name, cnt))
	board = Leaderboard(interaction, title, data)
	await board.start()

@leaderboardGroup.command(
	name="delays",
	description=locale_str("commands.lb.delays.description")
)
@app_commands.describe(
	channel=locale_str("commands.lb.arg.channel"),
	worst=locale_str("commands.lb.delays.arg.worst"),
	avg=locale_str("commands.lb.delays.arg.avg")
)
async def delaysLeaderboard(interaction: Interaction, channel: discord.TextChannel | None = None, worst: bool = False, avg: bool = False):
	l = i18n.getChannelLocale(interaction.channel, interaction)
	if worst and avg:
		await interaction.response.send_message(f"❌ {i18n.t(l, 'commands.lb.delays.error')}.", ephemeral=True)
		return

	await interaction.response.defer()
	conn, cursor = connectDb()
	if channel:
		cursor.execute("SELECT id FROM channels WHERE discord_channel_id = ?", (str(channel.id),))
		row = cursor.fetchone()
		if not row:
			conn.close()
			return await interaction.followup.send(f"❌ {channel.mention} is not registered.", ephemeral=True)
		title = f"⏱️ {i18n.t(l, 'commands.lb.delays.worst') if worst else i18n.t(l, 'commands.lb.delays.avg') if avg else i18n.t(l, 'commands.lb.delays.best')} {i18n.t(l, 'commands.lb.delays.title')} #{channel.name}"
		cursor.execute(
			"""
			SELECT users.discord_user_id, m.timestamp
			FROM messages m
			JOIN users ON users.id = m.user_id
			WHERE m.category = 'success' AND m.channel_id = ?
		""", (row[0],))
	else:
		title = f"⏱️ {i18n.t(l, 'commands.lb.delays.worst') if worst else i18n.t(l, 'commands.lb.delays.avg') if avg else i18n.t(l, 'commands.lb.delays.best')} {i18n.t(l, 'commands.lb.delays.gtitle')}"
		cursor.execute(
			"""
			SELECT users.discord_user_id, m.timestamp
			FROM messages m
			JOIN users ON users.id = m.user_id
			WHERE m.category = 'success'
		""")
	rows = cursor.fetchall()
	conn.close()

	deltasPerUser: dict[str, list[float]] = {}
	for userId, ts in rows:
		dt = datetime.fromisoformat(ts)
		delta = dt.second + dt.microsecond / 1_000_000
		deltasPerUser.setdefault(userId, []).append(delta)

	data: list[tuple[str, float]] = []
	for userId, deltas in deltasPerUser.items():
		name = await getUsername(userId, interaction)
		if avg:
			value = round(sum(deltas) / len(deltas), 3)
			name = f"{name} ({len(deltas)})"
		elif worst:
			value = max(deltas)
		else:
			value = min(deltas)

		data.append((name, value))


	board = Leaderboard(interaction, title, data, sortReverse=worst)
	await board.start()

@leaderboardGroup.command(
	name="streaks",
	description=locale_str("commands.lb.streaks.description")
)
@app_commands.describe(
	channel=locale_str("commands.lb.arg.channel"),
	current=locale_str("commands.lb.streaks.arg.current"))
async def streaksLeaderboard(interaction: Interaction, channel: discord.TextChannel | None = None, current: bool = False):
	await interaction.response.defer()
	l = i18n.getChannelLocale(interaction.channel, interaction)
	conn, cursor = connectDb()

	try:
		if channel:
			cursor.execute(
				"SELECT id FROM channels WHERE discord_channel_id = ?",
				(str(channel.id),)
			)
			row = cursor.fetchone()
			if not row:
				await interaction.followup.send(f"❌ {channel.mention} is not registered.", ephemeral=True)
				return

			title = f"🔥 {i18n.t(l, 'commands.lb.streaks.title')} #{channel.name}"

			# get users who have success messages in that channel, join to user_streaks
			cursor.execute(
				"""
				SELECT u.discord_user_id, u.timezone,
					   COALESCE(us.current_streak, 0) AS current_streak,
					   COALESCE(us.max_streak, 0) AS max_streak
				FROM messages m
				JOIN users u ON u.id = m.user_id
				LEFT JOIN user_streaks us ON us.user_id = u.id
				WHERE m.category = 'success' AND m.channel_id = ?
				GROUP BY u.discord_user_id, u.timezone
				ORDER BY u.discord_user_id
				""",
				(row[0],)
			)
		else:
			# global: read all users from user_streaks (precomputed)
			title = f"🔥 {i18n.t(l, 'commands.lb.streaks.gtitle')}"
			cursor.execute(
				"""
				SELECT u.discord_user_id, u.timezone,
					   COALESCE(us.current_streak, 0) AS current_streak,
					   COALESCE(us.max_streak, 0) AS max_streak
				FROM user_streaks us
				JOIN users u ON u.id = us.user_id
				ORDER BY u.discord_user_id
				"""
			)

		rows = cursor.fetchall()
	finally:
		conn.close()

	# rows: (discord_user_id, timezone, current_streak, max_streak)
	data: list[tuple[str, int]] = []
	for discordId, tzStr, currentStreak, bestStreak in rows:

		name = await getUsername(discordId, interaction)

		if current:
			value = currentStreak
			paren = f" ({bestStreak})" if bestStreak > currentStreak else ""
			display = f"{name}{paren}"
		else:
			value = bestStreak
			name = f" 🔥 {name}" if currentStreak >= bestStreak else name
			display = f"{name}"

		data.append((display, value))

	board = Leaderboard(interaction, title, data)
	await board.start()


@leaderboardGroup.command(
	name="days",
	description=locale_str("commands.lb.days.description")
)
@app_commands.describe(
	channel=locale_str("commands.lb.arg.channel")
)
async def participationDaysLeaderboard(interaction: Interaction, channel: discord.TextChannel | None = None):
	"""Show the top 10 days by count of distinct users with a success message."""
	await interaction.response.defer()
	l = i18n.getChannelLocale(interaction.channel, interaction)
	conn, cursor = connectDb()

	if channel:
		cursor.execute(
			"SELECT id FROM channels WHERE discord_channel_id = ?",
			(str(channel.id),)
		)
		row = cursor.fetchone()
		if not row:
			conn.close()
			return await interaction.followup.send(
				f"❌ {channel.mention} {i18n.t(l, 'commands.lb.errors.not_registered')}. Use `/add channel` first.",
				ephemeral=True
			)
		chan_id = row[0]
		title = f"📅 {i18n.t(l, 'commands.lb.days.title')} #{channel.name}"
		cursor.execute(
			"""
			SELECT DATE(m.timestamp) as day, COUNT(DISTINCT m.user_id) as users_count
			FROM messages m
			WHERE m.category = 'success' AND m.channel_id = ?
			GROUP BY day
			ORDER BY users_count DESC
			LIMIT 10
			""",
			(chan_id,)
		)
	else:
		title = f"📅 {i18n.t(l, 'commands.lb.days.gtitle')}"
		cursor.execute(
			"""
			SELECT DATE(m.timestamp) as day, COUNT(DISTINCT m.user_id) as users_count
			FROM messages m
			WHERE m.category = 'success'
			GROUP BY day
			ORDER BY users_count DESC
			LIMIT 10
			"""
		)

	rows = cursor.fetchall()
	conn.close()

	data: list[tuple[str,int]] = []
	for day, count in rows:
		formatted = datetime.fromisoformat(day).strftime("%d %b, %Y")
		data.append((formatted, count))

	board = Leaderboard(interaction, title, data, itemsPerPage=10, sortReverse=True)
	await board.start()
