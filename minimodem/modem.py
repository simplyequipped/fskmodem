import os, subprocess, threading, time
from subprocess import PIPE, DEVNULL


RX = 'rx'
TX = 'tx'


class HDLC:
    START = b'|->'
    STOP = b'<-|'


class MiniModem:
    #RX = 'rx'
    #TX = 'tx'
    #MODES = [RX, TX]

    def __init__(self, mode, alsa_dev, baudrate=300, start=True):

        if mode in [RX, TX]:
            self.mode = mode
        else:
            raise Exception('Unknown mode \'' + mode + '\'')

        self.alsa_dev = alsa_dev
        self.baudrate = baudrate
        self.process = None
        self.online = False

        #TODO handle case of minimodem not installed
        execpath = subprocess.check_output(['which', 'minimodem']).decode('utf-8').strip()

        if self.alsa_dev == None:
            # use system default audio device
            self.shellcmd = '%s --%s --quiet --print-filter %s' %(execpath, self.mode, self.baudrate)
        else:
            # use specified alsa audio device
            self.shellcmd = '%s --%s --quiet --alsa=%s --print-filter %s' %(execpath, self.mode, self.alsa_dev, self.baudrate)


        if start:
            self.start()

    def start(self):
        if not self.online:
            self.process = subprocess.Popen(self.shellcmd, shell=True, bufsize=-1, stdin=PIPE, stdout=PIPE, stderr=DEVNULL)
            self.online = True

    def stop(self):
        self.online = False
        self.process.terminate()
        self.process.communicate()
        if self.process.poll() == None:
            self.process.kill()

    def send(self, data):
        self.process.stdin.write(data)
        self.process.stdin.flush()

    def receive(self, size=1):
        return self.process.stdout.read(size)


class Modem:
    def __init__(self, alsa_dev_in=None, alsa_dev_out=None, baudrate=300, start=True):
        self.baudrate = baudrate
        self.alsa_dev_in = alsa_dev_in
        self.alsa_dev_out = alsa_dev_out
        self._rx = None
        self._tx = None
        self.rx_callback = None
        # TODO set equal to Reticulum MTU
        self.MTU = 512
        self.online = False

        if self.alsa_dev_out == None:
            self.alsa_dev_out = self.alsa_dev_in

        self._rx = MiniModem(RX, self.alsa_dev_in, baudrate=self.baudrate, start=False)
        self._tx = MiniModem(TX, self.alsa_dev_out, baudrate=self.baudrate, start=False)

        if start:
            self.start()

    def start(self):
        self._rx.start()
        self._tx.start()
        self._job_thread = threading.Thread(target=self._rx_loop)
        self._job_thread.daemon = True
        self._job_thread.start()
        self.online = True

    def stop(self):
        self.online = False
        self._tx.stop()
        self._rx.stop()

    def send(self, data):
        if type(data) != bytes:
            raise TypeError('Modem data must be type bytes, ' + str(type(data)) + ' given.')
            return None

        data = HDLC.START + data + HDLC.STOP
        self._tx.send(data)

    def set_rx_callback(self, callback):
        self.rx_callback = callback

    def _receive(self):
        data = self._rx.receive()

        # capture bad characters that cannot be decoded
        try:
            data.decode('utf-8')
        except UnicodeDecodeError:
            return b''
        
        return data

    def _rx_loop(self):
        data_buffer = b''
        self.buffer = b''

        while self.online:
            # blocks until next character received
            #data_buffer += self._receive()
            data = self._receive()
            data_buffer += data
            self.buffer += data
            
            if HDLC.START in data_buffer:
                if HDLC.STOP in data_buffer:
                    # delimiters found, capture substring
                    start = data_buffer.find(HDLC.START) + len(HDLC.START)
                    end = data_buffer.end (HDLC.STOP, start)
                    if end > start:
                        data = data_buffer[start:end]
                        # remove received data from buffer
                        data_buffer = data_buffer[end + len(HDLC.STOP):]
                        
                        if len(data) <= self.MTU:
                            # under max packet length, receive data
                            if self.rx_callback != None:
                                self.rx_callback(data)
                        else:
                            # over max packet length, drop data
                            pass
                    else:
                        # partial packets causing mixed up delimiters,
                        # remove bad data from beginning of buffer
                        data_buffer = data_buffer[start + len(HDLC.START):]
                else:
                    if len(data_buffer) > self.MTU:
                        # no end delimiter and buffer length over max packaet size,
                        # remove data up to last start delimiter in buffer
                        data_buffer = data_buffer[data_buffer.rfind(HDLC.START):]
            else:
                # avoid missing start delimiter split over multiple loop iterations
                if len(data_buffer) > 10 * len(HDLC.START):
                    data_buffer = b''

            # simmer down
            time.sleep(0.1)



def get_alsa_device(device_desc, device_mode=RX):
    if device_mode == RX:
        alsa_cmd = ['arecord', '-l']
    elif device_mode == TX:
        alsa_cmd = ['aplay', '-l']
    else:
        raise Exception('Unknown mode \'' + device_mode + '\'')
        return None

    alsa_dev = None
    alsa_devs = subprocess.check_output(alsa_cmd).decode('utf-8').split('\n')

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





