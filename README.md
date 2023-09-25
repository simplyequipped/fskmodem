# fskmodem
Python package for creating a full duplex audio frequency shift keying (AFSK) soft modem.


### Example #1
```
import fskmodem

# use system default alsa audio device and modem defaults (300 baud)
modem = fskmodem.Modem()
modem.set_rx_callback(rx_func)

modem.send('hello world!')
```

### Example #2
```
import fskmodem

def rx_callback(data):
    print(data)

# 1200 baud, start subprocesses later
modem = fskmodem.Modem(search_alsa_dev_in='USB PnP', baudrate=1200, start=False)
modem.set_rx_callback(rx_callback)
modem.start()

modem.send('hello world!')
```

### Reticulum

Use *fskmodem* as a KISS TNC with [Reticulum](https://github.com/markqvist/Reticulum) via the TCPClientInterface and the [tcpkissserver](https://github.com/simplyequipped/tcpkissserver) package. See [this gist](https://gist.github.com/simplyequipped/6c982ebb1ede6e5adfc149be15bbde6b) to get started quickly, and be sure to update the Reticulum config file accordingly.

### Install
Install the *fskmodem* package using pip:
```
pip3 install fskmodem
```

### Dependencies
The *minimodem* package is required and can be installed on Debian systems using apt:
```
sudo apt install minimodem
```

### Acknowledgements

The *minimodem* Unix application is developed by Kamal Mostafa
[http://www.whence.com/minimodem/](http://www.whence.com/minimodem/)
