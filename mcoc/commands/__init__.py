from mcoc.abc import CompositeMetaClass
from .alliance_data import AllianceData
from .champ_data import ChampData
from .map_data import MapData
from .roster_data import RosterData
from ..abc import CompositeMetaClass

class Commands(AllianceData, ChampData, MapData, RosterData, metaclass=CompositeMetaClass):
    '''Class joining all command subclasses'''

    