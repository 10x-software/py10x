from typing import Self

from core_10x_i import BNucleus


class Nucleus:
    __slots__           = ()
    ID_TAG              = BNucleus.ID_TAG
    COLLECTION_TAG      = BNucleus.COLLECTION_TAG
    CLASS_TAG           = BNucleus.CLASS_TAG
    REVISION_TAG        = BNucleus.REVISION_TAG

    serialize_any       = BNucleus.serialize_any
    deserialize_any     = BNucleus.deserialize_any

    serialize_type      = BNucleus.serialize_type
    deserialize_type    = BNucleus.deserialize_type
    serialize_complex   = BNucleus.serialize_complex
    deserialize_complex = BNucleus.deserialize_complex
    serialize_date      = BNucleus.serialize_date
    deserialize_date    = BNucleus.deserialize_date
    serialize_list      = BNucleus.serialize_list
    deserialize_list    = BNucleus.deserialize_list
    serialize_dict      = BNucleus.serialize_dict
    deserialize_dict    = BNucleus.deserialize_dict

    #===============================================================================================================================
    #   The following methods must be implemented by a subclass of Nucleus
    #===============================================================================================================================

    def __repr__(self):
        return self.to_str()

    def __eq__(self, other):
        return self.__class__.same_values(self, other)

    def to_str(self) -> str:
        return str(self)

    def to_id(self) -> str:
        return self.to_str()

    def serialize(self, embed: bool):
        raise NotImplementedError

    @classmethod
    def deserialize(cls, serialized_data) -> Self:
        raise NotImplementedError

    @classmethod
    def from_str(cls, s: str) -> Self:
        raise NotImplementedError

    @classmethod
    def from_any_xstr(cls, value) -> Self:
        raise NotImplementedError

    @classmethod
    def from_any(cls, value) -> Self:
        if isinstance(value, cls):
            return value

        if isinstance(value, str):
            return cls.from_str(value)

        return cls.from_any_xstr(value)

    @classmethod
    def same_values(cls, value1, value2) -> bool:
        raise NotImplementedError

    @classmethod
    def choose_from(cls):
        return {}
