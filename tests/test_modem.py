import time
import minimodem

alsa_device = minimodem.get_alsa_device('USB PnP')
modem = minimodem.Modem(alsa_device)

modem.send('hello world!')

rx_start = time.time()
timeout = 10

while time.time() < rx_start + timeout:
    time.sleep(1)
    data = modem.receive()
    print(': ' + data)

