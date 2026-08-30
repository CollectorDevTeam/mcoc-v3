# mcoc/common/cache_status.py
from typing import Any, Dict, Optional
import logging
from .componentsV2 import CDTEmbed, _is_valid_http_url

log = logging.getLogger("red.mcoc.cache_status")

class CacheStatusPoster:
    """
    Helper to post a status embed and update it progressively.
    Usage:
      poster = CacheStatusPoster(ctx, title="Sync status")
      msg = await poster.post_initial()
      await poster.update_section("Champions", "started")
      await poster.update_section("Champions", "complete: 1234 items")
      await poster.update_prestige_line("Tier1 ascended 5* rank 1 synced")
      await poster.finalize("Sync complete")
    """

    def __init__(self, ctx, title: str = "MCOC Sync Status"):
        self.ctx = ctx
        self.title = title
        self.sections: Dict[str, str] = {}
        self.prestige_lines: list[str] = []
        self.message = None

    def _build_embed(self):
        emb = CDTEmbed.embed(self.ctx, title=self.title, description="Progress updates will appear below.", footer_text="Sync progress")
        # add section fields
        for name, value in self.sections.items():
            CDTEmbed.add_field(emb, name=name, value=value or "pending", inline=False)
        if self.prestige_lines:
            CDTEmbed.add_field(emb, name="Prestige", value="\n".join(self.prestige_lines), inline=False)
        return emb

    async def post_initial(self):
        emb = self._build_embed()
        try:
            self.message = await self.ctx.send(embed=emb)
        except Exception:
            log.exception("Failed to post initial cache status embed")
            # try sanitized
            try:
                try:
                    CDTEmbed.set_image(emb, image_url=None)
                except Exception:
                    pass
                self.message = await self.ctx.send(embed=emb)
            except Exception:
                log.exception("Sanitized post failed")
                self.message = None
        return self.message

    async def update_section(self, name: str, value: str):
        self.sections[name] = value
        emb = self._build_embed()
        if self.message:
            try:
                await self.message.edit(embed=emb)
            except Exception:
                log.exception("Failed to edit cache status embed; retrying sanitized")
                try:
                    try:
                        CDTEmbed.set_image(emb, image_url=None)
                    except Exception:
                        pass
                    await self.message.edit(embed=emb)
                except Exception:
                    log.exception("Failed to edit cache status embed (sanitized)")

    async def update_prestige_line(self, line: str):
        self.prestige_lines.append(line)
        await self.update_section("Prestige", "\n".join(self.prestige_lines))

    async def finalize(self, final_text: Optional[str] = None):
        if final_text:
            self.sections["Overall"] = final_text
        await self.update_section("Overall", final_text or "complete")
