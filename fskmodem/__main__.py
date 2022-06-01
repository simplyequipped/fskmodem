import sys, time, threading
import fskmodem

# if package is run directly, start the modem using command line arguments
# Reticulum PipeInterface operation is assumed

if __name__ == '__main__':

    modem = fskmodem.Modem(start=False)

    def rx_callback(data):
        sys.stdout.write(data.decode('utf-8'))
        sys.stdout.flush()

    def read_stdin():
        in_frame = False
        escape = False
        data_buffer = b''
        hdlc_flag = 0x7E 
        hdlc_esc = 0x7D
        hdlc_esc_mask = 0x20

        while modem.online:
            byte = sys.stdin.buffer.read(1)

            if len(byte):
                if in_frame and byte == hdlc_flag:
                    in_frame = False
                    modem.send(data_buffer)
                elif byte == hdlc_flag:
                    in_frame = True
                    data_buffer = b''
                elif in_frame and len(data_buffer) < modem.MTU:
                    if byte == hdlc.esc:
                        escape = True
                    else:
                        if escape:
                            if byte == hdlc_flag ^ hdlc_esc_mask:
                                byte = hdlc_flag
                            if byte == hdlc_esc ^ hdlc_esc_mask:
                                byte = hdlc_esc
                            escape = False

                        data_buffer += byte
                        
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            arg = arg.split('=')
            option = str(arg[0]).strip()
            value = str(arg[1]).strip()

            if option == 'get_alsa_device' and len(value) > 0:
                alsa_dev = get_alsa_device(value)
                modem.alsa_dev_in = alsa_dev
            elif option == 'alsa_dev_in':
                modem.alsa_dev_in = value
            elif option == 'alsa_dev_out':
                modem.alsa_dev_out = value
            elif option == 'baudrate':
                modem.baudrate = value
            elif option == 'sync_byte':
                modem.sync_byte = value
            elif option == 'confidence':
                modem.confidence = value

    modem.set_rx_callback(rx_callback)
    modem.start()
    
    time.sleep(0.1)
    
    thread = threading.Thread(target=read_stdin)
    thread.setDaemon(True)
    thread.start()

    
