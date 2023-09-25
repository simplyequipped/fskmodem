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
import argparse
import threading

import fskmodem


class HDLC:
    # RNS Pipe Interface packetizes data using simplified HDLC framing, similar to PPP
    FLAG              = 0x7E
    ESC               = 0x7D
    ESC_MASK          = 0x20

    @staticmethod
    def escape(data):
        data = data.replace(bytes([HDLC.ESC]), bytes([HDLC.ESC, HDLC.ESC^HDLC.ESC_MASK]))
        data = data.replace(bytes([HDLC.FLAG]), bytes([HDLC.ESC, HDLC.FLAG^HDLC.ESC_MASK]))
        return data


def _write_stdout(data):
    sys.stdout.write(data)
    sys.stdout.flush()

def _read_stdin():
    global modem
    in_frame = False
    escape = False
    data_buffer = b''
    
    while modem.online:
        byte = sys.stdin.read(1)

        if len(byte) == 0:
            # EOL reached, pipe closed
            modem.stop()
            break
        
        byte = ord(byte)

        if (in_frame and byte == HDLC.FLAG):
            in_frame = False
            modem.send_bytes(data_buffer)
        elif (byte == HDLC.FLAG):
            in_frame = True
            data_buffer = b''
        elif (in_frame and len(data_buffer) < modem.MTU):
            if (byte == HDLC.ESC):
                escape = True
            else:
                if (escape):
                    if (byte == HDLC.FLAG ^ HDLC.ESC_MASK):
                        byte = HDLC.FLAG
                    if (byte == HDLC.ESC  ^ HDLC.ESC_MASK):
                        byte = HDLC.ESC
                    escape = False
                data_buffer += bytes([byte])
                
if __name__ == '__main__':
    help_epilog = '\'--search_alsa_dev_in\' is set to \'QDX\' if no audio devices are specifed and --qdxcat is set.\')'
    parser = argparse.ArgumentParser(description='stdin/stdout pipe interface for fskmodem', epilog = help_epilog)
    parser.add_argument('--search_alsa_dev_in', help='ALSA audio input device search text')
    parser.add_argument('--search_alsa_dev_out', help='ALSA audio output device search text')
    parser.add_argument('--alsa_dev_in', help='ALSA audio input device formated as \'card,device\'')
    parser.add_argument('--alsa_dev_out', help='ALSA audio output device formated as \'card,device\'')
    parser.add_argument('--baudmode', help='Baudmode of the modem', default='300')
    parser.add_argument('--sync_byte', help='Suppress rx carrier detection until the specified byte is received (ex. \'0x23\')')
    parser.add_argument('--confidence', help='Minimum confidence threshold based on SNR (i.e. squelch)', default=1.5, type=float)
    parser.add_argument('--mark', help='Mark frequency in Hz', type=int)
    parser.add_argument('--space', help='Space frequency in Hz', type=int)
    parser.add_argument('--qdxcat', help='Utilize qdxcat for PTT control of QRPLabs QDX radio', action='store_true')
    parser.add_argument('--qdxcat_freq', help='QDX radio frequency in Hz', type=int)
    args = parser.parse_args()

    search_alsa_dev_in = args.search_alsa_dev_in

    if args.qdxcat:
        # init qdx cat control
        import qdxcat
        qdx = qdxcat.QDX()

        if args.qdxcat_freq:
            # set qdx vfo frequency
            qdx.set(qdx.VFO_A, args.qdxcat_freq)

        if (args.qdxcat and
            search_alsa_dev_in is None and
            args.search_alsa_dev_out is None and
            args.alsa_dev_in is None and
            args.alsa_dev_out is None
        ):
            # use QDX audio device if no other audio devices specified and qdxcat is set
            search_alsa_dev_in = 'QDX'
    
    modem = fskmodem.Modem(
        search_alsa_dev_in,
        args.search_alsa_dev_out,
        args.alsa_dev_in,
        args.alsa_dev_out,
        args.baudmode,
        args.sync_byte,
        args.confidence,
        args.mark,
        args.space
    )

    if args.qdxcat:
        # set qdx ptt toggle callback
        modem.set_ptt_callback(qdx.toggle_ptt)

    # on modem rx, write to stdout pipe
    modem.set_rx_callback(_write_stdout)

    # read from stdin, send via modem tx
    thread = threading.Thread(target=_read_stdin)
    thread.daemon = True
    thread.start()

    while modem.online:
        time.sleep(0.25)
