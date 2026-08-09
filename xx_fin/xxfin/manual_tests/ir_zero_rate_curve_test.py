if __name__ == '__main__':
    from datetime import date

    from xxfin.ir_zero_rate_curve import ZeroRateCurve
    from xxfin.snapshot import SNAPSHOT

    sofr = dict(
        provider_name   ='XX_DEV',
        mkt_name        ='SOFR',
        # md_date         = date(2025, 3, 12),  ## flat
        # md_date         =date(2025, 5, 22),   ## hump
        # md_date         =date(2025, 5, 30),   ## flat (?)
        # md_date         =date(2025, 7, 3),    ## super steep
        md_date         =date(2025, 10, 10),    ## not steep
        snapshot        =SNAPSHOT.CLOSE,
    )

    sonia = dict(
        provider_name   ='XX_DEV',
        mkt_name        ='SONIA',
        # md_date         = date(2025, 3, 12),  ## flat
        # md_date         =date(2025, 5, 30),   ## steep
        md_date         =date(2025, 5, 22),   ## downward
        # md_date         =date(2025, 7, 3),    ## super steep ; start < 0
        # md_date         =date(2025, 10, 10),    ## not steep; start < 0
        snapshot        =SNAPSHOT.CLOSE,
    )

    zrc = ZeroRateCurve(**sofr)

    mas = zrc.mkt_assembly_object
    res = zrc.payload

    for dv in res.dates_values():
        print(f'{dv[0]} , {dv[1] * 100}')

    # r = res.rate_fwd(date(2025, 10, 14), date(2025, 10, 22))

    # import matplotlib.pyplot as plt
    #
    # plt.figure(figsize=(12, 8))
    # plt.plot(res.dates, res.values, market = 'o')
    # plt.grid = True
    # plt.tight_layout()
    # plt.show()