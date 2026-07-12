import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Try importing SpeechRecognition
try:
    import speech_recognition as sr
except ImportError:
    sr = None
    logging.warning("SpeechRecognition is not installed. Voice input is disabled.")


class SpeechToText:
    def __init__(self):
        self.recognizer = None
        self.microphone = None

        # If SpeechRecognition isn't installed (e.g. Railway)
        if sr is None:
            return

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
        if self.microphone is None:
            return

        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=2)

    def listen(self):
        if sr is None:
            logging.warning("SpeechRecognition is unavailable.")
            return None

        if self.microphone is None:
            logging.warning("No microphone available.")
            return None

        try:
            with self.microphone as source:
                logging.info("Listening...")
                audio = self.recognizer.listen(source)

            text = self.recognizer.recognize_google(
                audio,
                language="en-US"
            )
            return text.strip().lower()

        except sr.UnknownValueError:
            return None

        except sr.RequestError as e:
            logging.error(f"SpeechRecognition service error: {e}")
            return None

        except Exception as e:
            logging.error(f"Speech recognition error: {e}")
            return None


# Create singleton
stt = SpeechToText()


def listen():
    """
    Returns recognized text or None if speech input
    is unavailable.
    """
    return stt.listen()