from redbot.core import commands

class MODOKException(Exception):
    pass

class QuietUserError(commands.UserInputError):
    pass

class AmbiguousArgError(QuietUserError):
    pass

class MODOKError(QuietUserError):
    pass

class SignatureError(Exception):
    pass

class MissingKabamText(SignatureError):
    pass

class MissingSignatureData(SignatureError):
    pass

class SignatureSchemaError(SignatureError):
    pass

class InsufficientData(SignatureError):
    pass

class LowDataWarning(SignatureError):
    pass

class PoorDataFit(SignatureError):
    pass

# class TitleError(Exception):
#     def __init__(self, champ):
#         self.champ = champ






