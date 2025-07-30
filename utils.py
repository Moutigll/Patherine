import os
import datetime
import importlib

def log(message):
	timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
	print(f"{timestamp} {message}")

def connectDb():
	import sqlite3
	conn = sqlite3.connect("patherine.db")
	cursor = conn.cursor()
	cursor.execute("PRAGMA foreign_keys = ON;")
	return conn, cursor

def loadCommandModules():
	commandsDir = os.path.join(os.path.dirname(__file__), "commands")
	for filename in os.listdir(commandsDir):
		if not filename.endswith(".py") or filename == "__init__.py":
			continue
		moduleName = f"commands.{filename[:-3]}"
		print(f"[DEBUG] Loading command module: {moduleName}")
		importlib.import_module(moduleName)
