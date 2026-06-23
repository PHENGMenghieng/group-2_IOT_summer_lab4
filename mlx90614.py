import ustruct

MLX90614_ADDR = 0x5A
RAM_TOBJ1 = 0x07
RAM_TA    = 0x06

class MLX90614:
    def __init__(self, i2c, address=MLX90614_ADDR):
        self.i2c = i2c
        self.addr = address

    def _read_word(self, reg):
        data = self.i2c.readfrom_mem(self.addr, reg, 3)
        return ustruct.unpack('<H', data[:2])[0]

    def _to_celsius(self, raw):
        return (raw * 0.02) - 273.15

    @property
    def ambient_temperature(self):
        return self._to_celsius(self._read_word(RAM_TA))

    @property
    def object_temperature(self):
        return self._to_celsius(self._read_word(RAM_TOBJ1))
