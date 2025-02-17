from core_10x.nucleus import Nucleus


class NamedConstant(Nucleus):
    """
    In a subclass, each line representing a member must be one of the following:
        MEMBER_NAME = (label, value)    #-- label,          value
        MEMBER_NAME = (label, )         #-- label,          auto-value
        MEMBER_NAME = ()                #-- MEMBER_NAME,    auto-value
        MEMBER_NAME = value             #-- MEMBER_NAME,    value

        where:

        MEMBER_NAME - a valid uppercase identifier
        label       - a string
        value       - any value
        auto-value  - automatically generated (int) value

        NOTE:   all the members must have either explicit or auto-generated values exclusively
    """

    def __init__(self, name = '', label = '', value = None):
        self.name = name
        self.label = label
        self.value = value

    def __eq__(self, other):
        return self.name == other.name

    @classmethod
    def _create(cls, args) -> 'NamedConstant':
        cdef = cls()
        if type(args) is not tuple:     #-- just a value
            cdef.value = args

        else:
            n = len(args)
            if n == 0:      #-- ()
                pass

            elif n == 1:    #-- just a label
                cdef.label = args[0]

            elif n == 2:    #-- (label, value)
                cdef.label = args[0]
                cdef.value = args[1]

            else:
                assert False, f"'{args}' may have at most two items"

        return cdef

    #===================================================================================================================
    #   Nucleus Interface implementation
    #===================================================================================================================

    def to_str(self) -> str:
        return f'{self.__class__.__name__}.{self.name}'

    def to_id(self) -> str:
        return self.name

    def serialize(self, embed: bool) -> str:
        return self.name

    @classmethod
    def deserialize(cls, name: str) -> 'NamedConstant':
        dir = cls.s_dir
        cdef = dir.get(name, dir)
        if cdef is dir:
            raise TypeError(f'{cls} - unknown constant {name}')

        return cdef

    @classmethod
    def from_str(cls, s: str) -> 'NamedConstant':
        return cls.s_dir.get(s)

    @classmethod
    def from_any_xstr(cls, data) -> 'NamedConstant':
        if type(data) is cls.s_data_type:
            reverse_dir = cls.s_reverse_dir
            if reverse_dir:
                return reverse_dir.get(data)

            #-- the last resort - this is slow!
            for cdef in cls.s_dir.values():
                if cdef.value == data:
                    return cdef

        return None

    @classmethod
    def same_values(cls, value1, value2) -> bool:
        return value1 is value2

    @classmethod
    def choose_from(cls):
        return cls.s_dir

    #===================================================================================================================

    s_dir = {}
    s_reverse_dir = {}
    s_data_type = None
    s_default_labels = False
    s_lowercase_values = False
    def __init_subclass__(
        cls,
        default_labels: bool    = None,    #-- if True and a label is not defined, creates it by calling default_label(name)
        lowercase_values: bool  = None,    #-- if a value is not defined, sets it to name, or name.lower() if True
    ):
        dir = cls.s_dir = { name: cls(cdef.name, cdef.label, cdef.value) for name, cdef in cls.s_dir.items() }

        if default_labels is not None:
            cls.s_default_labels = default_labels
        else:
            default_labels = cls.s_default_labels

        if lowercase_values is not None:
            cls.s_lowercase_values = lowercase_values
        else:
            lowercase_values = cls.s_lowercase_values

        data_type = cls.s_data_type
        for name, constant_definition in cls.__dict__.items():
            if not name.isupper():
                continue

            cdef = cls._create(constant_definition)
            cdef.name = name
            if not cdef.label:
                cdef.label = cls.default_label(name) if default_labels else name

            if cdef.value is None:
                value = cls.next_auto_value()
                if value is None:
                    value = name if not lowercase_values else name.lower()
                cdef.value = value

            dt = type(cdef.value)
            if data_type is None:
                data_type = dt
            else:
                assert issubclass(dt, data_type), f'{cls}.{name} must be a subclass of {data_type}'

            dir[name] = cdef

        cls.s_data_type = data_type
        if getattr(data_type, '__hash__', None):    #-- check if data_type is hashable and build the reverse dir if so
             cls.s_reverse_dir = { cdef.value: cdef for cdef in dir.values() }

        for name, cdef in dir.items():
            setattr(cls, name, cdef)

    @classmethod
    def default_label(cls, name: str) -> str:
        return name.title().replace('_', ' ')

    @classmethod
    def next_auto_value(cls):
        return None

class Enum(NamedConstant):
    """
    Enum constants definitions are in a simplified form:
        - an empty tuple (next enum auto value)
        - a string - just a label
    """
    s_last_value = 0
    s_step = 1
    def __init_subclass__(cls, seed: int = None, step: int = None, **kwargs):
        if seed is not None:
            cls.s_last_value = seed
        else:
            cls.s_last_value = cls.s_last_value

        if step is not None:
            cls.s_step = step
        else:
            cls.s_step = cls.s_step

        super().__init_subclass__(**kwargs)

    def __int__(self):
        return self.value

    @classmethod
    def _create(cls, args) -> 'Enum':
        cdef = cls()
        if args == ():
            return cdef

        if type(args) is str:     #-- just a label
            cdef.label = args
            return cdef

        assert False, f'an empty tuple or string is expected'

    @classmethod
    def next_auto_value(cls):
        last_value = cls.s_last_value
        cls.s_last_value += cls.s_step
        return last_value

NO_FLAGS_TAG = 'NONE'
class EnumBits(NamedConstant):

    s_last_flag = 0x1
    def __init_subclass__(cls, **kwargs):
        cls.s_last_flag = cls.s_last_flag
        super().__init_subclass__(**kwargs)
        setattr(cls, NO_FLAGS_TAG, cls(name = NO_FLAGS_TAG, value = 0x0))

    @classmethod
    def next_auto_value(cls):
        mask = cls.s_last_flag
        cls.s_last_flag <<= 1
        return mask

    @classmethod
    def names_from_value(cls, value: int) -> tuple:
        return tuple(name for name, cdef in cls.s_dir.items() if cdef.value & value)

    def __or__(self, other):
        the_value = self.value
        value = the_value | other.value
        if value == the_value:
            return self

        cls = self.__class__
        return cls.from_int(value)

    def __sub__(self, other):
        the_value = self.value
        value = the_value & ~other.value
        if value == the_value:
            return self

        cls = self.__class__
        return cls.from_int(value)

    @classmethod
    def names_to_value(cls, cnames: list) -> int:
        value = 0x0
        dir = cls.s_dir
        for cname in cnames:
            cdef = dir.get(cname)
            if cdef is None:
                raise TypeError(f'{cls} - unknown bit {cname}')

            value |= cdef.value

        return value

    @classmethod
    def from_str(cls, s: str) -> 'EnumBits':
        if not s:
            return getattr(cls, NO_FLAGS_TAG)

        found = cls.s_dir.get(s)
        if found is not None:
            return found

        cnames = s.split('|')
        value = cls.names_to_value(cnames)
        return cls(s, s, value)

    @classmethod
    def from_int(cls, value: int) -> 'EnumBits':
        cnames = cls.names_from_value(value)
        if not cnames:
            return getattr(cls, NO_FLAGS_TAG)

        name = '|'.join(cnames)
        return cls(name, name, value)

    @classmethod
    def from_any_xstr(cls, data) -> 'EnumBits':
        dt = type(data)
        if dt is int:
            return cls.from_int(data)

        elif dt is tuple or dt is list:
            value = cls.names_to_value(data)
            if not value:
                return getattr(cls, NO_FLAGS_TAG)

            name = '|'.join(data)
            return cls(name, name, value)

    @classmethod
    def deserialize(cls, data) -> 'EnumBits':
        return cls.from_str(data)

    @classmethod
    def same_values(cls, value1, value2) -> bool:
        return value1 is value2 or value1.name == value2.name

class ErrorCode(Enum, seed = -1, step = -1):
    def __call__(self, *args, **kwargs):
        return self.label.format(*args, **kwargs)

class NamedConstantValue:
    __slots__ = 'named_constant_class', 'data'

    def __init__(self, named_constant_class, **named_constant_values):
        assert issubclass(named_constant_class, NamedConstant), f'{named_constant_class} must be a subclass of NamedConstant'
        c_defs = named_constant_class.s_dir
        num_values = len(c_defs)
        assert num_values == len(named_constant_values), f'{named_constant_class} - number of named values must be {num_values}'
        self.named_constant_class = named_constant_class

        self.data = data = {}
        for cname, value in named_constant_values.items():
            cdef = c_defs.get(cname)
            assert cdef, f'{named_constant_class}.{cname} - unknown named constant'
            self.process_row( cdef, data, value)

    def process_row(self, cdef: NamedConstant, data: dict, row ):
        data[cdef] = row

    def __getitem__(self, key):
        try:
            return self.data[key]   #-- if it's a known NamedConstant

        except KeyError:
            #-- check if it is a name of a constant
            named_constant_class = self.named_constant_class
            cdef = named_constant_class.s_dir.get(key)
            if not cdef:
               raise KeyError(f'{named_constant_class}.{key} - unknown named constant')

            return self.data[cdef]

    def __setitem__(self, key, value):
        raise AssertionError(f'{self.__class__} - may not be modified')

    def __getattr__(self, key):
        return self.__getitem__(key)

class NamedConstantTable(NamedConstantValue):
    __slots__ = 'named_constant_class', 'data', 'col_named_constant_class'

    def __init__(self, row_nc_class, col_nc_class, **named_tuple_values):
        assert issubclass(col_nc_class, NamedConstant), f'{col_nc_class} must be a subclass of NamedConstant'
        self.col_named_constant_class = col_nc_class
        super().__init__(row_nc_class, **named_tuple_values)

    def process_row(self, cdef: NamedConstant, data: dict, row):
        assert type(row) is tuple, f'{cdef.name} = is not a tuple'
        col_defs = self.col_named_constant_class.s_dir
        assert len(row) == len(col_defs), f'{cdef.name} must have {len(col_defs)} values'
        data[cdef] = NamedConstantValue(
            self.col_named_constant_class,
            **{ col_name: row[i] for i, col_name in enumerate(col_defs) }
        )

