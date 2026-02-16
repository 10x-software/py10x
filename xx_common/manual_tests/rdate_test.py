if __name__ == '__main__':

       from xx_common.rdate import RDate


       r = RDate('3M')
       r2 = RDate('10Y')

       c = r.conversion_freq_multiplier(r2.freq)

       x = r.equate_freq(r2)

