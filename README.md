# fskmodem
Python package for creating a full duplex frequency shift keying (FSK) soft modem with carrier sense collision avoidance.

### Example #1
```
import fskmodem

# use system default alsa audio device
# use defaults: 300 baud, sync byte = 0x23 (UTF-8 '#')
modem = fskmodem.Modem()
modem.set_rx_callback(my_rx_func)

modem.send(b'hello world!')
```

### Example #2
```
import fskmodem

def rx_callback(data):
    print(data.decode('utf-8'))

# find alsa audio device by description (see arecord -l)
alsa_device = fskmodem.get_alsa_dev('USB PnP')

# 1200 baud, no sync byte, manual start
modem = fskmodem.Modem(alsa_dev=alsa_device, baudrate=1200, sync_byte=None, start=False)
modem.set_rx_callback(rx_callback)
modem.start()

modem.send(b'hello world!')
```

### Dependencies
The minimodem package is required and can be installed on Debian based systems using the following command:
```
apt install minimodem
```

### Credits

The minimodem Unix application is developed by Kamal Mostafa
[http://www.whence.com/minimodem/](http://www.whence.com/minimodem/)
