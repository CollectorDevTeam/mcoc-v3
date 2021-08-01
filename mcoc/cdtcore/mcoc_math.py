from ..abc import MixinMeta

class McocMath(MixinMeta):

    @staticmethod
    def from_flat(flat, ch_rating):
        denom = 5 * ch_rating + 1500 + flat
        return round(100 * flat / denom, 2)

    @staticmethod
    def to_flat(per, ch_rating):
        num = (5 * ch_rating + 1500) * per
        return round(num / (100 - per), 2)