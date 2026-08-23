# mcoc/pagination.py
import typing
import asyncio

# Keep top-level imports minimal; import discord lazily inside methods to remain import-neutral.
class PagesMenu:
    """
    A simple paginated View for discord.py v2+.
    - Instantiate with a list of discord.Embed (or embed-like objects) and the invoking user.
    - Safe to import in common modules because discord is imported lazily.
    """

    def __init__(self, pages: typing.List[typing.Any], user: typing.Any, timeout: int = 60):
        # store raw values; do not import discord at module import time
        self.pages = pages or []
        self.user = user
        self.page = 0
        self.timeout = timeout
        self._view = None  # will hold the actual discord.ui.View instance once created

    @staticmethod
    def add_page_numbers(pages: typing.List[typing.Any]) -> typing.List[typing.Any]:
        """
        Add "Page X of Y" footer to each embed-like object.
        Works with discord.Embed or dict-like fallbacks.
        """
        total = len(pages)
        out = []
        for i, embed in enumerate(pages):
            try:
                # discord.Embed case
                import discord
                if isinstance(embed, discord.Embed):
                    e = embed
                    try:
                        e.set_footer(text=f"Page {i+1} of {total}")
                    except Exception:
                        pass
                    out.append(e)
                    continue
            except Exception:
                pass

            # dict-like fallback
            if isinstance(embed, dict):
                e = dict(embed)
                footer = e.get("footer", {})
                if isinstance(footer, dict):
                    footer_text = footer.get("text", "")
                    footer_text = f"{footer_text} | Page {i+1} of {total}" if footer_text else f"Page {i+1} of {total}"
                    e["footer"] = {"text": footer_text, "icon_url": footer.get("icon_url")}
                else:
                    e["footer"] = {"text": f"Page {i+1} of {total}"}
                out.append(e)
            else:
                out.append(embed)
        return out

    # -----------------------------
    # Build the actual discord View lazily
    # -----------------------------
    def _build_view(self):
        """
        Create and return a discord.ui.View instance with buttons wired to callbacks.
        This is created lazily so importing this module doesn't require discord.
        """
        try:
            import discord
        except Exception:
            raise RuntimeError("discord library not available in this environment")

        class _View(discord.ui.View):
            def __init__(self, outer: "PagesMenu"):
                super().__init__(timeout=outer.timeout)
                self.outer = outer
                # disable buttons if only one page
                if len(outer.pages) <= 1:
                    for item in self.children:
                        item.disabled = True

            async def interaction_check(self, interaction: "discord.Interaction") -> bool:
                if interaction.user.id != self.outer.user.id:
                    try:
                        await interaction.response.send_message("You cannot control this menu.", ephemeral=True)
                    except Exception:
                        pass
                    return False
                return True

            @discord.ui.button(label="≪", style=discord.ButtonStyle.secondary)
            async def first_page(self, interaction: "discord.Interaction", button: "discord.ui.Button"):
                self.outer.page = 0
                await self._update(interaction)

            @discord.ui.button(label="‹", style=discord.ButtonStyle.secondary)
            async def prev_page(self, interaction: "discord.Interaction", button: "discord.ui.Button"):
                self.outer.page = (self.outer.page - 1) % max(1, len(self.outer.pages))
                await self._update(interaction)

            @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
            async def close(self, interaction: "discord.Interaction", button: "discord.ui.Button"):
                try:
                    await interaction.message.delete()
                except Exception:
                    try:
                        await interaction.response.edit_message(content="Menu closed.", embed=None, view=None)
                    except Exception:
                        pass
                self.stop()

            @discord.ui.button(label="›", style=discord.ButtonStyle.secondary)
            async def next_page(self, interaction: "discord.Interaction", button: "discord.ui.Button"):
                self.outer.page = (self.outer.page + 1) % max(1, len(self.outer.pages))
                await self._update(interaction)

            @discord.ui.button(label="≫", style=discord.ButtonStyle.secondary)
            async def last_page(self, interaction: "discord.Interaction", button: "discord.ui.Button"):
                self.outer.page = max(0, len(self.outer.pages) - 1)
                await self._update(interaction)

            async def _update(self, interaction: "discord.Interaction"):
                # safe edit with fallbacks
                try:
                    await interaction.response.edit_message(embed=self.outer.pages[self.outer.page], view=self)
                except Exception:
                    try:
                        await interaction.message.edit(embed=self.outer.pages[self.outer.page], view=self)
                    except Exception:
                        try:
                            await interaction.response.send_message("Unable to update page.", ephemeral=True)
                        except Exception:
                            pass

        return _View(self)

    # -----------------------------
    # Public helpers to start the menu
    # -----------------------------
    async def start(self, ctx_or_interaction):
        """
        Start the menu. Accepts a Context or an Interaction.
        Returns the created View instance.
        """
        # prepare pages with page numbers
        self.pages = self.add_page_numbers(self.pages)

        # build view lazily
        if self._view is None:
            self._view = self._build_view()
            # after self._view = self._build_view()
            if len(self.pages) <= 1:
                for item in self._view.children:
                    try:
                        item.disabled = True
                    except Exception:
                        pass


        # send initial message depending on context type
        try:
            import discord
            if isinstance(ctx_or_interaction, discord.Interaction):
                await ctx_or_interaction.response.send_message(embed=self.pages[self.page], view=self._view, ephemeral=False)
                return self._view
            else:
                # assume a Context-like object with send()
                msg = await ctx_or_interaction.send(embed=self.pages[self.page], view=self._view)
                return self._view
        except Exception:
            # last-resort: try to call send on the object and ignore failures
            try:
                await ctx_or_interaction.send(embed=self.pages[self.page])
            except Exception:
                pass
            return self._view

    def stop(self):
        """Stop the underlying view if it exists."""
        if self._view is not None:
            try:
                self._view.stop()
            except Exception:
                pass
