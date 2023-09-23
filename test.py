import fskmodem

def ptt():
    pass

modem = fskmodem.Modem(baudmode=100)
modem._debug = True
modem.set_ptt_callback(ptt)

