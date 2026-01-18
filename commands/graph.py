import discord
import matplotlib.pyplot as plt
import io
import time
from matplotlib.dates import DateFormatter, date2num
from matplotlib.ticker import MaxNLocator
from datetime import datetime
from discord import app_commands

from commands import graphGroup, makeEmbed
from utils.utils import connectDb, log

MAX_POINTS = 75  # Nombre max de points affichés

@graphGroup.command(name="users", description="Show a graph of user participation over time")
@app_commands.describe(total="Show total participation instead of daily", points="Maximum number of points to display")
async def graphUsersCommand(interaction: discord.Interaction, total: bool = False, points: int = MAX_POINTS):
	await interaction.response.defer()

	if points < 10 or points > 150:
		await interaction.followup.send("Points parameter must be between 10 and 150.")
		return

	start_time = time.perf_counter()
	conn, cursor = connectDb()
	try:
		if total:
			cursor.execute("""
				SELECT MIN(DATE(timestamp, 'localtime')) AS first_seen, user_id
				FROM messages
				WHERE category='success'
				GROUP BY user_id
				ORDER BY first_seen
			""")
			rows = cursor.fetchall()
			# Count occurrences per day
			dates_count = {}
			for day_str, _ in rows:
				dates_count[day_str] = dates_count.get(day_str, 0) + 1

			sorted_dates = sorted(dates_count)
			cumulative_counts = []
			total_users = 0
			for d in sorted_dates:
				total_users += dates_count[d]
				cumulative_counts.append(total_users)

			dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in sorted_dates]
			user_counts = cumulative_counts
		else:
			cursor.execute("""
				SELECT DATE(timestamp, 'localtime') AS day, COUNT(DISTINCT user_id) AS user_count
				FROM messages
				WHERE category='success'
				GROUP BY day
				ORDER BY day
			""")
			data = cursor.fetchall()
			if not data:
				await interaction.followup.send("No data available to generate the graph.")
				return

			dates = [datetime.strptime(d, "%Y-%m-%d").date() for d, _ in data]
			user_counts = [count for _, count in data]
	finally:
		conn.close()

	# --- Downsample if too many points ---
	if len(dates) > points:
		step = len(dates) / points
		new_dates = []
		new_counts = []
		for i in range(points):
			start = int(i * step)
			end = int((i + 1) * step)
			segment_dates = dates[start:end]
			segment_counts = user_counts[start:end]
			# Moyenne des counts
			avg_count = sum(segment_counts) / len(segment_counts)
			new_dates.append(segment_dates[len(segment_dates)//2])  # Date centrale du segment
			new_counts.append(avg_count)
		dates, user_counts = new_dates, new_counts

	# --- Plotting ---
	plt.figure(figsize=(12, 6))
	plt.plot(dates, user_counts, marker='o', color="#5865F2", linewidth=2)
	plt.title("Total User Participation" if total else "Daily User Participation", fontsize=16)
	plt.xlabel("Date", fontsize=12)
	plt.ylabel("Number of Users", fontsize=12)
	plt.grid(alpha=0.3)

	plt.gca().xaxis.set_major_formatter(DateFormatter("%Y-%m-%d"))
	plt.gca().xaxis.set_major_locator(MaxNLocator(nbins=20, prune='both'))
	plt.xticks(rotation=45)
	plt.tight_layout()

	# --- Save plot to buffer ---
	buffer = io.BytesIO()
	plt.savefig(buffer, format='png')
	buffer.seek(0)
	plt.close()

	elapsed = time.perf_counter() - start_time
	dest = interaction.guild.name if interaction.guild else interaction.user.name + " (DM)"
	log(f"Graph: {'total' if total else 'daily'} user participation generated in {elapsed:.2f} seconds for {dest}.")
	file = discord.File(buffer, filename='user_participation_graph.png')
	embed = makeEmbed(
		title="User Participation Graph",
		description=f"{'Total' if total else 'Daily'} user participation over time.\n"
	)
	embed.set_footer(text=f"Generated in {elapsed:.2f} seconds.")
	embed.set_image(url="attachment://user_participation_graph.png")

	await interaction.followup.send(embed=embed, file=file)
