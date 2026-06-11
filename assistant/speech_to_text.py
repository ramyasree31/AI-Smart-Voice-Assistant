import speech_recognition as sr
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class SpeechToText:
    def __init__(self):
        self.recognizer = sr.Recognizer()

        # 🔥 STABLE SETTINGS
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.5
        self.recognizer.non_speaking_duration = 0.8

        self.microphone = sr.Microphone()

        self._calibrate()

    def _calibrate(self):
        logging.info("Calibrating microphone...")

        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=2)

        logging.info("Microphone ready")

    def listen(self):
        try:
            with self.microphone as source:

                logging.info("🎤 Listening...")

                audio = self.recognizer.listen(
                    source,
                    timeout=None,
                    phrase_time_limit=None
                )

            logging.info("Recognizing...")

            text = self.recognizer.recognize_google(
                audio,
                language="en-US"
            )

            text = text.strip()

            if not text:
                return None

            logging.info(f"Recognized: {text}")

            return text.lower()

        except sr.UnknownValueError:
            return None

        except sr.RequestError as e:
            logging.error(f"Speech service error: {e}")
            return None

        except Exception as e:
            logging.error(f"Speech error: {e}")
            return None


# Singleton
stt = SpeechToText()


def listen():
    return stt.listen()