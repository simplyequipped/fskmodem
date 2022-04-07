# minimodem
Python package for using the Unix minimodem application to create a full duplex modem with carrier sense collision avoidance and transmit buffering.

### Example #1
```
import minimodem

# use system default alsa audio device
# use defaults: 300 baud, sync byte = 0x23 (UTF-8 '#')
modem = minimodem.Modem()
modem.set_rx_callback(my_rx_func)

modem.send(b'hello world!')
```

### Example #2
```
import minimodem

def rx_callback(data):
    print(data.decode('utf-8'))

# find alsa audio device by description (see arecord -l)
alsa_device = minimodem.get_alsa_dev('USB PnP')

# 1200 baud, no sync byte, manual start
modem = minimodem.Modem(alsa_dev=alsa_device, baudrate=1200, sync_byte=None, start=False)
modem.set_rx_callback(rx_callback)
modem.start()

modem.send(b'hello world!')
```

### Credits

The minimodem Unix application is developed by Kamal Mostafa
[http://www.whence.com/minimodem/](http://www.whence.com/minimodem/)
