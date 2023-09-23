import fskmodem

def ptt():
    pass

modem = fskmodem.Modem(baudmode=100, sync_byte=None)
#modem = fskmodem.Modem(baudmode=100, sync_byte=None)
modem._debug = True
modem.set_ptt_callback(ptt)

