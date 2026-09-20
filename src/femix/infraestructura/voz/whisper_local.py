import os
from faster_whisper import WhisperModel
from ...puertos.voz import MotorVoz

RUTA_MODELO = os.path.expanduser("~/.cache/whisper-base")

class MotorWhisperLocal(MotorVoz):
    def __init__(self):
        origen = RUTA_MODELO if os.path.exists(RUTA_MODELO) else "base"
        self._modelo = WhisperModel(origen, device="cpu", compute_type="int8")

    def transcribir(self, ruta_audio: str) -> str:
        segmentos, _ = self._modelo.transcribe(ruta_audio, language="es")
        return " ".join(segmento.text for segmento in segmentos).strip()
