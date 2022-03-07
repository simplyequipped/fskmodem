import minimodem

def rx_callback(data):
    print(data.decode('utf-8'))

alsa_device = minimodem.get_alsa_device('USB PnP')
if alsa_device is None:
    print('No alsa device found')
    exit()

modem = minimodem.Modem(alsa_device)
modem.set_rx_callback(rx_callback)

