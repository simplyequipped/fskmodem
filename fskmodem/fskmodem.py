
import pyaudio
import numpy as np

# Setup audio parameters
BIT_RATE = 44100
FREQ_HIGH = 1200
FREQ_LOW = 800
BIT_DURATION = 0.1

# Create audio stream
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paFloat32, channels=1, rate=BIT_RATE, output=True)

# Modulate binary data into audio frequency shifts
def modulate(b):
    freq = FREQ_HIGH if b == 1 else FREQ_LOW
    samples = int(BIT_RATE * BIT_DURATION)
    t = np.linspace(0, BIT_DURATION, samples, endpoint=False)
    waveform = np.sin(2 * np.pi * freq * t)
    return waveform


# Demodulate audio frequency shifts into binary data
def demodulate(samples):
    spectrum = np.fft.fft(samples)
    freqs = np.fft.fftfreq(samples.size, d=1 / BIT_RATE)
    pos_amplitude = np.abs(spectrum[freqs > 0])
    neg_amplitude = np.abs(spectrum[freqs < 0])
    high_amp = np.mean(pos_amplitude[freqs[freqs > 0] > FREQ_HIGH])
    low_amp = np.mean(pos_amplitude[freqs[freqs > 0] > FREQ_LOW])
    return high_amp > low_amp


# Send binary data over audio stream
def send_bytes(bytes_to_send):
    for b in bytes_to_send:
        waveform = modulate(b)
        stream.write(waveform.astype(np.float32).tobytes())

# Receive binary data from audio stream
def receive_bytes(bytes_to_receive):
    binary_data = []
    samples_per_bit = int(BIT_RATE * BIT_DURATION)
    for i in range(bytes_to_receive):
        samples = np.frombuffer(stream.read(samples_per_bit), dtype=np.float32)
        binary_data.append(demodulate(samples))
    return np.array(binary_data, dtype=np.uint8)


# Example usage
send_bytes([1, 0, 1, 1, 0])
received_bytes = receive_bytes(5)
print(received_bytes)
