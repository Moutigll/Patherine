import io
import time
from datetime import datetime
from typing import List, Tuple

import discord
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from matplotlib.ticker import MaxNLocator
from discord import app_commands

from commands import graphGroup, makeEmbed
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
