import minimodem

def rx_callback(data):
    print('\nPacket received: ' + data.decode('utf-8'))

# use system default audio device
modem = minimodem.Modem()
modem.set_rx_callback(rx_callback)
