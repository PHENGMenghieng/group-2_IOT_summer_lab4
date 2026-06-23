import utime
from machine import I2C

DS3231_ADDR = 0x68

def bcd2dec(bcd):
    return (bcd >> 4) * 10 + (bcd & 0x0F)

class DS3231:
    def __init__(self, i2c):
        self.i2c = i2c

    def get_time(self):
        data = self.i2c.readfrom_mem(DS3231_ADDR, 0x00, 7)
        ss = bcd2dec(data[0])
        mm = bcd2dec(data[1])
        hh = bcd2dec(data[2] & 0x3F)
        dd = bcd2dec(data[4])
        mo = bcd2dec(data[5] & 0x1F)
        yy = bcd2dec(data[6]) + 2000
        return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(yy, mo, dd, hh, mm, ss)
