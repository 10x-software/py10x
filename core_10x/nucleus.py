from __future__ import annotations

from core_10x_i import BNucleus


class Nucleus:
    # fmt: off
    __slots__           = ()
    TYPE_TAG            = BNucleus.TYPE_TAG
    CLASS_TAG           = BNucleus.CLASS_TAG
    REVISION_TAG        = BNucleus.REVISION_TAG
    OBJECT_TAG          = BNucleus.OBJECT_TAG
    COLLECTION_TAG      = BNucleus.COLLECTION_TAG
    ID_TAG              = BNucleus.ID_TAG
    NX_RECORD_TAG       = BNucleus.NX_RECORD_TAG
    TYPE_RECORD_TAG     = BNucleus.TYPE_RECORD_TAG
    PICKLE_RECORD_TAG   = BNucleus.PICKLE_RECORD_TAG

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
    deserialize_record  = BNucleus.deserialize_record
    # fmt: on
    # ===============================================================================================================================
    #   The following methods must be implemented by a subclass of Nucleus
    # ===============================================================================================================================

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
    def deserialize(cls, serialized_data) -> Nucleus:
        raise NotImplementedError

    @classmethod
    def from_str(cls, s: str) -> Nucleus:
        raise NotImplementedError

    @classmethod
    def from_any_xstr(cls, value) -> Nucleus:
        raise NotImplementedError

    @classmethod
    def from_any(cls, value) -> Nucleus:
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
