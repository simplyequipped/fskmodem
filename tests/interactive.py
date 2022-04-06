import minimodem

modem = minimodem.Modem()

def rx_callback(data):
    print(data)

modem.set_rx_callback(rx_callback)
