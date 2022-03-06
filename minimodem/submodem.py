import os, subprocess, threading, time, signal
from subprocess import PIPE
import pexpect
from pexpect.popen_spawn import PopenSpawn


class MiniModem:
    RX = 'rx'
    TX = 'tx'
    MODES = [RX, TX]

    def __init__(self, mode, alsa_dev, baudrate=300, start=True):

        if mode in MiniModem.MODES:
            self.mode = mode
        else:
            raise Exception('Unknown mode \'' + mode + '\'')

        self.alsa_dev = alsa_dev
        self.baudrate = baudrate
        self.process = None
        self.active = False

        #TODO handle case of minimodem not installed
        execpath = subprocess.check_output(['which', 'minimodem']).decode('utf-8').trim()
        self.shellcmd = '%s --%s --quiet --alsa=%s --print-filter %s' %(execpath, self.mode, self.alsa_dev, self.baudrate)

        if start:
            self.start()

    def start(self):
        if not self.active:
            self.process = subprocess.Popen(self.shellcmd, shell=True, bufsize=-1, stdin=PIPE, stdout=PIPE)
            self.active = True

    def stop(self):
        self.active = False
        self.process.terminate()
        self.process.communicate()
        if self.process.poll() == None:
            self.process.kill()

    def send(self, data):
        if not type(data) == bytes():
            data = data.encode('utf-8')

        self.process.stdin.write(data)
        self.process.stdin.flush()

    def receive(self, size=-1):
        data = self.process.stdout.read(size)
        return data.decode('utf-8')


class Modem:
    RX      = 'rx'
    TX      = 'tx'
    RXTX    = 'rx/tx'
    MODES = [RX, TX, RXTX]

    def __init__(self, alsa_dev_in, alsa_dev_out=None, baudrate=300, mode='rx/tx', start=True):
        self.baudrate = baudrate
        self.alsa_dev_in = alsa_dev_in
        self.alsa_dev_out = alsa_dev_out
        self.rx = None
        self.tx = None
        self.active = False

        if mode in Modem.MODES:
            self.mode = mode
        else:
            raise Exception('Unknown mode \'' + mode + '\'')

        if self.alsa_dev_out == None:
            self.alsa_dev_out = self.alsa_dev_in

        if self.mode in [Modem.RXTX, Modem.RX]:
            self.rx = MiniModem(MiniModem.RX, self.alsa_dev_in, baudrate=self.baudrate, start=False)

        if self.mode in [Modem.RXTX, Modem.TX]:
            self.tx = MiniModem(MiniModem.TX, self.alsa_dev_out, baudrate=self.baudrate, start=False)

        if start:
            self.start()

    def start(self):
        if self.rx:
            self.rx.start()
        if self.tx:
            self.tx.start()

        self.active = True

        self._job_thread = threading.Thread(target=self._job_loop)
        self._job_thread.daemon = True
        self._job_thread.start()

    def stop(self):
        self.active = False

        if self.tx:
            self.tx.stop()
        if self.rx:
            self.rx.stop()

    def send(self, data):
        if self.tx:
            self.tx.send(data)

    def receive(self, timeout=1):
        ifself.rx:
            return self.rx.receive()

    def _job_loop(self):
        while self.active:
            if self.rx:
                data = ''

                try:
                    data = self.receive()
                except UnicodeDecodeError as e:
                    #TODO handle error
                    pass

                if len(data):
                    #TODO append data to buffer?
                    print(': ' + data)

            time.sleep(1)



def get_alsa_device(device_desc, device_mode=Modem.RX):

    if device_mode in [Modem.RXTX, Modem.RX]:
        alsa_cmd = ['arecord', '-l']
    elif device_mode == Modem.TX:
        alsa_cmd = ['aplay', '-l']
    else:
        raise Exception('Unknown mode \'' + device_mode + '\'')
        return None

    alsa_dev = None
    alsa_devs = subprocess.check_output(alsa_cmd).decode('utf-8').split('\r\n')

    for line in alsa_devs:
        if device_desc in line:
            start = 'card'
            end = ':'
            start_index = line.find(start) + len(start)
            end_index = line.find(end, start_index)
            card = line[start_index:end_index].strip()

            start = 'device'
            end = ':'
            start_index = line.find(start) + len(start)
            end_index = line.find(end, start_index)
            device = line[start_index:end_index].strip()

            alsa_dev = card + ',' + device
            break

    return alsa_dev






