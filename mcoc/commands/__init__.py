# from .user_data import ProfileData
# from .alliance_data import AllianceData
# from .champ_data import ChampData
# from .map_data import MapData
# from .roster_data import RosterData
from .modoksays import MODOKSays
from ..abc import CompositeMetaClass

# class Commands(AllianceData, ChampData, MapData, RosterData, metaclass=CompositeMetaClass):

class Commands(MODOKSays, metaclass=CompositeMetaClass):

    '''Class joining all command subclasses'''

    