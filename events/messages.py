import discord
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from commands import bot
from commands.populateDb import getCategoryFromTime, getUserId, isUserUntracked
from utils.utils import connectDb, log

DEFAULT_TZ = ZoneInfo("Europe/Paris")


# --- DB helpers ---
def getChannelInfo(cursor, discordChannelId: str):
	"""Return (internalId, tzName, discord_role_id) for channel, or None."""
	cursor.execute(
		"SELECT id, timezone, discord_role_id FROM channels WHERE discord_channel_id = ?",
		(discordChannelId,),
	)
	return cursor.fetchone()


def insertMessage(cursor, channelId: int, userId: int, messageId: str, timestampIso: str) -> bool:
	"""
	Insert message as 'success'. Returns True if inserted, False if duplicate.
	"""
	cursor.execute(
		"""
		INSERT INTO messages (channel_id, user_id, message_id, timestamp, category)
		VALUES (?, ?, ?, ?, 'success')
		ON CONFLICT(message_id) DO NOTHING
		""",
		(channelId, userId, messageId, timestampIso),
	)
	cursor.execute("SELECT changes()")
	return cursor.fetchone()[0] > 0


def upsertStreak(cursor, table: str, messageDateIso: str, entityId: int | None = None):
	"""
	Insert or update streaks (user, channel, global):
	- table: 'user_streaks', 'channel_streaks' ou 'global_streak'
	- entityId: user_id or channel_id, None for global_streak
	- messageDateIso: date of the new success message (YYYY-MM-DD)
	"""
	if table == "global_streak":
		# global table: single row
		cursor.execute(f"""
			INSERT INTO {table}(current_streak, max_streak, last_success_date)
			VALUES (1, 1, ?)
			ON CONFLICT(rowid) DO UPDATE SET
				current_streak = CASE
					WHEN DATE(excluded.last_success_date) = DATE({table}.last_success_date, '+1 day')
						THEN {table}.current_streak + 1
					WHEN DATE(excluded.last_success_date) = DATE({table}.last_success_date)
						THEN {table}.current_streak
					ELSE 1
				END,
				max_streak = MAX(
					{table}.max_streak,
					CASE
						WHEN DATE(excluded.last_success_date) = DATE({table}.last_success_date, '+1 day')
							THEN {table}.current_streak + 1
						WHEN DATE(excluded.last_success_date) = DATE({table}.last_success_date)
							THEN {table}.current_streak
						ELSE 1
					END
				),
				last_success_date = CASE
					WHEN DATE(excluded.last_success_date) > DATE({table}.last_success_date)
						THEN excluded.last_success_date
					ELSE {table}.last_success_date
				END
		""", (messageDateIso,))
	else:
		# user_streaks or channel_streaks
		if entityId is None:
			raise ValueError("entityId must be provided for user or channel streaks")

		idColumn = "user_id" if table == "user_streaks" else "channel_id"
		cursor.execute(f"""
			INSERT INTO {table}({idColumn}, current_streak, max_streak, last_success_date)
			VALUES (?, 1, 1, ?)
			ON CONFLICT({idColumn}) DO UPDATE SET
				current_streak = CASE
					WHEN DATE(excluded.last_success_date) = DATE({table}.last_success_date, '+1 day')
						THEN {table}.current_streak + 1
					WHEN DATE(excluded.last_success_date) = DATE({table}.last_success_date)
						THEN {table}.current_streak
					ELSE 1
				END,
				max_streak = MAX(
					{table}.max_streak,
					CASE
						WHEN DATE(excluded.last_success_date) = DATE({table}.last_success_date, '+1 day')
							THEN {table}.current_streak + 1
						WHEN DATE(excluded.last_success_date) = DATE({table}.last_success_date)
							THEN {table}.current_streak
						ELSE 1
					END
				),
				last_success_date = CASE
					WHEN DATE(excluded.last_success_date) > DATE({table}.last_success_date)
						THEN excluded.last_success_date
					ELSE {table}.last_success_date
				END
		""", (entityId, messageDateIso))


def fetchUserRoleIds(cursor, userId: int) -> list[str]:
	"""Return list of role IDs for channels where the user has success messages."""
	cursor.execute(
		"""
		SELECT DISTINCT c.discord_role_id
		FROM channels c
		JOIN messages m ON m.channel_id = c.id
		WHERE m.user_id = ? AND m.category = 'success' AND c.discord_role_id IS NOT NULL
		""",
		(userId,),
	)
	return [r[0] for r in cursor.fetchall() if r[0]]


async def assignRoles(member: discord.Member, guild: discord.Guild, roleIds: list[str]):
	"""Add roles to member if not already present."""
	for roleId in roleIds:
		try:
			role = guild.get_role(int(roleId))
			if role and role not in member.roles:
				await member.add_roles(role, reason="Has rightfully worshipped Catherine!")
		except Exception as e:
			log(f"Failed to add role {roleId} to {member.id}: {e}")


# --- Event handler ---
@bot.event
async def on_message(message: discord.Message):
	# Ignore bots or irrelevant content
	if message.author.bot or "cath" not in message.content.lower():
		return

	conn, cursor = connectDb()
	try:
		# --- Get channel config ---
		ch = getChannelInfo(cursor, str(message.channel.id))
		if not ch:
			return
		internalId, tzName, _ = ch
		tz = ZoneInfo(tzName) if tzName else DEFAULT_TZ

		# --- Local datetime in channel TZ ---
		localDt = message.created_at.replace(tzinfo=timezone.utc).astimezone(tz)

		# Only 'success' messages matter
		category = getCategoryFromTime(localDt.time())
		if category != "success":
			return

		# --- User checks ---
		uidStr = str(message.author.id)
		if isUserUntracked(uidStr, cursor):
			return
		userId = getUserId(conn, cursor, uidStr)

		messageDateIso = localDt.date().isoformat()

		# --- DB transaction: insert + streak update ---
		try:
			conn.execute("BEGIN")
			if not insertMessage(cursor, internalId, userId, str(message.id), localDt.isoformat()):
				conn.rollback()
				return

			# User
			upsertStreak(cursor, "user_streaks", messageDateIso, userId)
			# Channel
			upsertStreak(cursor, "channel_streaks", messageDateIso, internalId)
			# Global
			upsertStreak(cursor, "global_streak", messageDateIso)

			conn.commit()
		except Exception:
			conn.rollback()
			raise

		# --- Post-commit async tasks ---
		try:
			await message.add_reaction("💜")
		except discord.HTTPException:
			pass

		roleIds = fetchUserRoleIds(cursor, userId)
		await assignRoles(message.author, message.guild, roleIds)
		await handleAchievements(conn, cursor, internalId, userId, tzName, message)

	finally:
		try:
			conn.close()
		except Exception:
			pass
