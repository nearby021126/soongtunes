from flask import jsonify

import pyaudio
import numpy as np
from google.cloud import speech
from google.oauth2 import service_account 
import queue

RATE = 16000 
CHUNK = int(RATE / 10) 

CREDENTIALS = service_account.Credentials.from_service_account_file('api_key.json')

class MicrophoneStream:
    def __init__(self, rate, chunk):
        self.rate = rate
        self.chunk = chunk
        self.buffer = queue.Queue()
        self.closed = True

        self.is_speaking = False
        self.silence_threshold = 5  
        self.silence_chunks = 0
        self.max_silence_chunks = 30  

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        audio_data = np.frombuffer(in_data, dtype=np.int16)
        rms = np.sqrt(np.mean(audio_data**2)) if np.mean(audio_data**2) > 0 else 0 
        print(rms)

        if rms > self.silence_threshold:
            self.is_speaking = True
        else:
            self.is_speaking = False

        if self.is_speaking:
            self.silence_chunks = 0
        else: 
            self.silence_chunks += 1 

        if self.silence_chunks >= self.max_silence_chunks:
            self.buffer.put(None)  
            return None, pyaudio.paComplete
        self.buffer.put(in_data)
        return None, pyaudio.paContinue

    def __enter__(self):
        self.audio_interface = pyaudio.PyAudio()
        self.audio_stream = self.audio_interface.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk,
            stream_callback=self._fill_buffer,
        )
        self.closed = False
        return self

    def __exit__(self, type, value, traceback):
        self.audio_stream.stop_stream()
        self.audio_stream.close()
        self.closed = True
        self.buffer.put(None)
        self.audio_interface.terminate()

    def generator(self):
        while not self.closed:
            chunk = self.buffer.get()
            if chunk is None:
                return
            yield chunk

def listen_print_loop(responses):
    for response in responses:
        if not response.results:
            continue

        result = response.results[0]
        if not result.alternatives:
            continue

        transcript = result.alternatives[0].transcript
        print(f"Transcription: {transcript}")

        if result.is_final:
            print(f"Final: {transcript}\n")
            return transcript


def recognize_audio():
    language_code = "ko-KR"
    client = speech.SpeechClient(credentials=CREDENTIALS)

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=language_code,
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=True,
    )

    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (speech.StreamingRecognizeRequest(audio_content=content) for content in audio_generator)

        responses = client.streaming_recognize(streaming_config, requests)
        text = listen_print_loop(responses)
        return text
    