class GUIError(Exception):
    pass


class ReconstructionError(GUIError):
    pass


class NoWindowError(ReconstructionError):
    pass


class PermissionError(ReconstructionError):
    pass
