import discord
import discord.app_commands

class PagesMenu(discord.ui.View):
    def __init__(self, pages, user, timeout=60):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.user = user
        self.page = 0

        # Disable buttons if only one page
        if len(pages) <= 1:
            for item in self.children:
                item.disabled = True

    @staticmethod
    def add_page_numbers(pages):
        for i, embed in enumerate(pages):
            embed.set_footer(text=f"Page {i+1} of {len(pages)}")
        return pages

    # -----------------------------
    # Permission: only invoking user
    # -----------------------------
    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.user.id

    # -----------------------------
    # Button: First Page
    # -----------------------------
    @discord.ui.button(label="≪", style=discord.ButtonStyle.secondary)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)

    # -----------------------------
    # Button: Previous Page
    # -----------------------------
    @discord.ui.button(label="‹", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = (self.page - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)

    # -----------------------------
    # Button: Close
    # -----------------------------
    @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        self.stop()

    # -----------------------------
    # Button: Next Page
    # -----------------------------
    @discord.ui.button(label="›", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = (self.page + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)

    # -----------------------------
    # Button: Last Page
    # -----------------------------
    @discord.ui.button(label="≫", style=discord.ButtonStyle.secondary)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = len(self.pages) - 1
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)
