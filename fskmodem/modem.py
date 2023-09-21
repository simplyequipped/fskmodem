#TODO
# - add license
# - separate outgoing buffering and buffer processing jobs (see send_raw function)
# - separate rx and tx fskmodem classes


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

import os
import sys
import subprocess
import threading
import time
import random
import atexit
import shutil
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
        '''Initialize FSKModem class instance.

        Args:
            mode (str): Operating mode of the minimodem application (see module constants)
            alsa_dev (str): Input/output ALSA device formated as 'card,device' (ex. '2,0'), defaults to None
            baudrate (int): Baudrate of the modem, defaults to 300 baud
            sync_byte (str): Suppress rx carrier detection until the specified byte is received, defaults to None
            confidence (float): Minimum confidence threshold based on SNR (i.e. squelch), defaults to None
            start (bool): Start minimodem subprocess on object instantiation, defaults to True

        Returns:
            fskmodem.FSKModem: FSKModem instance object
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
            exec_path = shutil.which('minimodem')
        except CalledProcessError:
            raise ProcessLookupError('minimodem application not installed, try: sudo apt install minimodem')

        # configure comandline switches
        # note spaces before switch strings
        switch_mode = ' --' + str(self.mode)
        switch_alsa_dev = ''
        switch_confidence = ''
        switch_sync_byte = ''
        switch_filter = ' --print-filter'

        if self.alsa_dev is not None:
            switch_alsa_dev = ' --alsa=' + str(self.alsa_dev)
        if self.confidence is not None:
            switch_confidence = ' --confidence ' + str(self.confidence)
        if self.sync_byte is not None:
            switch_sync_byte = ' --sync-byte ' + str(self.sync_byte)

        switches = [switch_mode, switch_alsa_dev, switch_confidence, switch_sync_byte, switch_filter]
        # confidence, sync byte, quiet, and print filter are not used in tx mode
        self.shell_cmd = exec_path + ''.join(switches) + ' ' + str(self.baudrate)

        if start:
            self.start()
        
    def start(self):
        '''Start minimodem subprocess.'''
        if not self.online:
            # create subprocess with pipes for interaction with child process
            self.process = subprocess.Popen(self.shell_cmd, shell=True, bufsize=-1, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            self.online = True

    def stop(self):
        '''Stop minimodem subprocess.'''
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
        '''Send data to the minimodem subprocess.

        This method is only used with transmit mode (mode = minimodem.TX).

        Args:
            data (int): byte string to send to the subprocess pipe
        '''
        if self.sync_byte is not None:
            data = self.sync_byte.encode('utf-8') + data

        self.process.stdin.write(data)
        self.process.stdin.flush()

    def receive(self, size=1):
        '''Receive data from minimodem subprocess.

        Reading from the subprocess.Popen.stdout pipe is blocking until the specified number of bytes is available.

        This method is only used with receive mode (mode = minimodem.RX).

        Args:
            size (int): Number of bytes to read from the subprocess pipe

        Returns:
            bytes: Received byte string of specified length
        '''
        return self.process.stdout.read(size)

    def _get_stderr(self, size=1):
        '''Get stderr data from minimodem subprocess.

        Reading from the subprocess.Popen.stderr pipe is blocking until the specified number of bytes is available.

        This method is only used with receive mode (mode = minimodem.RX).

        Args:
            size (int): Number of bytes to read from the subprocess pipe

        Returns:
            bytes: Received byte string of specified length
        '''
        return self.process.stderr.read(size)


class Modem:
    '''Create and manage a soft FSK modem.

    Attributes:
        alsa_dev_in (str): Input ALSA device formated as 'card,device' (ex. '2,0')
        alsa_dev_out (str): Output ALSA device formated as 'card,device' (ex. '2,0')
        baudrate (int): Baudrate of the modem, defaults to 300 baud
        sync_byte (str): Suppress rx carrier detection until the specified byte is received, defaults to '0x23' (UTF-8 '#')
        confidence (float): Minimum confidence threshold based on SNR (i.e. squelch), defaults to 1.5
        MTU (int): Maximum size of packet to be transmitted or received (default: 500, see Reticulum Network Stack)
        online (bool): True if modem subprocesses are running, False otherwise
        carrier_sense (bool): True if incoming carrier detected, False otherwise
    '''

    def __init__(self, alsa_dev=None, alsa_dev_in=None, alsa_dev_out=None, baudrate=300, sync_byte='0x23', confidence=1.5, start=True):
        '''Initialize Modem class instance.

        If the input and output ALSA devices are the same device, use *alsa_dev*. Otherwise, use *alsa_dev_in* and *alsa_dev_out* to specifiy different devices for input and output.

        Args:
            alsa_dev (str): Input/output ALSA device formated as 'card,device' (ex. '2,0'), defaults to None
            alsa_dev_in (str): Input ALSA device formated as 'card,device' (ex. '2,0'), defaults to None
            alsa_dev_out (str): Output ALSA device formated as 'card,device' (ex. '2,0'), defaults to None
            baudrate (int): Baudrate of the modem, defaults to 300 baud
            sync_byte (str): Suppress rx carrier detection until the specified byte is received, defaults to '0x23' (UTF-8 '#')
            confidence (float): Minimum confidence threshold based on SNR (i.e. squelch), defaults to 1.5
            start (bool): Start modem subprocesses on object instantiation, defaults to True

        Returns:
            fskmodem.Modem: Modem instance object
        '''
        if alsa_dev is None:
            self.alsa_dev_in = alsa_dev_in
            self.alsa_dev_out = alsa_dev_out
        else:
            self.alsa_dev_in = alsa_dev
            self.alsa_dev_out = alsa_dev
        
        self.baudrate = baudrate
        self.sync_byte = sync_byte
        self.confidence = confidence
        self.MTU = 500
        self.online = False
        self.carrier_sense = False
        self._rx_callback = None
        self._toggle_ptt_callback = None
        self._rx_confidence = {'confidence': 0.0, 'timestamp': 0}
        self._tx_buffer = []
        self._rx = None
        self._tx = None

        # configure exit handler
        atexit.register(self.stop)

        # start the modem if specified
        if start:
            self.start()

    def start(self):
        '''Start modem monitoring loops and underlying FSKModem instances.'''
        # create receive minimodem instance
        self._rx = FSKModem(RX, self.alsa_dev_in, baudrate=self.baudrate, sync_byte=self.sync_byte, confidence=self.confidence)
        # create transmit minimodem instance
        self._tx = FSKModem(TX, self.alsa_dev_out, baudrate=self.baudrate, sync_byte=self.sync_byte, confidence=self.confidence)
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
        '''Stop modem and underlying processes.'''
        self.online = False

        # use a thread to stop the child process non-blocking-ly
        if self._tx is not None:
            stop_tx_thread = threading.Thread(target=self._tx.stop)
            stop_tx_thread.daemon = True
            stop_tx_thread.start()
        # use a thread to stop the child process non-blocking-ly
        if self._rx is not None:
            stop_rx_thread = threading.Thread(target=self._rx.stop)
            stop_rx_thread.daemon = True
            stop_rx_thread.start()

    def send(self, data):
        '''Encode and send data via the underlying transmit FSKModem instance.
        
        Data is UTF-8 encoded to bytes and wrapped with HDLC flags prior to transmitting.

        If actively receiving (a carrier event has occured), outgoing data is buffered for later transmission.

        Args:
            data (str): data to send
        '''
        data = data.encode('utf-8')
        self.send_raw(data)
    
    def send_raw(self, data):
        '''Send data via the underlying transmit FSKModem instance.
        
        Data is wrapped with HDLC flags prior to transmitting.

        If actively receiving (a carrier event has occured), outgoing data is buffered for later transmission.

        Args:
            data (bytes): data to send

        Raises:
            TypeError: specified data is not type bytes
        '''
        if type(data) != bytes:
            raise TypeError('Raw data must be of type bytes, not: {}'.format(str(type(data)))
            return None

        if self.carrier_sense:
            self._tx_buffer.append(data)
            return None

        # wrap data in start and stop flags
        data = HDLC.START + data + HDLC.STOP

        # toggle ptt
        if self._ptt is not None:
            self._toggle_ptt_callback()
        
        self._tx.send(data)

        # toggle ptt
        if self._ptt is not None:
            self._toggle_ptt_callback()

    def set_rx_callback(self, callback):
        '''Set incoming packet callback function.
            
        Callback function signature:
        function(data, confidence) where *data* is type *bytes* and *confidence* is type *float*

        Args:
            callback (function): Function to call when a packet is received
        '''
        self._rx_callback = callback

    def set_ptt_callback(self, callback):
        '''Set PTT toggle callback function.

        Args:
            callback (function): Function to call to toggle radio PTT state

        Raises:
            TypeError: Specified callback object is not callable
        '''
        if callable(callback):
            self._toggle_ptt_callback = callback
        else:
            raise TypeError('Specified callback object is not callable')
    
    def _receive(self):
        '''Get next byte from receive MiniModem instance.

        Always call this function from a thread since the underlying subprocess pipe read will not return until data is available.
        Validation of the received byte is performed by attempting to decode the byte and catching any UnicodeDecodeError exceptions.

        Returns:
            bytes: Received byte string (could be  b'' if a decode error occured)
        '''
        data = self._rx.receive()

        # capture characters that cannot be decoded (receiver noise)
        try:
            data.decode('utf-8')
        except UnicodeDecodeError:
            return b''
        
        return data

    def _job_loop(self):
        '''Process data in the transmit buffer when not receiving.'''

        while self.online:
            while self.carrier_sense:
                time.sleep(0.01) # 10 milliseconds

            # random delay (100 - 250 milliseconds) before transmitting to avoid collisions
            time.sleep(random.uniform(0.10, 0.25))
                time.sleep(random.uniform(0.5, 2.0))

            # process next item in transmit buffer
            if not self.carrier_sense and len(self._tx_buffer) > 0:
                data = self._tx_buffer.pop(0)
                self.send(data)
    
    def _rx_loop(self):
        '''Receive incoming bytes into a buffer and find data packets.

        The configured rx callback function is called once a complete packet is received.
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
                        
                        # under max packet length, receive data
                        if len(data) <= self.MTU:
                            # wait for confidence data to be available
                            #TODO test timeout duration on a slow platform (i.e Raspberry Pi)
                            if self._rx_confidence['timestamp'] == 0:
                                timeout = 0.100 # 100 milliseconds
                                start_time = time.time()
                                while self._rx_confidence['timestamp'] == 0 and time.time() < (start_time + timeout):
                                    time.sleep(0.001) # 1 millisecond

                            if self.rx_callback is not None:
                                self.rx_callback(data, self._rx_confidence['confidence'])

                            # reset confidence data to avoid reuse
                            self._rx_confidence['confidence'] = 0.0
                            self._rx_confidence['timestamp'] = 0

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

            #TODO test timeout duration on a slow platform (i.e Raspberry Pi)
            # if confidence data is stale (> 100 milliseconds old) discard it
            if (
                self._rx_confidence['timestamp'] != 0 and
                self._rx_confidence['timestamp'] < (time.time() - 0.100)
            ):
                self._rx_confidence['confidence'] = 0.0
                self._rx_confidence['timestamp'] = 0

            # simmer down
            time.sleep(0.001)

    def _stderr_loop(self):
        '''Receive stderr data from the MiniModem process into a buffer and identify carrier events.

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

                        # find confidence data in no-carrier event
                        for data in carrier_event_data:
                            if b'confidence' in data:
                                carrier_confidence = data.split(b'=')
                                carrier_confidence = carrier_confidence[1]
                                break

                        # try to decode and record confidence data
                        try:
                            carrier_confidence = float(carrier_confidence.decode('utf-8'))
                            self._rx_confidence['confidence'] = carrier_confidence
                            self._rx_confidence['timestamp'] = time.time()
                        except:
                            # discard on failure to decode or cast to float
                            pass

            else:
                # avoid missing symbol split over multiple loop iterations
                if len(stderr_buffer) > 2 * len(carrier_event_symbol):
                    stderr_buffer = b''

            # simmer down
            time.sleep(0.001)



def get_alsa_device(device_desc, device_mode=RX):
    '''Get ALSA 'card,device' device string based on device description text.

    The purpose of this function is to ensure the correct card and device are identified in case the connected audo devices change. The output of 'arecord -l' or 'aplay -l' (depending on specified device mode) is used to get device descriptions. Try running the applicable command (arecord or aplay) to find the device description.

    Args:
        device_desc (str): Snique string to search for in device descriptions (ex. 'USB PnP' or 'QDX')
        device_mode (str): Search for input or output audio devices (optional, default: fskmodem.RX, see module constants)

    Returns:
        str: Card and device (ex. '2,0')
        None: No device was found matching the specified text
    '''
    if device_mode == RX:
        alsa_cmd = ['arecord', '-l']
    elif device_mode == TX:
        alsa_cmd = ['aplay', '-l']
    else:
        raise Exception('Unknown mode: {}'.format(device_mode))
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
            # build and return the device string
            return '{},{}'.format(card, device)

