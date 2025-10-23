if __name__ == '__main__':

       from core_10x.rdate import RDate, BIZDAY_ROLL_RULE, TENOR_FREQUENCY, TENOR_PARAMS, FREQUENCY_TABLE


       r = RDate('3M')
       r2 = RDate('10Y')

       c = r.conversion_freq_multiplier(r2.freq)

       x = r.equate_freq(r2)

