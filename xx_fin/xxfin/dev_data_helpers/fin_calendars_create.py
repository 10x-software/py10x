from xxfin.fin_calendar import KNOWN_CALENDARS, FinCalendar


def run():
    for name in KNOWN_CALENDARS.s_dir:
        FinCalendar(name=name, _replace=True).save().throw()

if __name__ == '__main__':
    run()
