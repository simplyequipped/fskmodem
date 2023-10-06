# MIT License
# 
# Copyright (c) 2022-2023 Simply Equipped
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

__docformat__ = 'google'


'''A full duplex AFSK soft modem.

[minimodem](http://www.whence.com/minimodem/) application copyright by Kamal Mostafa.

The *minimodem* application can be installed on Debian systems with the following command:
`sudo apt install minimodem`

See the [minimodem manpage](http://www.whence.com/minimodem/minimodem.1.html) for more information about configuration options and supported protocols.

*minimodem* Protocol Defaults:

| Baudmode | Baudrate | Mode | Mark | Space | Notes |
| -------- | -------- | -------- | -------- | -------- | -------- |
| N | N bps | Bell 202-style | 1200 Hz | 2200 Hz | sets `--ascii` |
| 1200 | 1200 bps | Bell 202 | 1200 Hz | 2200 Hz | sets `--ascii` |
| 300 | 300 bps | Bell 103 | 1270 Hz | 1070 Hz | sets `--ascii` |
| rtty | 45.45 bps | Bell 103 | variable | -170 Hz | sets `--baudot --stopbits 1.5` |
| tdd | 45.45 bps | TTY/TDD | 1400 Hz | 1800 Hz | sets `--baudot --stopbits 2` |
| same | 520.83 bps | NOAA S.A.M.E. | 2083 1/3 Hz | 1562.5 Hz | sets `−−startbits 0 −−stopbits 0 −−sync-byte 0xAB` |
| callerid | 1200 bps | Bell 202 Caller-ID (MDMF or SDMF) | 1200 Hz | 2200 Hz | receive only |
| uic-train | 600 bps | UIC-751-3 train-to-ground | 1300 Hz | 1700 Hz | receive only, `−−startbits 8 −−stopbits 0` |
| uic-ground | 600 bps | UIC-751-3 ground-to-train | 1300 Hz | 1700 Hz | receive only, `−−startbits 8 −−stopbits 0` |
'''

import os
import sys
import time
import random
import atexit
import shutil
import threading
import subprocess
from subprocess import PIPE, CalledProcessError, SubprocessError


class HDLC:
    '''Defines packet framing flags similar to HDLC or PPP.
    
    Multiple characters per flag makes it less likely that receiver noise will emulate a flag.
    
    Attributes:
        START (bytes): b'|>'
        STOP (bytes): b'<|'
    '''

    START = b'|>'
    STOP = b'<|'


class FSKBase:
    '''Create and interact with a minimodem subprocess.

    Attributes:
        mode (str): Operating mode of the minimodem application ('rx', 'receive', 'read', 'tx', 'transmit', or 'write')
        alsa_dev (str or None): ALSA audio device formated as 'card,device' (ex. '2,0'), or None if using system default audio device
        baudmode (int): Baudmode of the modem (see package docs or *minimodem* docs for more details)
        baud (int): Baud rate of the modem, based on *baudmode*
        sync_byte (str): Suppress rx carrier detection until the specified byte is received, defaults to None
        confidence (float): Minimum confidence threshold based on SNR (i.e. squelch), defaults to None
        mark (int): Mark frequency in Hz, defaults to None
        space (int): Space frequency in Hz, defaults to None
        online (bool): True if subprocess is running, False otherwise
    '''
    def __init__(self, mode, alsa_dev=None, baudmode=300, sync_byte=None, confidence=None, mark=None, space=None, start=True):
        '''Initialize FSKBase class instance.
        
        Args:
            mode (str): Operating mode of the minimodem application ('rx', 'receive', 'read', 'tx', 'transmit', or 'write')
            alsa_dev (str): ALSA audio device formated as 'card,device' (ex. '2,0'), defaults to None
            baudmode (int): Baudmode of the modem (see package docs or *minimodem* docs for more details), defaults to 300
            sync_byte (str): Suppress rx carrier detection until the specified byte is received, defaults to None
            confidence (float): Minimum confidence threshold based on SNR (i.e. squelch), defaults to None
            mark (int): Mark frequency in Hz, defaults to None
            space (int): Space frequency in Hz, defaults to None
            start (bool): Start minimodem subprocess on object instantiation, defaults to True

        Returns:
            fskmodem.FSKBase: FSKBase instance object

        Raises:
            ProcessLookupError: minimodem application not installed
        '''
        self.mode = mode.lower()
        self.alsa_dev = alsa_dev
        self.baudmode = str(baudmode)
        self.sync_byte = sync_byte
        self.confidence = confidence
        self.mark = mark
        self.space = space
        self.online = False
        self._process = None
        self._shell_cmd = None

        # get full file path for minimodem executable
        exec_path = shutil.which('minimodem')
        
        if exec_path is None:
            # minimodem not installed
            raise ProcessLookupError('minimodem application not installed, try: sudo apt install minimodem')

        # configure minimodem comand line switches
        switch_alsa_dev = None
        switch_sync_byte = None
        switch_confidence = None
        switch_mark = None
        switch_space = None
        switch_mode = '--{}'.format(self.mode)
        switch_filter = '--print-filter'

        if self.alsa_dev is not None:
            switch_alsa_dev = '--alsa={}'.format(self.alsa_dev)
        if self.sync_byte is not None:
            switch_sync_byte = '--sync-byte {}'.format(self.sync_byte)
        if self.confidence is not None:
            switch_confidence = '--confidence {}'.format(self.confidence)
        if self.mark is not None:
            switch_mark = '--mark {}'.format(self.mark)
        if self.space is not None:
            switch_space = '--space {}'.format(self.space)

        switches = [switch_mode, switch_alsa_dev, switch_confidence, switch_sync_byte, switch_filter, switch_mark, switch_space]
        switches = [switch for switch in switches if switch is not None]
        # note from minimodem docs: confidence, sync byte, quiet, and print filter are ignored in tx mode
        self._shell_cmd = '{} {} {}'.format(exec_path, ' '.join(switches), self.baudmode)

        if start:
            self.start()
        
    def start(self):
        '''Start minimodem subprocess.'''
        if self.online:
            return
            
        # create subprocess with pipes for interaction with child process
        self._process = subprocess.Popen(self._shell_cmd, shell=True, bufsize=-1, stdin=PIPE, stdout=PIPE, stderr=PIPE)

        time.sleep(0.1)
        
        # check if process failed with exit code (returns None if running)
        exit_code = self._process.poll()
        if exit_code != None:
            raise SubprocessError('{} subprocess failed with exit code {}, check minimodem settings (ex. ALSA device)'.format(self.mode.title(), exit_code))

        self.online = True

    def stop(self):
        '''Stop minimodem subprocess.'''
        self.online = False
        # try to terminate normally
        self._process.terminate()
        # use a thread to communicate non-blocking-ly
        comm_thread = threading.Thread(target=self._process.communicate)
        comm_thread.daemon = True
        comm_thread.start()
        
        comm_start = time.time()
        comm_timeout = 5
        # manual timeout
        while time.time() < comm_start + comm_timeout:
            time.sleep(1)

        if self._process.poll() == None:
            # if the process still hasn't stopped, try to kill it
            self._process.kill()
            # use a thread to communicate non-blocking-ly
            comm_thread = threading.Thread(target=self._process.communicate)
            comm_thread.daemon = True
            comm_thread.start()


class FSKReceive(FSKBase):
    '''Reciever subclass of the FSKBase class.'''
    
    def __init__(self, **kwargs):
        '''Initialize FSKRecieve class instance.

        Args:
            alsa_dev (str): Input/output ALSA device formated as 'card,device' (ex. '2,0'), defaults to None
            baudmode (int): Baudmode of the modem (see package docs or *minimodem* docs for more details), defaults to 300
            sync_byte (str): Suppress rx carrier detection until the specified byte is received, defaults to None
            confidence (float): Minimum confidence threshold based on SNR (i.e. squelch), defaults to None
            mark (int): Mark frequency in Hz, defaults to None
            space (int): Space frequency in Hz, defaults to None
            start (bool): Start minimodem subprocess on object instantiation, defaults to True

        Returns:
            fskmodem.FSKRecieve: FSKReceive instance object
        '''
        self.mode = 'rx'
        super().__init__(self.mode, **kwargs)

    def receive(self, size=1):
        '''Receive data from minimodem subprocess.

        Reading from the subprocess.Popen.stdout pipe is blocking until the specified number of bytes is available.

        Args:
            size (int): Number of bytes to read from the subprocess pipe

        Returns:
            bytes: Received byte string of specified length
        '''
        return self._process.stdout.read(size)

    def get_stderr(self, size=1):
        '''Get stderr data from minimodem subprocess.

        Reading from the subprocess.Popen.stderr pipe is blocking until the specified number of bytes is available.

        Args:
            size (int): Number of bytes to read from the subprocess pipe

        Returns:
            bytes: Received byte string of specified length
        '''
        return self._process.stderr.read(size)


class FSKTransmit(FSKBase):
    '''Transmitter subclass of the FSKBase class.'''
    
    def __init__(self, **kwargs):
        '''Initialize FSKTransmit class instance.

        Args:
            alsa_dev (str): Input/output ALSA device formated as 'card,device' (ex. '2,0'), defaults to None
            baudmode (int): Baudmode of the modem (see package docs or *minimodem* docs for more details), defaults to 300
            sync_byte (str): Suppress rx carrier detection until the specified byte is received, defaults to None
            confidence (float): Minimum confidence threshold based on SNR (i.e. squelch), defaults to None
            mark (int): Mark frequency in Hz, defaults to None
            space (int): Space frequency in Hz, defaults to None
            start (bool): Start minimodem subprocess on object instantiation, defaults to True

        Returns:
            fskmodem.FSKTransmit: FSKTransmit instance object
        '''
        self.mode = 'tx'
        super().__init__(self.mode, **kwargs)

    def send(self, data):
        '''Send data to the minimodem subprocess.

        Args:
            data (int): byte string to send to the subprocess pipe
        '''
        if self.sync_byte is not None:
            data = self.sync_byte.encode('utf-8') + data

        self._process.stdin.write(data)
        self._process.stdin.flush()


class Modem:
    '''Create and manage an AFSK soft modem.

    Attributes:
        alsa_in (str): ALSA audio input device formated as 'card,device' (ex. '2,0')
        alsa_out (str): ALSA audio output device formated as 'card,device' (ex. '2,0')
        baudmode (str or int): Baudmode of the modem (see package docs or *minimodem* docs for more details), defaults to 300
        baudrate (int): Baudrate of the modem, determined by *baudmode*
        sync_byte (str): Suppress rx carrier detection until the specified byte is received, defaults to '0x23' (utf-8 '#')
        confidence (float): Minimum confidence threshold based on SNR (i.e. squelch), defaults to 1.5
        MTU (int): Maximum size of packet to be transmitted or received (default: 500, see Reticulum Network Stack)
        online (bool): True if modem subprocesses are running, False otherwise
        carrier_sense (bool): True if incoming carrier detected, False otherwise
        BAUDMODES (dict): Map of *minimodem* baudmodes to baudrates
    '''

    # minimodem baudmodes and assocaited baudrates
    BAUDMODES = {
        'rtty': 45.45,
        'tdd': 45.45,
        'same': 520.83,
        'callerid': 1200,
        'uic-train': 600,
        'uic-ground': 600
    }

    @staticmethod
    def get_alsa_device(device_desc, device_type='input'):
        '''Get ALSA device string based on device description text.
    
        The purpose of this function is to ensure the correct card and device are identified in case the connected audo devices change. Device descriptions are sourced from 'arecord -l' (input) or 'aplay -l' (output) bash commands.
    
        Args:
            device_desc (str): Text to search for in device descriptions (ex. 'QDX')
            device_type (str): 'input' to match audio input devices or 'output' to match audio output devices, defaults to 'input'
    
        Returns:
            - str: Card and device (ex. '2,0')
            - None: No device matching the specified text
        '''
        device_type = device_type.lower()
        
        if device_type == 'input':
            alsa_cmd = ['arecord', '-l']
        elif device_type == 'output':
            alsa_cmd = ['aplay', '-l']
        else:
            raise Exception('Unknown device type: {}'.format(device_type))
    
        alsa_dev = None
        # get audio device descriptions
        alsa_devs = subprocess.check_output(alsa_cmd).decode('utf-8').split('\n')
    
        for line in alsa_devs:
            if device_desc in line:
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
                
                return '{},{}'.format(card, device)

    def __init__(self, search_alsa_in=None, search_alsa_out=None, alsa_in=None, alsa_out=None, baudmode=300, sync_byte=None, confidence=1.5, mark=None, space=None, start=True):
        '''Initialize Modem class instance.

        Use *search_alsa_in* and *search_alsa_out* to search for an ALSA audio device containing the specified text. If *search_alsa_out* is *None*, *search_alsa_in* is used for both input and output audio devices.

        Use *alsa_in* and *alsa_out* to specify an audio device by ALSA card/device (ex. '2,0'). If *alsa_out* is *None*, *alsa_in* is used for both input and output audio devices.
        
        If no audio device arguments are set, the ALSA default system device will be used.
        
        Args:
            search_alsa_in (str): ALSA audio input device search text (ex. 'QDX'), defaults to None
            search_alsa_out (str): ALSA audio output device search text (ex. 'QDX'), defaults to None
            alsa_in (str): ALSA audio input device formated as 'card,device' (ex. '2,0'), defaults to None
            alsa_out (str): ALSA audio output device formated as 'card,device' (ex. '2,0'), defaults to None
            baudmode (str or int): Baudmode of the modem (see package docs or *minimodem* docs for more details), defaults to 300
            sync_byte (str): Suppress rx carrier detection until the specified byte is received, defaults to None
            confidence (float): Minimum confidence threshold based on SNR (i.e. squelch), defaults to 1.5
            mark (int): Mark frequency in Hz, defaults to None
            space (int): Space frequency in Hz, defaults to None
            start (bool): Start modem subprocesses on object instantiation, defaults to True

        Returns:
            fskmodem.Modem: Modem instance object

        Raises:
            OSError: No ALSA audio device found containing specified search text
            ValueError: Unable to determine baudrate from specified baudmode
        '''
        if search_alsa_in is not None:
            # get first alsa card/device containing specified text
            alsa_in = Modem.get_alsa_device(search_alsa_in, 'input')
            if alsa_in is None:
                raise OSError('No ALSA audio input device found containing: {}'.format(search_alsa_in))

        if search_alsa_out is not None:
            alsa_out = Modem.get_alsa_device(search_alsa_out, 'output')
            if alsa_out is None:
                raise OSError('No ALSA audio output device found containing: {}'.format(search_alsa_out))

        if alsa_in is not None and alsa_out is None:
            alsa_out = alsa_in
            
        self.alsa_in = alsa_in
        self.alsa_out = alsa_out
        self.baudmode = str(baudmode)
        self.sync_byte = sync_byte
        self.confidence = confidence
        self.mark = mark
        self.space = space
        self.MTU = 500
        self.online = False
        self.carrier_sense = False
        self._debug = False
        self._rx_callback = None
        self._rx_callback_bytes = None
        self._toggle_ptt_callback = None
        self._rx_confidence = 0
        self._rx_confidence_timestamp = 0
        self._tx_buffer = []
        self._rx = None
        self._tx = None

        # determine baudrate based on specified baudmode
        #TODO does not support float baudrates
        if self.baudmode.isnumeric():
            self.baudrate = int(self.baudmode)
        elif self.baudmode in Modem.BAUDMODES:
            self.baudrate = Modem.BAUDMODES[self.baudmode]
        else:
            raise ValueError('Unable to determine baudrate from baudmode: {}'.format(self.baudmode))

        # configure exit handler
        atexit.register(self.stop)

        if start:
            self.start()

    def start(self):
        '''Start modem monitoring loops and subprocesses.'''
        self._rx = FSKReceive(alsa_dev=self.alsa_in, baudmode=self.baudmode, sync_byte=self.sync_byte, confidence=self.confidence, mark=self.mark, space=self.space)
        self._tx = FSKTransmit(alsa_dev=self.alsa_out, baudmode=self.baudmode, sync_byte=self.sync_byte, confidence=self.confidence, mark=self.mark, space=self.space)
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
        job_thread = threading.Thread(target=self._tx_loop)
        job_thread.daemon = True
        job_thread.start()

    def stop(self):
        '''Stop modem and subprocesses.'''
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

    def set_rx_callback(self, callback):
        '''Set incoming packet callback function.
            
        Callback function signature:
            function(data, confidence) where *data* is type *str* and *confidence* is type *float*

        Args:
            callback (function): Function to call when a packet is received

        Raises:
            TypeError: Specified callback object is not callable
        '''
        if callable(callback):
            self._rx_callback = callback
        else:
            raise TypeError('Specified callback object is not callable')

    def set_rx_callback_bytes(self, callback):
        '''Set incoming packet bytes callback function.
            
        Callback function signature:
            function(data) where *data* is type *bytes*

        Args:
            callback (function): Function to call when a packet is received

        Raises:
            TypeError: Specified callback object is not callable
        '''
        if callable(callback):
            self._rx_callback_bytes = callback
        else:
            raise TypeError('Specified callback object is not callable')

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

    def send(self, data):
        '''Send string via transmit FSKModem instance.
        
        Data is utf-8 encoded to bytes and wrapped with HDLC flags prior to transmitting.

        Args:
            data (str): data to send
        '''
        data = data.encode('utf-8')
        self.send_bytes(data)
    
    def send_bytes(self, data):
        '''Send bytes via transmit FSKModem instance.
        
        Data is wrapped with HDLC flags.

        Args:
            data (bytes): data to send

        Raises:
            TypeError: specified data is not type bytes
        '''
        if not isinstance(data, bytes):
            raise TypeError( 'Data must be of type bytes, {} given'.format( type(data) ) )

        data = HDLC.START + data + HDLC.STOP
        self._tx_buffer.append(data)

    def _toggle_ptt(self):
        '''Toggle radio PTT via callback function.'''
        if self._toggle_ptt_callback is not None:
            if self._debug:
                print('PTT')

            self._toggle_ptt_callback()
    
    def _receive_next(self):
        '''Get next byte from receive minimodem instance.

        Always call this function from a thread since the underlying subprocess pipe read will not return until data is available.
        Validation of the received byte is performed by attempting to decode the byte and catching any UnicodeDecodeError exceptions.

        Returns:
            bytes: Received byte string (may be  b'' if a decode error occured)
        '''
        data = self._rx.receive()

        # capture characters that cannot be decoded (receiver noise)
        try:
            data.decode('utf-8')
        except UnicodeDecodeError:
            return b''
        
        if self._debug:
            print(data.decode('utf-8'), sep='', end='', flush=True)

        return data

    def _process_rx_callback(self, data, confidence):
        '''Call rx callback functions via thread.

        If *str* and *bytes* callbacks are set, both callbacks will be called.

        Args:
            data (bytes): received data
            confidence (float): receiver confidence near the time the data was received
        '''
        if self._debug:
            print('\nRX: ' + data.decode('utf-8'))
        
        if self._rx_callback_bytes is not None:
            # use bytes callback function
            rx_bytes_thread = threading.Thread(target=self._rx_callback_bytes, args=data)
            rx_bytes_thread.daemon = True
            rx_bytes_thread.start()
            
        if self._rx_callback is not None:
            # decode data before callback
            data = data.decode('utf-8')
            # use str callback function
            rx_thread = threading.Thread(target=self._rx_callback, args=(data, confidence))
            rx_thread.daemon = True
            rx_thread.start()

    def _rx_loop(self):
        '''Receive incoming bytes into a buffer and find data packets.

        The rx callback function is called once a complete packet is received.
        '''
        data_buffer = b''
        max_data_buffer_len = 1024

        while self.online:
            # blocks until next character received
            data_buffer += self._receive_next()
            
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
                            if self._rx_confidence_timestamp == 0:
                                timeout = time.time() + 0.1 # 100 ms
                                while self._rx_confidence_timestamp == 0 and time.time() <= timeout:
                                    time.sleep(0.001) # 1 millisecond

                            self._process_rx_callback(data, self._rx_confidence)
                            # reset confidence data to avoid reuse
                            self._rx_confidence = 0
                            self._rx_confidence_timestamp = 0

                        else:
                            # over max packet length, drop data
                            pass
                    else:
                        # partial packets causing mixed up delimiters, remove buffer data up to last start delimiter
                        data_buffer = data_buffer[start + len(HDLC.START):]
                else:
                    if len(data_buffer) > max_data_buffer_len:
                        # no end delimiter and buffer length over max packaet size, remove buffer data up to last start delimiter
                        data_buffer = data_buffer[data_buffer.rfind(HDLC.START):]
            else:
                # avoid missing start delimiter split over multiple loop iterations
                if len(data_buffer) > 10 * len(HDLC.START):
                    data_buffer = b''

            #TODO test timeout duration on a slow platform (i.e Raspberry Pi)
            # discard confidence data if older than 100 ms
            if self._rx_confidence != 0 and self._rx_confidence_timestamp < (time.time() - 0.1):
                self._rx_confidence = 0
                self._rx_confidence_timestamp = 0

            # simmer down
            time.sleep(0.001)

    def _tx_loop(self):
        '''Process data in the transmit buffer.'''
        while self.online:
            time.sleep(0.01) # 10 ms
            
            if self.carrier_sense:
                continue

            # process transmit buffer
            if len(self._tx_buffer) > 0:
                # random delay (100 - 250 ms) before transmitting to avoid collisions
                time.sleep(random.uniform(0.10, 0.25))
                
                if self.carrier_sense:
                    continue

                # track bytes sent and start time
                tx_bit_count = 0
                tx_start_timestamp = time.time()
                self._toggle_ptt()
                time.sleep(0.1) # 100 ms
                
                while len(self._tx_buffer) > 0:
                    data = self._tx_buffer.pop(0)

                    if self._debug:
                        print('TX: ' + data.decode('utf-8'))

                    self._tx.send(data)
                    tx_bit_count += len(data) * 8

                # calculate duration of transmission based on number of bits sent
                if self.sync_byte is not None:
                    # minimodem adds 16 leading sync bytes, plus start and stop bytes for each sync byte
                    tx_bit_count += 16 * (8 + 2)

                # bits sent / baudrate = transmit time in seconds
                tx_duration = tx_bit_count / self.baudrate
                # 1.3x mupltiplier necessary to align with actual transmit duration
                tx_duration *= 1.3
                # 0.5 sec ptt tail
                tx_duration += 0.5

                tx_end_timestamp = tx_start_timestamp + tx_duration
                
                while time.time() < tx_end_timestamp:
                    time.sleep(0.1) # 100 ms
                    
                self._toggle_ptt()

                if self._debug:
                    duration = tx_end_timestamp - tx_start_timestamp
                    print('{} bits at {} bps     tx duration: {} s'.format(tx_bit_count, self.baudrate, tx_duration))


    def _stderr_loop(self):
        '''Receive stderr data from the MiniModem process into a buffer and identify carrier events.

        The carrier sense property is set (True/False) depending on the type of event received (CARRIER or NOCARRIER).
        '''
        stderr_buffer = b''
        carrier_event_symbol = b'###'

        while self.online:
            # blocks until next character received
            stderr_buffer += self._rx.get_stderr()
            
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
                            self._rx_confidence = carrier_confidence
                            self._rx_confidence_timestamp = time.time()
                        except:
                            # discard on failure to decode or cast to float
                            pass

            else:
                # avoid missing symbol split over multiple loop iterations
                if len(stderr_buffer) > 2 * len(carrier_event_symbol):
                    stderr_buffer = b''

            # simmer down
            time.sleep(0.001)
            
