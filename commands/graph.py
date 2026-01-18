import io
import time
from datetime import date, datetime, timedelta
from typing import List, Tuple

import discord
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from matplotlib.ticker import MaxNLocator
from discord import app_commands

from commands import graphGroup, makeEmbed
from commands.leaderboard import getUsername
from utils.utils import connectDb, log

MAX_POINTS_DEFAULT = 75
MIN_POINTS = 10
MAX_POINTS = 150


# --- Helpers ---
def downsampleWithAverage(dates: List[datetime.date], counts: List[float], max_points: int
							 ) -> Tuple[List[datetime.date], List[float]]:
	"""
	Downsample (with averaging) long time series to at most max_points while
	ensuring the first and last date remain as endpoints.
	Returns (new_dates, new_counts).
	"""
	if len(dates) <= max_points:
		return dates, counts

	# Reserve first and last, split the middle into (max_points - 2) segments
	target_middle = max_points - 2
	step = (len(dates) - 2) / target_middle
	new_dates = [dates[0]]
	new_counts = [counts[0]]

	for i in range(target_middle):
		start = 1 + int(i * step)
		end = 1 + int((i + 1) * step)
		seg_dates = dates[start:end] or [dates[start]]
		seg_counts = counts[start:end] or [counts[start]]
		avg = sum(seg_counts) / len(seg_counts)
		mid_date = seg_dates[len(seg_dates) // 2]
		new_dates.append(mid_date)
		new_counts.append(avg)

	new_dates.append(dates[-1])
	new_counts.append(counts[-1])
	return new_dates, new_counts


def plotToBuffer(dates: List[datetime.date], counts: List[float], title: str, ylabel: str) -> io.BytesIO:
	"""
	Create a matplotlib plot and return it as a BytesIO PNG buffer.
	"""
	plt.figure(figsize=(12, 6))
	plt.plot(dates, counts, marker='o', linewidth=2)
	plt.title(title, fontsize=16)
	plt.xlabel("Date", fontsize=12)
	plt.ylabel(ylabel, fontsize=12)
	plt.grid(alpha=0.28)
	ax = plt.gca()
	ax.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d"))
	ax.xaxis.set_major_locator(MaxNLocator(nbins=20, prune='both'))
	plt.xticks(rotation=45)
	plt.tight_layout()

	buf = io.BytesIO()
	plt.savefig(buf, format="png")
	buf.seek(0)
	plt.close()
	return buf


def makeGraphEmbed(title: str, description: str, filename: str, elapsed_seconds: float) -> discord.Embed:
	"""
	Create an embed that places the image (attachment) above the description
	and uses set_footer for the generation time (so footer is rendered by Discord).
	"""
	embed = makeEmbed(title=title, description=description)
	embed.set_image(url=f"attachment://{filename}")
	embed.set_footer(text=f"Generated in {elapsed_seconds:.2f} s")
	return embed


#--- Commands ---
@graphGroup.command(name="users", description="Show a graph of user participation over time")
@app_commands.describe(
	total="Show total (cumulative) users instead of daily unique users",
	points=f"Maximum number of points to display (between {MIN_POINTS} and {MAX_POINTS})"
)
async def graphUsersCommand(interaction: discord.Interaction, total: bool = False, points: int = MAX_POINTS_DEFAULT):
	"""Generate and send a user participation graph."""
	await interaction.response.defer()

	if points < MIN_POINTS or points > MAX_POINTS:
		await interaction.followup.send(f"Points parameter must be between {MIN_POINTS} and {MAX_POINTS}.")
		return

	start = time.perf_counter()
	conn, cursor = connectDb()
	try:
		if total:
			# For cumulative users: take first_seen date per user, count new users per day, then cumulative
			cursor.execute("""
				SELECT MIN(DATE(timestamp, 'localtime')) AS first_seen, user_id
				FROM messages
				WHERE category = 'success'
				GROUP BY user_id
				ORDER BY first_seen
			""")
			rows = cursor.fetchall()
			if not rows:
				await interaction.followup.send("No data available to generate the graph.")
				return

			per_day = {}
			for day_str, _ in rows:
				per_day[day_str] = per_day.get(day_str, 0) + 1

			sorted_days = sorted(per_day.keys())
			dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in sorted_days]
			counts = []
			acc = 0
			for d in sorted_days:
				acc += per_day[d]
				counts.append(acc)
		else:
			# Daily distinct users
			cursor.execute("""
				SELECT DATE(timestamp, 'localtime') AS day, COUNT(DISTINCT user_id) AS user_count
				FROM messages
				WHERE category = 'success'
				GROUP BY day
				ORDER BY day
			""")
			rows = cursor.fetchall()
			if not rows:
				await interaction.followup.send("No data available to generate the graph.")
				return
			dates = [datetime.strptime(d, "%Y-%m-%d").date() for d, _ in rows]
			counts = [v for _, v in rows]
	finally:
		try:
			conn.close()
		except Exception:
			pass

	# Downsample while preserving endpoints
	dates, counts = downsampleWithAverage(dates, counts, points)

	# Ensure x-limits include first and last recorded day
	buf = plotToBuffer(dates, counts, ("Total User Participation" if total else "Daily User Participation"), "Number of Users")

	elapsed = time.perf_counter() - start
	filename = "user_participation_graph.png"
	log(f"Graph(users): {'total' if total else 'daily'} generated in {elapsed:.2f}s for {interaction.guild.name if interaction.guild else interaction.user}")
	file = discord.File(buf, filename=filename)
	embed = makeGraphEmbed(
		title="User Participation Graph",
		description=f"{'Total' if total else 'Daily'} user participation over time.",
		filename=filename,
		elapsed_seconds=elapsed
	)
	await interaction.followup.send(embed=embed, file=file)


@graphGroup.command(name="messages", description="Show a graph of messages sent over time")
@app_commands.describe(
	total="Show total (cumulative) messages instead of daily counts",
	points=f"Maximum number of points to display (between {MIN_POINTS} and {MAX_POINTS})"
)
async def graphMessagesCommand(interaction: discord.Interaction, total: bool = False, points: int = MAX_POINTS_DEFAULT):
	"""Generate and send a messages-per-day graph."""
	await interaction.response.defer()

	if points < MIN_POINTS or points > MAX_POINTS:
		await interaction.followup.send(f"Points parameter must be between {MIN_POINTS} and {MAX_POINTS}.")
		return

	start = time.perf_counter()
	conn, cursor = connectDb()
	try:
		if total:
			# Daily message counts, then cumulative
			cursor.execute("""
				SELECT DATE(timestamp, 'localtime') AS day, COUNT(*) AS message_count
				FROM messages
				WHERE category = 'success'
				GROUP BY day
				ORDER BY day
			""")
			rows = cursor.fetchall()
			if not rows:
				await interaction.followup.send("No data available to generate the graph.")
				return
			dates = [datetime.strptime(d, "%Y-%m-%d").date() for d, _ in rows]
			counts = []
			acc = 0
			for _, c in rows:
				acc += c
				counts.append(acc)
		else:
			# Daily message counts
			cursor.execute("""
				SELECT DATE(timestamp, 'localtime') AS day, COUNT(*) AS message_count
				FROM messages
				WHERE category = 'success'
				GROUP BY day
				ORDER BY day
			""")
			rows = cursor.fetchall()
			if not rows:
				await interaction.followup.send("No data available to generate the graph.")
				return
			dates = [datetime.strptime(d, "%Y-%m-%d").date() for d, _ in rows]
			counts = [v for _, v in rows]
	finally:
		try:
			conn.close()
		except Exception:
			pass

	# Downsample while preserving endpoints
	dates, counts = downsampleWithAverage(dates, counts, points)

	buf = plotToBuffer(dates, counts, ("Total Messages" if total else "Daily Messages"), "Number of Messages")

	elapsed = time.perf_counter() - start
	filename = "messages_graph.png"
	log(f"Graph(messages): {'total' if total else 'daily'} generated in {elapsed:.2f}s for {interaction.guild.name if interaction.guild else interaction.user}")
	file = discord.File(buf, filename=filename)
	embed = makeGraphEmbed(
		title="Messages Graph",
		description=f"{'Total' if total else 'Daily'} messages over time.",
		filename=filename,
		elapsed_seconds=elapsed
	)
	await interaction.followup.send(embed=embed, file=file)


#-----------------------------
#    Streaks Graph Command
#-----------------------------

g_streakHistoryCache = {
	"day": None,
	"data": None
}

def computeBestStreakTimeline(days: List[datetime.date]
							 ) -> Tuple[List[datetime.date], List[int]]:
	if not days:
		return [], []

	dates = []
	values = []

	currentStreak = 0
	maxStreak = 0
	prevDay = None

	for day in days:
		if prevDay and day == prevDay + timedelta(days=1):
			currentStreak += 1
		else:
			currentStreak = 1

		if currentStreak > maxStreak:
			maxStreak = currentStreak
			dates.append(day)
			values.append(maxStreak)

		prevDay = day

	return dates, values


def getTopStreaksHistory(cursor) -> List[dict]:
	today = date.today()

	if g_streakHistoryCache["day"] == today:
		return g_streakHistoryCache["data"]

	cursor.execute("""
		SELECT us.user_id, u.discord_user_id, us.max_streak
		FROM user_streaks us
		JOIN users u ON u.id = us.user_id
		ORDER BY us.max_streak DESC
		LIMIT 10
	""")
	users = cursor.fetchall()

	result = []

	for _, discordUserId, _ in users:
		cursor.execute("""
			SELECT DISTINCT DATE(m.timestamp, 'localtime') AS day
			FROM messages m
			JOIN users u ON u.id = m.user_id
			WHERE m.category = 'success'
			AND u.discord_user_id = ?
			ORDER BY day
		""", (discordUserId,))
		rows = cursor.fetchall()

		days = [datetime.strptime(d, "%Y-%m-%d").date() for d, in rows]
		dates, values = computeBestStreakTimeline(days)

		if dates:
			result.append({
				"discord_user_id": int(discordUserId),
				"dates": dates,
				"values": values
			})

	g_streakHistoryCache["day"] = today
	g_streakHistoryCache["data"] = result
	return result


def plotStreaksToBuffer(usersData: List[dict]) -> io.BytesIO:
	plt.figure(figsize=(13, 7))

	for userData in usersData:
		dates = userData["dates"]
		values = userData["values"]
		username = userData.get("username", "Unknown user")

		# Filter out intermediate consecutive dates for clarity
		if dates:
			filtered_dates = [dates[0]]
			filtered_values = [values[0]]

			if len(dates) > 2:
				for i in range(1, len(dates)-1):
					if dates[i] != dates[i-1] + timedelta(days=1) or dates[i] != dates[i+1] - timedelta(days=1):
						filtered_dates.append(dates[i])
						filtered_values.append(values[i])
			filtered_dates.append(dates[-1])
			filtered_values.append(values[-1])

			dates, values = filtered_dates, filtered_values

		plt.plot(
			dates,
			values,
			marker="o",
			linewidth=2,
			label=username
		)

	plt.title("Best Streak Progression (Top 10 Users)", fontsize=16)
	plt.xlabel("Date", fontsize=12)
	plt.ylabel("Best streak achieved", fontsize=12)
	plt.grid(alpha=0.3)

	ax = plt.gca()
	ax.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d"))
	ax.xaxis.set_major_locator(MaxNLocator(nbins=15, prune="both"))
	plt.xticks(rotation=45)

	plt.legend(
		title="User",
		fontsize=9,
		title_fontsize=10,
		loc="upper left"
	)

	plt.tight_layout()

	buf = io.BytesIO()
	plt.savefig(buf, format="png")
	buf.seek(0)
	plt.close()

	return buf


@graphGroup.command(name="streaks", description="Show best streak progression for top 10 users")
async def graphStreaksCommand(interaction: discord.Interaction):
	await interaction.response.defer()

	start = time.perf_counter()
	conn, cursor = connectDb()
	try:
		usersData = getTopStreaksHistory(cursor)
		if not usersData:
			await interaction.followup.send("No streak data available.")
			return
	finally:
		try:
			conn.close()
		except Exception:
			pass

	for userData in usersData:
		discordUserId = int(userData["discord_user_id"])
		username = await getUsername(discordUserId, interaction)
		maxStreak = userData.get("values", [])[-1] if userData.get("values") else 0
		userData["username"] = f"{username} - {maxStreak}"


	buf = plotStreaksToBuffer(usersData)

	elapsed = time.perf_counter() - start
	filename = "streaks_graph.png"

	log(f"Graph(streaks): generated in {elapsed:.2f}s")

	file = discord.File(buf, filename=filename)
	embed = makeGraphEmbed(
		title="Best Streak Progression",
		description="Top 10 users by max streak – progression of record streaks over time.",
		filename=filename,
		elapsed_seconds=elapsed
	)

	await interaction.followup.send(embed=embed, file=file)
