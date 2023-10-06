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

'''stdin/stdout pipe interface for fskmodem.

Developed for use with the [RNS PipeInterface](https://markqvist.github.io/Reticulum/manual/interfaces.html#pipe-interface), but may have other CLI uses as well.

Try `python -m fskmodem --help` for command line switch options.
'''

#TODO
# - subprocess call for external ptt on, off, and toggle scripts, script paths supplied via args

import sys
import time
import argparse
import threading

import fskmodem


class HDLC:
    # RNS PipeInterface packetizes data using simplified HDLC framing, similar to PPP
    FLAG = 0x7E
    ESC = 0x7D
    ESC_MASK = 0x20

    @staticmethod
    def escape(data):
        data = data.replace(bytes([HDLC.ESC]), bytes([HDLC.ESC, HDLC.ESC^HDLC.ESC_MASK]))
        data = data.replace(bytes([HDLC.FLAG]), bytes([HDLC.ESC, HDLC.FLAG^HDLC.ESC_MASK]))
        return data


def _write_stdout(data, confidence):
    sys.stdout.write(data)
    sys.stdout.flush()

def _read_stdin():
    global modem
    global EOM # end of message
    data_buffer = ''
    
    while modem.online:
        byte = sys.stdin.read(1)

        if len(byte) == 0:
            # EOL reached, pipe closed
            modem.stop()
            break

        data_buffer += byte

        if len(data_buffer) > modem.MTU:
            data_buffer = ''
        elif len(data_buffer) >= 2 and data_buffer[-2:] == EOM:
            modem.send(data_buffer[:-2])
            data_buffer = ''

def _rns_write_stdout(data, confidence):
    data = bytes([HDLC.FLAG]) + HDLC.escape(data) + bytes([HDLC.FLAG])
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()

def _rns_read_stdin():
    global modem
    in_frame = False
    escape = False
    data_buffer = b''
    
    while modem.online:
        byte = sys.stdin.buffer.read(1)

        if len(byte) == 0:
            # EOL reached, pipe closed
            modem.stop()
            break
        
        byte = ord(byte)

        if in_frame and byte == HDLC.FLAG:
            in_frame = False
            modem.send_bytes(data_buffer)

        elif byte == HDLC.FLAG:
            in_frame = True
            data_buffer = b''

        elif in_frame and len(data_buffer) < modem.MTU:
            if byte == HDLC.ESC:
                escape = True
            else:
                if escape:
                    if byte == HDLC.FLAG ^ HDLC.ESC_MASK:
                        byte = HDLC.FLAG
                    if byte == HDLC.ESC ^ HDLC.ESC_MASK:
                        byte = HDLC.ESC
                    escape = False
                data_buffer += bytes([byte])


if __name__ == '__main__':
    help_epilog = 'The qdxcat package is required to use *--qdx* options.\n'
    help_epilog += 'If *--qdx* is specified, and no audio devices are specified, *--search_alsa_in* is set to \'QDX\'.\n'
    help_epilog += 'See fskmodem docs for more information on ALSA audio device settings:\n'
    help_epilog += 'https://simplyequipped.github.io/fskmodem/fskmodem/modem.html#Modem\n'

    program = 'python -m fskmodem'

    parser = argparse.ArgumentParser(prog=program, description='CLI for fskmodem package', epilog = help_epilog)
    parser.add_argument('--search-alsa-in', help='ALSA audio input device search text', metavar='TEXT')
    parser.add_argument('--search-alsa-out', help='ALSA audio output device search text', metavar='TEXT')
    parser.add_argument('--alsa-in', help='ALSA audio input device formated as \'card,device\'', metavar='DEVICE')
    parser.add_argument('--alsa-out', help='ALSA audio output device formated as \'card,device\'', metavar='DEVICE')
    parser.add_argument('--baudmode', help='Baudmode of the modem', default='300')
    parser.add_argument('--sync-byte', help='Suppress rx carrier detection until the specified ordinal byte value is received (ex. \'0x23\')', metavar='BYTE')
    parser.add_argument('--confidence', help='Minimum confidence threshold based on SNR (i.e. squelch)', default=1.5, type=float, metavar='CONF')
    parser.add_argument('--mark', help='Mark frequency in Hz', type=int, metavar='FREQ')
    parser.add_argument('--space', help='Space frequency in Hz', type=int, metavar='FREQ')
    parser.add_argument('--eom', help='stdin end-of-message string, defaults to \'\\n\\n\' (not used with *--rns*)', default='\n\n')
    parser.add_argument('--rns', help='Use RNS PipeInterface framing', action='store_true')
    parser.add_argument('--quiet', help='Do not print messages on start', action='store_true')
    parser.add_argument('--qdx', help='Utilize qdxcat for PTT control of QRPLabs QDX radio, optionally followed by QDX frequency in Hz', nargs='?', default=False, const=True, metavar='[FREQ]')
    args = parser.parse_args()

    search_alsa_in = args.search_alsa_in
    EOM = args.eom

    if args.qdx:
        # init qdx cat control
        import qdxcat
        qdx = qdxcat.QDX()

        if isinstance(args.qdx, str):
            # set qdx vfo frequency
            freq = int(args.qdx)
            qdx.set(qdx.VFO_A, freq)

        if (args.qdx and
            search_alsa_in is None and
            args.search_alsa_out is None and
            args.alsa_in is None and
            args.alsa_out is None
        ):
            # use QDX audio device if no other audio devices specified and qdx is specified
            search_alsa_in = 'QDX'
    
    modem = fskmodem.Modem(
        search_alsa_in,
        args.search_alsa_out,
        args.alsa_in,
        args.alsa_out,
        args.baudmode,
        args.sync_byte,
        args.confidence,
        args.mark,
        args.space
    )

    if args.qdx:
        # set qdx ptt toggle callback
        modem.set_ptt_callback(qdx.toggle_ptt)

    if args.rns:
        # use RNS packet framing and bytes data
        modem.set_rx_callback_bytes(_rns_write_stdout)
        thread = threading.Thread(target=_rns_read_stdin)
    else:
        # use EOM and string data
        modem.set_rx_callback(_write_stdout)
        thread = threading.Thread(target=_read_stdin)

    thread.daemon = True
    thread.start()

    if not args.quiet and not args.rns:
        print('Press Ctrl+C to exit...')

    # modem is stopped when EOF reached on stdin pipe
    while modem.online:
        try:
            time.sleep(0.25)
        except KeyboardInterrupt:
            print()
            break

