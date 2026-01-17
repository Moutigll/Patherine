def up(cursor):
	cursor.execute(
		"""
		CREATE TABLE IF NOT EXISTS user_streaks (
			user_id INTEGER PRIMARY KEY,
			category TEXT NOT NULL,
			current_streak INTEGER NOT NULL DEFAULT 0,
			max_streak INTEGER NOT NULL DEFAULT 0,
			last_success_date DATE NOT NULL,
			FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
		);
		"""
	)
