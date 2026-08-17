import discord
from discord import app_commands


class AdminSlash(app_commands.Group):
    """
    Slash command group: /mcocadmin
    Admin-only controls for MCOC.
    """

    def __init__(self, core):
        super().__init__(
            name="mcocadmin",
            description="Admin commands for MCOC"
        )
        self.core = core
        self.config = core.config
        try:
            raise Exception("TRACE: AdminSlash init")
        except Exception:
            import traceback
            traceback.print_exc()


    # ---------------------------------------------------------
    # Permission check helper
    # ---------------------------------------------------------
    async def _is_owner(self, interaction: discord.Interaction):
        return await interaction.client.is_owner(interaction.user)

    # ---------------------------------------------------------
    # /mcocadmin setapikey <key>
    # ---------------------------------------------------------
    @app_commands.command(name="setapikey", description="Set the MCOCHUB API key")
    async def setapikey(self, interaction: discord.Interaction, key: str):
        if not await self._is_owner(interaction):
            await interaction.response.send_message(
                "You must be a bot owner to use this command.",
                ephemeral=True
            )
            return

        await self.config.api_key.set(key)
        await interaction.response.send_message("API key saved.")

    # ---------------------------------------------------------
    # /mcocadmin clearapikey
    # ---------------------------------------------------------
    @app_commands.command(name="clearapikey", description="Clear the stored API key")
    async def clearapikey(self, interaction: discord.Interaction):
        if not await self._is_owner(interaction):
            await interaction.response.send_message(
                "You must be a bot owner to use this command.",
                ephemeral=True
            )
            return

        await self.config.api_key.set(None)
        await interaction.response.send_message("API key cleared.")

    # ---------------------------------------------------------
    # /mcocadmin status
    # ---------------------------------------------------------
    @app_commands.command(name="status", description="Show sync and API status")
    async def status(self, interaction: discord.Interaction):
        api_key = await self.config.api_key()
        interval = await self.config.sync_interval()
        metadata = self.core.cache.metadata

        embed = discord.Embed(
            title="CollectorBot Status",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="API Key",
            value="Set" if api_key else "Not Set",
            inline=False
        )

        embed.add_field(
            name="Sync Interval",
            value=f"{interval} hours",
            inline=False
        )

        versions = metadata.get("versions", {})
        if versions:
            version_text = "\n".join(
                f"• {k}: `{v}`" for k, v in versions.items()
            )
        else:
            version_text = "No cache metadata found."

        embed.add_field(
            name="Cached Versions",
            value=version_text,
            inline=False
        )

        await interaction.response.send_message(embed=embed)

    # ---------------------------------------------------------
    # /mcocadmin forcesync
    # ---------------------------------------------------------
    @app_commands.command(name="forcesync", description="Force a full sync from MCOCHUB")
    async def forcesync(self, interaction: discord.Interaction):
        if not await self._is_owner(interaction):
            await interaction.response.send_message(
                "You must be a bot owner to use this command.",
                ephemeral=True
            )
            return

        if not self.core.api:
            await interaction.response.send_message(
                "Cannot sync: API key not set.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        ok = await self.core.sync_data()
        if ok:
            await interaction.followup.send("Sync complete.")
        else:
            await interaction.followup.send("Sync skipped (offline mode).")

    # ---------------------------------------------------------
    # /mcocadmin setsyncinterval <hours>
    # ---------------------------------------------------------
    @app_commands.command(name="setsyncinterval", description="Set sync interval in hours")
    async def setsyncinterval(self, interaction: discord.Interaction, hours: int):
        if not await self._is_owner(interaction):
            await interaction.response.send_message(
                "You must be a bot owner to use this command.",
                ephemeral=True
            )
            return

        if hours < 1:
            await interaction.response.send_message(
                "Sync interval must be at least 1 hour.",
                ephemeral=True
            )
            return

        await self.config.sync_interval.set(hours)
        await interaction.response.send_message(f"Sync interval set to {hours} hours.")
