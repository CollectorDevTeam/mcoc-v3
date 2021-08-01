from .cdtembed import Embed
from .fetch_data import FetchData
from .cdtcheck import CdtCheck
from .mcoc_math import McocMath

class CDT(Embed, FetchData, CdtCheck, McocMath):
    """Joining core subclasses"""