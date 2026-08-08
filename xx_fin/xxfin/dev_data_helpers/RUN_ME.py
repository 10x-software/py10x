def run():
    from xxfin.dev_data_helpers.xxfin_stores_and_associations_create import run
    run()

    from xxfin.dev_data_helpers.fin_calendars_create import run
    run()

    from xxfin.dev_data_helpers.ccys_create import run
    run()

    from xxfin.dev_data_helpers.ir_rate_mkt_conventions_create import run
    run()

    from xxfin.dev_data_helpers.ir_zrc_mkt_data_create import run
    run()

    from xxfin.dev_data_helpers.fx_mkt_conventions_create import run
    run()

    from xxfin.dev_data_helpers.fx_mkt_data_create import run
    run()

    from xxfin.dev_data_helpers.pricing_contexts_create import run
    run()

    from xxfin.dev_data_helpers.basic_mas_create import run
    run()

    from xxfin.dev_data_helpers.bbg_dev_connector_create import run
    run()

if __name__ == '__main__':
    run()

