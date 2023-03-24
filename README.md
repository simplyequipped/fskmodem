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
alsa_device = fskmodem.get_alsa_device('USB PnP')

# 1200 baud, no sync byte, manual start
modem = fskmodem.Modem(alsa_dev_in=alsa_device, baudrate=1200, sync_byte=None, start=False)
modem.set_rx_callback(rx_callback)
modem.start()

modem.send(b'hello world!')
```

### Reticulum

<!---
Use fskmodem as a software application with [Reticulum](https://github.com/markqvist/Reticulum) via the PipeInterface by setting the appropriate command in the Reticulum config file (see example below). See the Reticulum [manaul](https://markqvist.github.io/Reticulum/manual/interfaces.html#pipe-interface) for more information.

```
[[Pipe Interface]]
  type = PipeInterface
  interface_enabled = True

  # External command to execute
  command = python3 -m fskmodem get_alsa_device='USB PnP' baudrate=1200
```
--->

Use *fskmodem* as a KISS TNC with Reticulum via the TCPClientInterface and the [tcpkissserver](https://github.com/simplyequipped/tcpkissserver) package. See [this gist](https://gist.github.com/simplyequipped/6c982ebb1ede6e5adfc149be15bbde6b) to get started quickly and be sure to update the Reticulum config file accordingly (see tcpkissserver README).

### Install
Install the *fskmodem* package using pip (or pip3 if needed):
```
pip install fskmodem
```

### Dependencies
The *minimodem* package is required and can be installed on Debian systems using apt:
```
sudo apt install minimodem
```

### Credits

The *minimodem* Unix application is developed by Kamal Mostafa
[http://www.whence.com/minimodem/](http://www.whence.com/minimodem/)
