# database/migrations/src/004_add_lang_channels.py
from utils.utils import connectDb

def up(cursor):
	cursor.execute("PRAGMA table_info(channels)")
	columns = [col[1] for col in cursor.fetchall()]
	if "lang" not in columns:
		cursor.execute("""
			ALTER TABLE channels
			ADD COLUMN lang TEXT DEFAULT 'fr'
		""")
	else:
		print("'lang' column already exists in channels.")
