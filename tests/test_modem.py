import minimodem

alsa_device = minimodem.get_alsa_device('USB PnP')
if alsa_device is None:
    print('No alsa device found')
    exit()

modem = minimodem.Modem(alsa_device)
#modem.send('hello world!')

#input('Press enter to stop modems\n')
#modem.stop()

#input('Press enter to quit test\n')


