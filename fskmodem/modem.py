'''A full duplex FSK soft modem utilizing the Unix application minimodem

The minimodem application can be installed on Debian systems with the command:
    sudo apt install minimodem

Classes:

    HDLC
    MiniModem
    Modem

Functions:

    get_alsa_device(device_desc[, device_mode=RX]) -> str

Constants:

    RX
    TX
'''


import os, subprocess, threading, time, random
from subprocess import PIPE, CalledProcessError



# Package constants
RX = 'rx'
TX = 'tx'

class HDLC:
    '''Defines packet framing flags similar to HDLC or PPP.
    
    Multiple characters per flag makes it less likely that receiver noise will emulate a flag.
    
    Constants:

        START
        STOP
    '''

    START = b'|->'
    STOP = b'<-|'

class FSKModem:
    '''Create and interact with a minimodem subprocess

    See the minimodem manpage for more information about the application.

    Attributes:
    
        mode : str, operating mode of the minimodem application (see module constants)
        alsa_dev : str | None, ALSA device formated as 'card,device' (ex. '2,0'), or None to use system default
        baudrate : int, baud rate of the modem
        sync_byte : str, suppress rx carrier detection until byte is received
        confidence : float, minimum confidence threshold based on SNR (i.e. squelch)
        process : object, subprocess.Popen instance of the minimodem application
        online: bool, status of the modem
        shell_cmd: str, command string passed to subprocess.Popen

    Methods:

        __init__(self, mode, alsa_dev[, baudrate=300, start=True])
        start(self)
        stop(self)
        send(self, data)
        receive(self[, size=1])
        _get_stderr(self[, size=1])
    '''

    def __init__(self, mode, alsa_dev=None, baudrate=300, sync_byte=None, confidence=None, start=True):
        '''Initialize FSKModem class instance

        :param mode: str, operating mode of the minimodem application (see module constants)
        :param alsa_dev: str, ALSA device formated as 'card,device' (ex. '2,0'), or None to use system default
        :param baudrate: int, baud rate of the modem (optional, default: 300)
        :param sync_byte: str, suppress rx carrier detection until byte is received (optional, default: None, ex. '0x23' = UTF-8 '#')
        :param confidence: float, minimum confidence threshold based on SNR (i.e. squelch, optional, default: None, ex. 2.0)
        :param start: bool, start the modem subprocess on object instantiation (optional, default: True)

        :return: object, class instance

        :raises: ValueError, if mode is not one of the module constants (RX, TX)
        :raises: ProcessLookupError, if the minimodem application is not installed
        '''

        if mode in [RX, TX]:
            self.mode = mode
        else:
            raise ValueError('Unknown mode \'' + mode + '\', must be minimodem.RX or minimodem.TX')

        self.alsa_dev = alsa_dev
        self.baudrate = baudrate
        self.sync_byte = sync_byte
        self.confidence = confidence
        self.process = None
        self.shell_cmd = None
        self.online = False

        try:
            # get full path of minimodem binary
            exec_path = subprocess.check_output(['which', 'minimodem']).decode('utf-8').strip()
        except CalledProcessError:
            raise ProcessLookupError('minimodem application not installed, try: sudo apt install minimodem')

        # configure comandline switches
        # note spaces before switch strings
        switch_mode = ' --' + str(self.mode)
        switch_alsa_dev = ''
        switch_confidence = ''
        switch_sync_byte = ''
        switch_filter = ' --print-filter'

        if self.alsa_dev != None:
            switch_alsa_dev = ' --alsa=' + str(self.alsa_dev)
        if self.confidence != None:
            switch_confidence = ' --confidence ' + str(self.confidence)
        if self.sync_byte != None:
            switch_sync_byte = ' --sync-byte ' + str(self.sync_byte)

        switches = [switch_mode, switch_alsa_dev, switch_confidence, switch_sync_byte, switch_filter]
        # confidence, sync byte, quiet, and print filter are not used in tx mode
        self.shell_cmd = exec_path + ''.join(switches) + ' ' + str(self.baudrate)

        if start:
            self.start()

    def start(self):
        '''Start the modem by creating the appropriate subprocess with the given parameters'''
        if not self.online:
            # create subprocess with pipes for interaction with child process
            self.process = subprocess.Popen(self.shell_cmd, shell=True, bufsize=-1, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            self.online = True

    def stop(self):
        '''Stop the modem by terminating or killing the subprocess'''
        self.online = False
        # try to terminate normally
        self.process.terminate()
        # use a thread to communicate non-blocking-ly
        comm_thread = threading.Thread(target=self.process.communicate)
        comm_thread.daemon = True
        comm_thread.start()
        
        comm_start = time.time()
        comm_timeout = 5
        # manual timeout
        while time.time() < comm_start + comm_timeout:
            time.sleep(1)

        if self.process.poll() == None:
            # if the process still hasn't stopped, try to kill it
            self.process.kill()
            # use a thread to communicate non-blocking-ly
            comm_thread = threading.Thread(target=self.process.communicate)
            comm_thread.daemon = True
            comm_thread.start()

    def send(self, data):
        '''Send data to the underlying minimodem subprocess

        This method is only used with transmit mode (mode = minimodem.TX)

        :param data: bytes, byte string of data to send to the subprocess pipe
        '''
        if self.sync_byte != None:
            data = self.sync_byte.encode('utf-8') + data

        self.process.stdin.write(data)
        self.process.stdin.flush()

    def receive(self, size=1):
        '''Receive data from the underlying minimodem subprocess

        Reading from the subprocess.Popen.stdout pipe is blocking until the specified number of bytes is available.

        This method is only used with receive mode (mode = minimodem.RX)

        :param size: int, number of bytes to read from the subprocess pipe

        :return: bytes, received byte string of specified length
        '''
        return self.process.stdout.read(size)

    def _get_stderr(self, size=1):
        '''Get stderr data from the underlying minimodem subprocess

        Reading from the subprocess.Popen.stderr pipe is blocking until the specified number of bytes is available.

        This method is only used with receive mode (mode = minimodem.RX)

        :param size: int, number of bytes to read from the subprocess pipe

        :return: bytes, received byte string of specified length
        '''
        return self.process.stderr.read(size)


class Modem:
    '''Create and manage FSKModem RX and TX instances to create a duplex soft modem

    Attributes:
    
        alsa_dev_in : str, input ALSA device formated as 'card,device' (ex. '2,0')
        alsa_dev_out : str, output ALSA device formated as 'card,device' (ex. '2,0')
        baudrate : int, baud rate of the modem
        sync_byte : str, suppress rx carrier detection until byte is received
        confidence : float, minimum confidence threshold based on SNR (i.e. squelch)
        _rx : object, instance of the FSKModem class
        _tx : object, instance of the FSKModem class
        rx_callback: func, received packet callback function with signature func(data) where data is type bytes
        MTU: int, maximum size of packet to be transmitted or received (default: 500, see Reticulum Network Stack)
        carrier_sense : bool, if a carrier signal is being received
        _tx_buffer : list, data to be transmitted (buffered when receiving based on carrier detect)
        online: bool, status of the modem

    Methods:

        __init__(self[, alsa_dev_in=None, alsa_dev_out=None, baudrate=300, start=True])
        start(self)
        stop(self)
        send(self, data)
        set_rx_callback(callback)
        _receive(self[, size=1])
        _job_loop(self)
        _rx_loop(self)
        _stderr_loop(self)
    '''

    def __init__(self, alsa_dev_in=None, alsa_dev_out=None, baudrate=300, sync_byte='0x23', confidence=1.5, start=True):
        '''Initialize a Modem class instance

        :param alsa_dev_in: str, input ALSA device formated as 'card,device' (ex. '2,0') (optional, default: None)
        :param alsa_dev_out: str, output ALSA device formated as 'card,device' (ex. '2,0') (optional, default: None, if None alsa_dev_out is set to alsa_dev_in)
        :param baudrate: int, baud rate of the modem (optional, default: 300)
        :param sync_byte: str, suppress rx carrier detection until byte is received (optional, default: '0x23' = UTF-8 '#')
        :param confidence: float, minimum confidence threshold based on SNR (i.e. squelch, optional, default: 1.5)
        :param start: bool, start the modem subprocess on object instantiation (optional, default: True)
        :return: object, class instance
        '''

        self.alsa_dev_in = alsa_dev_in
        self.alsa_dev_out = alsa_dev_out
        self.baudrate = baudrate
        self.sync_byte = sync_byte
        self.confidence = confidence
        self._rx = None
        self._tx = None
        self.rx_callback = None
        self.MTU = 500
        self.carrier_sense = False
        self._tx_buffer = []
        self.online = False

        # if a separate output device is not specified, assume it is the same as the input device
        if self.alsa_dev_out == None:
            self.alsa_dev_out = self.alsa_dev_in

        # create receive minimodem instance
        self._rx = FSKModem(RX, self.alsa_dev_in, baudrate=self.baudrate, sync_byte=self.sync_byte, confidence=self.confidence, start=False)
        # create transmit minimodem instance
        self._tx = FSKModem(TX, self.alsa_dev_out, baudrate=self.baudrate, sync_byte=self.sync_byte, confidence=self.confidence, start=False)

        # start the modem now if specified
        if start:
            self.start()

    def start(self):
        '''Start the modem by starting the underlying MiniModem instances and loop threads'''
        self._rx.start()
        self._tx.start()
        self.online = True

        # start the receive loop as a thread since reads from the child process are blocking
        rx_thread = threading.Thread(target=self._rx_loop)
        rx_thread.daemon = True
        rx_thread.start()

        # start the stderr loop as a thread since reads from the child process are blocking
        stderr_thread = threading.Thread(target=self._stderr_loop)
        stderr_thread.daemon = True
        stderr_thread.start()

        # start the job loop to process data in the tx buffer
        job_thread = threading.Thread(target=self._job_loop)
        job_thread.daemon = True
        job_thread.start()

    def stop(self):
        '''Stop the modem by stopping the underlying MiniModem instances'''
        self.online = False

        # use a thread to stop the child process non-blocking-ly
        stop_tx_thread = threading.Thread(target=self._tx.stop)
        stop_tx_thread.daemon = True
        stop_tx_thread.start()
        # use a thread to stop the child process non-blocking-ly
        stop_rx_thread = threading.Thread(target=self._rx.stop)
        stop_rx_thread.daemon = True
        stop_rx_thread.start()

    def send(self, data):
        '''Send data to the underlying transmit MiniModem instance after wrapping data with HDLC flags

        If receiving (a carrier event occured), buffer the data to transmit later

        :param data: bytes, byte string of data to send

        :raises: TypeError, if data is not type bytes
        '''
        if type(data) != bytes:
            raise TypeError('Modem data must be type bytes, ' + str(type(data)) + ' given.')
            return None

        if self.carrier_sense:
            self._tx_buffer.append(data)
            return None

        # wrap data in start and stop flags
        data = HDLC.START + data + HDLC.STOP
        self._tx.send(data)

    def set_rx_callback(self, callback):
        '''Set receive callback function

        :param callback: func, function to call when packet is received (signature: func(data) where data is type bytes)
        '''
        self.rx_callback = callback

    def _receive(self):
        '''Get next byte from receive MiniModem instance

        Always call this function from a thread since the underlying subprocess pipe read will not return until data is available.
        Validation of the received byte is performed by attempting to decode the byte and catching any UnicodeDecodeError exceptions.

        :return: bytes, received byte string (could be  b'' if a decode error occured)
        '''
        data = self._rx.receive()

        # capture characters that cannot be decoded (receiver noise)
        try:
            data.decode('utf-8')
        except UnicodeDecodeError:
            return b''
        
        return data

    def _job_loop(self):
        '''Process data in the transmit buffer when not receiving'''

        while self.online:
            while self.carrier_sense:
                time.sleep(random.uniform(0.5, 3.0))

            # process next item in transmit buffer
            if len(self._tx_buffer) > 0:
                data = self._tx_buffer.pop(0)
                self.send(data)
    
            time.sleep(0.1)

    def _rx_loop(self):
        '''Receive data into a buffer and find data packets

        The specified callback function is called once a complete packet is received.
        '''
        data_buffer = b''
        max_data_buffer_len = 1024

        while self.online:
            # blocks until next character received
            data_buffer += self._receive()
            
            if HDLC.START in data_buffer:
                if HDLC.STOP in data_buffer:
                    # delimiters found, capture substring
                    start = data_buffer.find(HDLC.START) + len(HDLC.START)
                    end = data_buffer.find(HDLC.STOP, start)
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
                    if len(data_buffer) > max_data_buffer_len:
                        # no end delimiter and buffer length over max packaet size,
                        # remove data up to last start delimiter in buffer
                        data_buffer = data_buffer[data_buffer.rfind(HDLC.START):]
            else:
                # avoid missing start delimiter split over multiple loop iterations
                if len(data_buffer) > 10 * len(HDLC.START):
                    data_buffer = b''

            # simmer down
            time.sleep(0.001)

    def _stderr_loop(self):
        '''Receive stderr data into a buffer and find carrier events

        The carrier sense property is set (True/False) depending on the type of event received (CARRIER or NOCARRIER).
        '''
        stderr_buffer = b''
        carrier_event_symbol = b'###'

        while self.online:
            # blocks until next character received
            stderr_buffer += self._rx._get_stderr()
            
            # detect carrier event
            if carrier_event_symbol in stderr_buffer:
                carrier_event_start = stderr_buffer.find(carrier_event_symbol) + len(carrier_event_symbol)
                carrier_event_end = stderr_buffer.find(carrier_event_symbol, carrier_event_start)
                if carrier_event_end > 0:
                    # capture carrier event text
                    carrier_event = stderr_buffer[carrier_event_start:carrier_event_end].strip()
                    # remove carrier event text from buffer
                    stderr_buffer = stderr_buffer[carrier_event_end + len(carrier_event_symbol):]

                    carrier_event_data  = carrier_event.split(b' ')
                    carrier_event_type = carrier_event_data[0]

                    # set carrier sense state
                    if carrier_event_type == b'CARRIER':
                        self.carrier_sense = True
                    elif carrier_event_type == b'NOCARRIER':
                        self.carrier_sense = False

            else:
                # avoid missing symbol split over multiple loop iterations
                if len(stderr_buffer) > 2 * len(carrier_event_symbol):
                    stderr_buffer = b''

            # simmer down
            time.sleep(0.001)



def get_alsa_device(device_desc, device_mode=RX):
    '''Get ALSA 'card,device' string based on device description

    The purpose of this function is to ensure the correct card and device are identified in case the connected audo devices change. The output of 'arecord -l' or 'aplay -l' (depending on specified device mode) is used to get device descriptions. Try running the applicable command (arecord or aplay) to find the device description.

    :param device_desc: str, unique string to search for in device descriptions (ex. 'USB PnP')
    :param device_mode: str, search for input or output audio devices (optional, default: minimodem.RX, see module constants)

    :return: str | None, card and device (ex. '2,0') or None if no matching device was found
    '''
    if device_mode == RX:
        alsa_cmd = ['arecord', '-l']
    elif device_mode == TX:
        alsa_cmd = ['aplay', '-l']
    else:
        raise Exception('Unknown mode \'' + device_mode + '\'')
        return None

    alsa_dev = None
    # get audio device descriptions
    alsa_devs = subprocess.check_output(alsa_cmd).decode('utf-8').split('\n')

    for line in alsa_devs:
        if device_desc in line:
            # if the specified description is found
            # capture the card number
            start = 'card'
            end = ':'
            start_index = line.find(start) + len(start)
            end_index = line.find(end, start_index)
            card = line[start_index:end_index].strip()
            # capture the device number
            start = 'device'
            end = ':'
            start_index = line.find(start) + len(start)
            end_index = line.find(end, start_index)
            device = line[start_index:end_index].strip()
            # build the device string
            alsa_dev = card + ',' + device
            break

    return alsa_dev





