import os, threading, time
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
        execpath = pexpect.which('minimodem')
        self.shellcmd = '%s --%s --quiet --alsa=%s --print-filter %s' %(execpath, self.mode, self.alsa_dev, self.baudrate)

        if start:
            self.start()

    def start(self):
        if not self.active:
            self.process = PopenSpawn(self.shellcmd, timeout=None, encoding='utf-8')
            self.active = True

    def stop(self):
        self.active = False
        # send ctrl-c to child process
        self.process.send(chr(3))
        #TODO how to kill the process?
        #self.process.proc.terminate()
        #self.process.proc.communicate()
        #if self.process.proc.poll() == None:
        #    self.process.proc.kill()


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
        if not self.tx:
            return None

        self.tx.process.sendline(data)

    def receive(self, timeout=1):
        if not self.rx:
            return None

        self.rx.process.expect_exact(pexpect.TIMEOUT, timeout=timeout)
        return self.rx.process.before

    def register_rx_callback(self, func):
        pass

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
                    print(':' + data)

            time.sleep(1)



def get_alsa_device(device_desc, device_mode=Modem.RX):

    if device_mode in [Modem.RXTX, Modem.RX]:
        alsa_cmd = 'arecord -l'
    elif device_mode == Modem.TX:
        alsa_cmd = 'aplay -l'
    else:
        raise Exception('Unknown mode \'' + device_mode + '\'')
        return None

    alsa_dev = None
    cmd = pexpect.spawn(alsa_cmd)
    cmd.expect(pexpect.EOF)
    alsa_devs = cmd.before.decode('utf-8').split('\r\n')
    cmd.close()

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






