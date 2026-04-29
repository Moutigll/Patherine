def up(cursor):
	"""
	Cleans up excess success messages:
	1. Keeps at most 1 success message per (user, channel, day)
	2. Keeps at most 3 success messages per (user, day) across all channels
	"""
	# Retrieve the IDs of messages to delete (to avoid OFFSET in subqueries)
	# Step 1: remove duplicates by user/channel/day
	cursor.execute("""
		DELETE FROM messages
		WHERE category = 'success'
		  AND id NOT IN (
			  SELECT MIN(id)
			  FROM messages
			  WHERE category = 'success'
			  GROUP BY user_id, channel_id, DATE(timestamp)
		  )
	""")
	deleted1 = cursor.rowcount

	# Step 2: keep only the first 3 success messages per user/day (across all channels)
	cursor.execute("""
		DELETE FROM messages
			WHERE category = 'success'
			  AND id IN (
				  SELECT id
				  FROM (
					  SELECT id,
							 ROW_NUMBER() OVER (
								 PARTITION BY user_id, DATE(timestamp)
								 ORDER BY timestamp   -- les plus anciens en premier
							 ) AS rn
					  FROM messages
					  WHERE category = 'success'
				  ) ranked
				  WHERE rn > 3   -- supprime les 4ème, 5ème, etc.
			  )
	""")
	deleted2 = cursor.rowcount
	print(f"Deleted {deleted1} excess success messages by user/channel/day and {deleted2} excess success messages by user/day")
