"""
A monarch butterfly's life is a natural example of an object whose behavior depends on
completely different external factors before and after a transformation.

Before metamorphosis, the insect is a caterpillar. It feeds exclusively on its host plant
(milkweed, for a monarch). If there are 50 grams of fresh leaves within its foraging range, it
feeds well, builds up energy reserves, and crawls relatively quickly. If only 2 grams are
available, it becomes energy-limited and crawls more slowly. Wind has essentially no effect on
how fast it crawls -- 0 m/s and 5 m/s make little difference.

At some point, having accumulated enough age, the caterpillar undergoes metamorphosis and emerges
as a butterfly. It's still the same "individual", but its needs and behavior have completely
changed.

After metamorphosis, that same property -- locomotion speed -- is now dominated by wind instead
of food. In still air the butterfly flies at its own characteristic airspeed; with a tailwind its
ground speed increases substantially; against a strong headwind its ground speed drops, and it
may struggle to make any forward progress at all. Meanwhile, the amount of host-plant leaf
available nearby has become irrelevant -- adult butterflies don't eat leaves at all, so going
from 2 grams to 50 grams changes nothing about how fast it flies.
"""

from datetime import date

from core_10x.traitable import NamedTraitable, T, RT


EXTERNAL_WORLD_NAME = 'main'

class ExternalWorld(NamedTraitable):
    """
    The external world the insect has no control over.
    """
    current_date: date          = RT()
    leaf_mass_available: float  = RT()      #-- grams of fresh host-plant leaf within reach
    wind_speed: float           = RT()      #-- m/s, signed -- positive = tailwind, negative = headwind

    def current_date_get(self) -> date:
        return date.today()

    @classmethod
    def current(cls):
        return ExternalWorld(EXTERNAL_WORLD_NAME)

class MonarchButterfly(NamedTraitable):
    """
    A monarch's lifecycle: one persistent identity whose locomotion speed depends on completely different
    external factors before and after metamorphosis. `dob` is intrinsic to this "individual".

    Before metamorphosis: a caterpillar, whose crawl speed depends on ExternalWorld's (EW) leaf_mass_available and
    is roughly indifferent to EW's wind_speed.

    After metamorphosis: a butterfly, whose flight speed depends on EW's wind_speed and is indifferent to EW's
    leaf_mass_available.
    """
    s_age_at_metamorphosis_days = 14        #-- the metamorphosis threshold

    dob: date                   = T()
    locomotive_speed: float     = RT()

    def locomotive_speed_get(self) -> float:
        #-- Locomotion speed, in cm/s
        ew = ExternalWorld.current()
        age_days = (ew.current_date - self.dob).days
        if age_days < self.s_age_at_metamorphosis_days:
            return self._caterpillar_speed(ew)
        return self._butterfly_speed(ew)

    def _caterpillar_speed(self, ew: ExternalWorld) -> float:
        #-- energy-limited crawl: more leaf nearby -> faster, saturating; wind is not a factor
        leaf_g = ew.leaf_mass_available
        max_crawl_speed_cmps = 0.5
        half_saturation_g = 10.
        return max_crawl_speed_cmps * leaf_g / (leaf_g + half_saturation_g)

    def _butterfly_speed(self, ew: ExternalWorld) -> float:
        #-- wind-dominated flight: still-air airspeed plus the wind's contribution; leaf mass is no longer relevant as
        #-- adults don't eat leaves
        still_air_speed_cmps = 150.
        wind_contribution_cmps = ew.wind_speed * 100.
        return max(0., still_air_speed_cmps + wind_contribution_cmps)
