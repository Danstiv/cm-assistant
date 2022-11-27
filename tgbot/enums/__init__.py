from enum import IntEnum, auto


class Category(IntEnum):
    INITIALIZE = auto()
    MAIN = auto()
    RESTORE = auto()
    FINISH = auto()
    FINALIZE = auto()


class QuoteReplyMode(IntEnum):
    OFF = auto()
    ON = auto()
    PYROGRAM = auto()


class PaginatorMode(IntEnum):
    NO_PAGES = auto()
    NO_TOTAL_PAGES = auto()
    STANDARD = auto()


class Gender(IntEnum):
    MALE = auto()
    FEMALE = auto()
