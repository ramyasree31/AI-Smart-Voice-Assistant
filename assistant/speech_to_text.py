import speech_recognition as sr
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

class SpeechToText:
    def __init__(self):
        self.recognizer = sr.Recognizer()

        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.5
        self.recognizer.non_speaking_duration = 0.8

        try:
            self.microphone = sr.Microphone()
            self._calibrate()
            logging.info("Microphone initialized.")
        except Exception as e:
            logging.warning(f"Microphone unavailable: {e}")
            self.microphone = None

    def _calibrate(self):
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=2)

    def listen(self):
        if self.microphone is None:
            logging.warning("No microphone available.")
            return None

        try:
            with self.microphone as source:
                logging.info("Listening...")
                audio = self.recognizer.listen(source)

            text = self.recognizer.recognize_google(audio, language="en-US")
            return text.strip().lower()

        except sr.UnknownValueError:
            return None

        except sr.RequestError as e:
            logging.error(e)
            return None

        except Exception as e:
            logging.error(e)
            return None


stt = SpeechToText()

def listen():
    return stt.listen()