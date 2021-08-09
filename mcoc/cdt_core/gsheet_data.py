import json
from logging import exception
from ..abc import MixinMeta
import gspread
from redbot.core.commands import Context

# from gsheets import Sheets
XREF = '1JSiGo-oGbPdmlegmGTH7hcurd_HYtkpTnZGY1mN_XCE'
SCHEDULE = '1a-gA4FCaChByM1oMoRn8mI3wx8BsHAJGlU0kbY9gQLE'
SYNERGIES = '1Apun0aUcr8HcrGmIODGJYhr-ZXBCE_lAR7EaFg_ZJDY'
AUNTMAI_PRESTIGE = '17niI72IDVn_dKqKY1pmyP-0soXxsb6bVyJvu4hp3lGU'
AUNTMAI_STATS = '1amDaKVtzG6-v8ioxKP4AE0is8HJ4scFxQTNIY4xg6Ok'

class GoogleSheets(MixinMeta):


    # reference
    # https://docs.gspread.org/en/latest/oauth2.html#for-bots-using-service-account

    async def gs_service_account(self):
        """Retrieve securt project_id, private_key_id, private_key, client_email, client_id, and client_x509_cert_url from self.Config.
        Initiate a GSpread connection to the service account.
        Return the GSpread connection.

        Returns:
            list_of_dicts [list]: list of dictionaries [ {}, {}, {} ] 
        """
        # credentials = {"project_id": None, "private_key": None, "private_key_id": None, "client_email": None, "client_id": None, "client_x509_cert_url": None}
        # async with self.bot.get_shared_api_tokens("gspread") as gspread_tokens:
        # gspread_tokens = await self.bot.get_shared_api_tokens("gspread")
        gspread_tokens = await self.bot.get_shared_api_tokens("gspread")
        if gspread_tokens["filepath"] is None:
            raise exception
        else:
            sheets = gspread.service_account(filename=gspread_tokens["filepath"])
            if sheets is None:
                return None
            else:
                return sheets

    async def cdt_gspread_get_xref(self):
        """Retrieve Champion crossreference id mapping

        Args:
            ctx ([type]): [description]

        Returns:
            list_of_dicts [list]: list of dictionaries [ {}, {}, {} ] 
        """
        sheets = await self.gs_service_account()
        gs = sheets.open_by_key(XREF)
        ws = gs.worksheet("export_xref")

        list_of_dicts = ws.get_all_records()
        return list_of_dicts

    async def cdt_gspread_get_info(self):
        """Retrieve Champion crossreference id mapping

        Args:
            ctx ([type]): [description]

        Returns:
            [type]: [description]
            
        Returns:
            list_of_dicts [list]: list of dictionaries [ {}, {}, {} ] 
        """
        sheets = await self.gs_service_account()
        if sheets is None:
            return None

        gs = sheets.open_by_key(XREF)
        ws = gs.worksheet("export_info")

        list_of_dicts = ws.get_all_records()
        return list_of_dicts

    async def cdt_gspread_get_auntmai_prestige(self):
        """Retrieve list of dictionaries of Auntmai prestige

        Args:
            ctx ([type]): [description]
            
        Returns:
            list_of_dicts [list]: list of dictionaries [ {}, {}, {} ] 
        """
        sheets = await self.gs_service_account()
        if sheets is None:
            return None

        gs = sheets.open_by_key(AUNTMAI_PRESTIGE)
        ws = gs.worksheet("export_prestige")
        list_of_dicts = ws.get_all_records()
        return list_of_dicts

    async def cdt_gspread_get_auntmai_stats(self):
        """Retrieve list of dictionaries of Auntmai stats

        Args:
            ctx ([type]): [description]
            
        Returns:
            list_of_dicts [list]: list of dictionaries [ {}, {}, {} ] 
        """
        sheets = await self.gs_service_account()
        if sheets is None:
            return None

        gs = sheets.open_by_key(AUNTMAI_STATS)
        ws = gs.worksheet("export_stats")
        list_of_dicts = ws.get_all_records()
        return list_of_dicts

    async def cdt_gspread_get_schedule(self):
        """Retrieve Champion crossreference id mapping

        Args:
            ctx ([type]): [description]

        Returns:
            list_of_dicts [list]: list of dictionaries [ {}, {}, {} ] 
        """
        sheets = await self.gs_service_account()
        if sheets is None:
            return None

        gs = sheets.open_by_key(SCHEDULE)
        ws = gs.worksheet("TinySchedule")

        list_of_dicts = ws.get_all_records()
        return list_of_dicts




