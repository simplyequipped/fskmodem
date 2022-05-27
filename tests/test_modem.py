import fskmodem

def rx_callback(data):
    print('\nPacket received: ' + data.decode('utf-8'))

# use system default audio device
modem = fskmodem.Modem()
modem.set_rx_callback(rx_callback)
