import time
import json
import network
from machine import I2C, Pin, ADC
from umqtt.simple import MQTTClient
from bmp280 import BMP280
from mlx90614 import MLX90614
from ds3231 import DS3231

# ─── Config ────────────────────────────────────────────────
WIFI_SSID   = "Robotic WIFI"
WIFI_PASS   = "rbtWIFI@2025"
MQTT_BROKER = "test.mosquitto.org"
MQTT_CLIENT = "esp32_lab4"
MQTT_TOPIC  = "/aupp/esp32/sensors"

# ─── WiFi ──────────────────────────────────────────────────
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)
    while not wlan.isconnected():
        time.sleep(0.5)
    print("WiFi connected:", wlan.ifconfig())

# ─── Sensors ───────────────────────────────────────────────
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100000)  # lowered to 100kHz for MLX stability
bmp = BMP280(i2c)
mlx = MLX90614(i2c)
rtc = DS3231(i2c)

mq5 = ADC(Pin(33))
mq5.atten(ADC.ATTN_11DB)
mq5.width(ADC.WIDTH_12BIT)

# ─── Moving Average ────────────────────────────────────────
gas_buffer = []

def moving_average(val):
    gas_buffer.append(val)
    if len(gas_buffer) > 5:
        gas_buffer.pop(0)
    return sum(gas_buffer) // len(gas_buffer)

def classify_gas(avg):
    if avg < 2100:
        return "SAFE"
    elif avg < 2600:
        return "WARNING"
    else:
        return "DANGER"

def fever_check(temp):
    return 1 if temp >= 32.5 else 0

# ─── Read MLX with retry ───────────────────────────────────
def read_mlx():
    for _ in range(3):  # try up to 3 times
        try:
            time.sleep_ms(150)
            temp = round(mlx.object_temperature, 2)
            if 20.0 <= temp <= 45.0:  # valid human body temp range
                return temp
        except:
            time.sleep_ms(300)
    return None  # failed all attempts

# ─── MQTT reconnect ────────────────────────────────────────
def connect_mqtt():
    c = MQTTClient(MQTT_CLIENT, MQTT_BROKER)
    c.connect()
    print("MQTT connected")
    return c

# ─── Main ──────────────────────────────────────────────────
connect_wifi()
client = connect_mqtt()

while True:
    try:
        # BMP280
        room_temp = round(bmp.temperature, 2)
        pressure  = round(bmp.pressure, 2)
        altitude  = round(44330 * (1 - (pressure / 101325) ** (1 / 5.255)), 2)
        print("BMP280 OK | Temp:", room_temp, "Pressure:", pressure, "Altitude:", altitude)

        # MQ5
        raw_gas = mq5.read()
        avg_gas = moving_average(raw_gas)
        risk    = classify_gas(avg_gas)
        print("MQ5 OK | Raw:", raw_gas, "Avg:", avg_gas, "Risk:", risk)

        # MLX90614 with retry — no longer skips publishing if it fails
        body_temp = read_mlx()
        if body_temp is None:
            print("MLX FAIL - publishing with null body_temp")
            fever = 0
        else:
            fever = fever_check(body_temp)
            print("MLX OK | Body Temp:", body_temp, "Fever:", fever)

        # DS3231
        try:
            timestamp = rtc.get_time()
            print("RTC OK |", timestamp)
        except:
            timestamp = "no-rtc"
            print("RTC FAIL - using fallback timestamp")

        # One single JSON packet
        payload = json.dumps({
            "timestamp":  timestamp,
            "room_temp":  room_temp,
            "pressure":   pressure,
            "altitude":   altitude,
            "gas_raw":    raw_gas,
            "gas_avg":    avg_gas,
            "risk_level": risk,
            "body_temp":  body_temp,  # will be null if MLX failed
            "fever_flag": fever
        })

        client.publish(MQTT_TOPIC, payload)
        print("Sent OK\n")

    except Exception as e:
        print("Error:", e)
        try:
            client = connect_mqtt()  # reconnect MQTT on error
        except Exception as e2:
            print("MQTT reconnect failed:", e2)

    time.sleep(5)
