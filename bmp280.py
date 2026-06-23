from machine import I2C
import time

class BMP280:
    def __init__(self, i2c, addr=0x76):
        self.i2c = i2c
        self.addr = addr
        self.sea_level_pressure = 1011.7

        chip_id = self.i2c.readfrom_mem(self.addr, 0xD0, 1)
        if chip_id[0] != 0x58:
            raise Exception("BMP280 not found")

        self.i2c.writeto_mem(self.addr, 0xE0, b'\xB6')
        time.sleep(0.2)

        calib = self.i2c.readfrom_mem(self.addr, 0x88, 24)

        def to_signed(val):
            if val > 32767:
                val -= 65536
            return val

        self.dig_T1 = calib[1] << 8 | calib[0]
        self.dig_T2 = to_signed(calib[3] << 8 | calib[2])
        self.dig_T3 = to_signed(calib[5] << 8 | calib[4])

        self.dig_P1 = calib[7] << 8 | calib[6]
        self.dig_P2 = to_signed(calib[9] << 8 | calib[8])
        self.dig_P3 = to_signed(calib[11] << 8 | calib[10])
        self.dig_P4 = to_signed(calib[13] << 8 | calib[12])
        self.dig_P5 = to_signed(calib[15] << 8 | calib[14])
        self.dig_P6 = to_signed(calib[17] << 8 | calib[16])
        self.dig_P7 = to_signed(calib[19] << 8 | calib[18])
        self.dig_P8 = to_signed(calib[21] << 8 | calib[20])
        self.dig_P9 = to_signed(calib[23] << 8 | calib[22])

        self.i2c.writeto_mem(self.addr, 0xF4, b'\x27')
        self.i2c.writeto_mem(self.addr, 0xF5, b'\xA0')

        self.t_fine = 0

    def _read_raw(self):
        data = self.i2c.readfrom_mem(self.addr, 0xF7, 6)
        adc_p = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        adc_t = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        return adc_t, adc_p

    def _compensate_temperature(self, adc_t):
        var1 = (((adc_t >> 3) - (self.dig_T1 << 1)) * self.dig_T2) >> 11
        var2 = (((((adc_t >> 4) - self.dig_T1) *
                  ((adc_t >> 4) - self.dig_T1)) >> 12) *
                self.dig_T3) >> 14
        self.t_fine = var1 + var2
        T = (self.t_fine * 5 + 128) >> 8
        return T / 100

    def _compensate_pressure(self, adc_p):
        var1 = self.t_fine - 128000
        var2 = var1 * var1 * self.dig_P6
        var2 = var2 + ((var1 * self.dig_P5) << 17)
        var2 = var2 + (self.dig_P4 << 35)
        var1 = ((var1 * var1 * self.dig_P3) >> 8) + ((var1 * self.dig_P2) << 12)
        var1 = (((1 << 47) + var1) * self.dig_P1) >> 33
        if var1 == 0:
            return 0
        p = 1048576 - adc_p
        p = (((p << 31) - var2) * 3125) // var1
        var1 = (self.dig_P9 * (p >> 13) * (p >> 13)) >> 25
        var2 = (self.dig_P8 * p) >> 19
        p = ((p + var1 + var2) >> 8) + (self.dig_P7 << 4)
        return p / 256

    def _read_all(self):
        adc_t, adc_p = self._read_raw()
        temp = self._compensate_temperature(adc_t)
        pressure = self._compensate_pressure(adc_p)
        return temp, pressure

    @property
    def temperature(self):
        temp, _ = self._read_all()
        return temp

    @property
    def pressure(self):
        _, pressure = self._read_all()
        return pressure

    @property
    def altitude(self):
        pressure_hpa = self.pressure / 100
        return 44330 * (1 - (pressure_hpa / self.sea_level_pressure) ** 0.1903)

