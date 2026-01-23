import json
from pathlib import Path

from discord import app_commands, Locale
from discord.app_commands import locale_str

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

	def t(self, locale, *keys):
		data = self.translations.get(locale) or self.translations[DEFAULT_LOCALE]

		for key in keys:
			data = data.get(key)
			if data is None:
				return "MISSING_TRANSLATION"
		return data

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
		keys = string.message.split(".")  # if you pass "commands.help.description"
		translated = i18n.t(loc, *keys)

		if translated == "MISSING_TRANSLATION":
			# fallback to English
			translated = string.message

		return translated

i18n = I18n()
