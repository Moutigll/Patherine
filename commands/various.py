import discord
from discord import app_commands
from commands import bot

INVITE_PERMISSIONS = discord.Permissions()
INVITE_PERMISSIONS.update(
	send_messages=True,
	read_message_history=True,
	embed_links=True,
	add_reactions=True,
	manage_roles=True
)

@bot.tree.command(name="invite", description="Get the bot invite link.")
async def inviteCommand(interaction: discord.Interaction):
	client_id = bot.user.id
	invite_url = discord.utils.oauth_url(client_id, permissions=INVITE_PERMISSIONS)
	await interaction.response.send_message(f"💜 [Invite Patherine]({invite_url})", ephemeral=True)

@bot.tree.command(name="help", description="Affiche les informations sur le bot et ses commandes")
async def helpCommand(interaction: discord.Interaction):
	embed = discord.Embed(
		title="🤖 Patherine - Aide",
		description="Bot dédié à célébrer Catherine de Médicis chaque jour à 12:06",
		color=discord.Color.purple()
	)
	
	embed.add_field(
		name="🎉 But du bot",
		value="Rendre hommage à **Catherine de Médicis** pour avoir popularisé les pâtes en France/Europe.\n"
			  "Chaque jour à 12:06 dans le salon dédié, le bot vérifie les messages contenant `cath`.",
		inline=False
	)
	
	embed.add_field(
		name="📚 Commandes principales",
		value=(
			"```/help``` Affiche ce message\n"
			"```/invite``` Donne le lien d'invitation du bot\n"
			"```/timezone``` Configure votre fuseau horaire"
		),
		inline=False
	)
	
	embed.add_field(
		name="📊 Statistiques (stat)",
		value=(
			"```/stat global``` - Stats globales\n"
			"```/stat channel [salon:<#salon>]``` - Stats d'un salon spécifique\n"
			"```/stat me``` - Vos stats personnelles\n"
			"```/stat user [utilisateur:@user]``` - Stats d'un membre"
		),
		inline=False
	)
	
	embed.add_field(
		name="🏆 Classements (leaderboard)",
		value=(
			"```/leaderboard messages [salon:<#salon>]```\n"
			"  - Messages validés (salon optionnel)\n\n"
			"```/leaderboard reactions [salon:<#salon>]```\n"
			"  - Réactions reçues (salon optionnel)\n\n"
			"```/leaderboard delays [salon:<#salon>] [worst:True/False] [avg:True/False]```\n"
			"  - `worst` : Afficher les pires délais (défaut=False)\n"
			"  - `avg` : Afficher les moyennes (incompatible avec worst)\n\n"
			"```/leaderboard streaks [salon:<#salon>] [current:True/False]```\n"
			"  - `current` : Afficher les séries en cours (défaut=False)"
			"```/leaderboard days [salon:<#salon>]```\n"
			"  - Classement des jours avec le plus de messages\n"
		),
		inline=False
	)
	
	embed.add_field(
		name="⚙️ Commandes admin",
		value=(
			"```/add admin [utilisateur:@user]```\n"
			"  - Ajoute un admin (OWNER only)\n\n"
			"```/add channel [salon:<#salon>] [role:@role] [tz_name:fuseau]```\n"
			"  - Ajoute un salon à la base de données (ADMIN only)\n"
			"  - `role` : Rôle associé (optionnel)\n"
			"  - `tz_name` : Fuseau horaire (défaut=Europe/Paris)\n\n"
			"```/update channel [salon:<#salon>]```\n"
			"  - Force la mise à jour des données (ADMIN only)\n\n"
		),
		inline=False
	)
	
	embed.add_field(
		name="🔎 Code source",
		value="[GitHub](https://github.com/Moutigll/Patherine)",
		inline=False
	)
	
	await interaction.response.send_message(embed=embed)
