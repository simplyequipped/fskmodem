import time
import math
import threading
import itertools

import pyaudio
import numpy as np

#TODO
# - add NRZI encode/decode
# - add framing bits
# - add sync bit
# - add bit stuffing encode/decode
#
# http://n1vg.net/packet/

class FSK:
    def __init__(self, bit_rate=44100):
        # Setup audio parameters
        self.bit_rate = bit_rate # aka frame rate
        self.bit_duration = 0.1
        self.samples_per_bit = int(self.bit_rate * self.bit_duration)
        
        self.baud_rate = 300
        self.mark_freq = 1270
        self.space_freq = 1070

    # Modulate binary data into audio frequency shifts
    # github.com/casebeer/afsk
    def modulate(self, data):
#        clock = (x / self.baud_rate for x in itertools.count(1))
#        tones = (self.mark_freq if bit is True else self.space_freq for bit in data)
#        phase = 0
#        seconds = 0
#        
#        for boundry, freq in zip(clock, tones):
#            phase_change = 2 * math.pi / (self.bit_rate / freq)
#            
#            while seconds < boundry:
#                yield math.sin(phase)
#                
#                seconds += 1.0 / self.bit_rate
#                phase += phase_change
#                
#                if phase > 2 * math.pi:
#                    phase -= 2 * math.pi
        
        for bit in data:
            freq = self.mark_freq if bit is True else self.space_freq
            tone = np.linspace(0, self.bit_duration, self.samples_per_bit, endpoint=False)
            waveform = np.sin(2 * np.pi * freq * tone)
            yield waveform

    # Demodulate audio frequency shifts into binary data
    def demodulate(self, samples):
        spectrum = np.fft.fft(samples)
        freqs = np.fft.fftfreq(samples.size, d=1 / self.bit_rate)
        pos_amplitude = np.abs(spectrum[freqs > 0])
        neg_amplitude = np.abs(spectrum[freqs < 0])
        high_amp = np.mean(pos_amplitude[freqs[freqs > 0] > self.mark_freq])
        low_amp = np.mean(pos_amplitude[freqs[freqs > 0] > self.space_freq])
        return high_amp > low_amp

    def nrzi_encode(self, data):
        state = True
        
        for bit in data:
            if bit == False:
                state = not state
                
            yield state
    
    def nrzi_decode(self, data):
        for i in range(len(data) - 1):
            if data[i] ^ data[i + 1] == True:
                yield 0
            else:
                yield 1
    
    
    
    
class FSKModem:
    def __init__(self, audio_bit_rate=44100):
        self.fsk = FSK(audio_bit_rate)
        
        self._tx_buffer = b''
        self._rx_buffer = b''
        
        # Create audio stream
        #TODO select audio device
        p = pyaudio.PyAudio()
        self.stream = p.open(format=pyaudio.paFloat32, channels=1, rate=self.bit_rate, output=True)
    
    # Send binary data over audio stream
    def send_bytes(self, bytes_to_send):
        for b in bytes_to_send:
            waveform = modulate(b)
            self.stream.write(waveform.astype(np.float32).tobytes())

    # Receive binary data from audio stream
    def receive_bytes(self, bytes_to_receive=1):
        binary_data = []
        for i in range(bytes_to_receive):
            samples = np.frombuffer(self.stream.read(self.fsk.samples_per_bit), dtype=np.float32)
            binary_data.append(demodulate(samples))
            
        return np.array(binary_data, dtype=np.uint8)
    
    def _rx_loop(self):
        while True:
            
            time.sleep(0.1)

            

# Example usage
modem = FSKModem()
modem.send_bytes([1, 0, 1, 1, 0])
received_bytes = modem.receive_bytes(1)
print(received_bytes)
