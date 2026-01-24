import json
from pathlib import Path

from discord import app_commands, Locale
from discord.app_commands import locale_str

from utils.utils import connectDb

LOCALES_PATH = Path("locales")
DEFAULT_LOCALE = "en"

class I18n:
	def __init__(self):
		self.translations = {}
		self.loadAll()

	def loadAll(self):
		for file in LOCALES_PATH.iterdir():
			if file.suffix == ".json":
				with open(file, "r", encoding="utf-8") as f:
					self.translations[file.stem] = json.load(f)

	def getLocale(self, interaction):
		locale = interaction.locale.value or DEFAULT_LOCALE
		return locale.split("-")[0]
	
	def getChannelLocale(self, chanId):
		conn, cursor = connectDb()
		cursor.execute("SELECT lang FROM channels WHERE discord_channel_id = ?", (str(chanId),))
		row = cursor.fetchone()
		conn.close()
		if row and row[0] in self.translations:
			return row[0]
		return DEFAULT_LOCALE

	def t(self, locale: str, *keys) -> str:
		# Support both:
		# t("en", "commands.invite.description")
		# t("en", "commands", "invite", "description")

		if len(keys) == 1 and isinstance(keys[0], str):
			parts = keys[0].split(".")
		else:
			parts = keys

		for loc in (locale, DEFAULT_LOCALE):
			data = self.translations.get(loc)
			if not data:
				continue

			current = data
			for part in parts:
				if not isinstance(current, dict):
					current = None
					break
				current = current.get(part)

			if isinstance(current, str):
				return current

		return ".".join(parts)


	def localizations(self, *keys):
		result = {}
		for locale, data in self.translations.items():
			value = data
			for key in keys:
				value = value.get(key)
				if value is None:
					break
			if value:
				result[locale] = value
		return result


class PatherineTranslator(app_commands.Translator):
	async def translate(self, string: locale_str, locale: Locale, context: app_commands.TranslationContext):
		"""
		Returns the translation of the message for the given locale.
		- string: the original text (locale_str)
		- locale: Discord locale (discord.Locale)
		- context: translation context
		"""
		# example: locale "fr" => "fr", "en-US" => "en"
		loc = locale.value.split("-")[0]

		# try with existing i18n
		keys = string.message.split(".") # e.g., "command.add.channel.description" -> ["command", "add", "channel", "description"]
		translated = i18n.t(loc, *keys)

		if translated == "MISSING_TRANSLATION":
			# fallback to English
			translated = string.message

		return translated

i18n = I18n()
