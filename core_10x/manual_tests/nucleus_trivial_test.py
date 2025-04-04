if __name__ == '__main__':
    from datetime import datetime, date
    from core_10x.nucleus import Nucleus

    from core_10x.named_constant import Enum, EnumBits

    class COLOR(Enum):
        RED     = ()
        GREEN   = ()
        BLUE    = ()

    class STATE(EnumBits):
        RUNNING     = ()
        SUSPENDED   = ()
        ABORTED     = ()

    data = {
        bool:           False,
        int:            100,
        type(None):     None,
        float:          1e-6,
        complex:        complex(5.43, -7.1),
        str:            'plain text',
        datetime:       datetime.now(),
        date:           date.today(),
        list:           [ 10, 5.1, 'label', datetime.now(), date(2020, 1, 1), ['a', 100], dict( a = 1, b = 2) ],
        tuple:          ( 10, 5.1, 'label', datetime.now(), date(2020, 1, 1), ['a', 100], dict( a = 1, b = 2) ),
        dict:           { 1: 1, 'a': 'abc', 'b': [ 10, 100. ], 'c': dict(x = -100, y = -200) },
        COLOR:          COLOR.GREEN,
        STATE:          STATE.RUNNING | STATE.SUSPENDED
    }

    serialized_data     = { dt: Nucleus.serialize_any(v, False) for dt, v in data.items() }
    deserialized_data   = { dt: Nucleus.deserialize_any(v, None) for dt, v in serialized_data.items() }

    for dt, value in data.items():
        s_value = deserialized_data.get(dt, deserialized_data)
        if s_value is deserialized_data:
            print(f'{dt} is missing')
        else:
            if s_value != value:
                print(f'{dt}:\nexpected\n{value}\ngot\n{s_value}')
