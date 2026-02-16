if __name__ == '__main__':

    from datetime import date

    from xx_common.xxcalendar import Calendar, CalendarAdjustment

    us_c = Calendar(_replace = True,
        name                = 'US',
        non_working_days    = [
            date(2025,1,1), date(2025,1,20), date(2025,2,17), date(2025,5,26), date(2025,7,4),
            date(2025,9,1), date(2025,10,13), date(2025,11,11), date(2025,11,27), date(2025,12, 25)
        ]
    )

    uk_c = Calendar(_replace = True,
        name                = 'UK',
        non_working_days    = [
            date(2025,1,1), date(2025,4,18), date(2025,5,5), date(2025,5,26), date(2025,8,25),
            date(2025,12, 25), date(2025,12, 26)
        ]
    )

    c = Calendar.union('US', 'UK')
    union_nwds = c.non_working_days

    c2 = Calendar.intersection('US', 'UK')
    cross_nwds = c2.non_working_days

    sofr_adjust = CalendarAdjustment(_replace = True,
        name        = 'SOFR',
        add_days    = [date(2019, 4, 4)]
    )

    ca = Calendar(name = 'US', adjusted_for = 'SOFR')
    nwds_ca = ca.non_working_days
