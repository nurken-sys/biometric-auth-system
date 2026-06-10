import os
import re
import json
import wave
import uuid
import random
import logging
import math
import subprocess
from pathlib import Path
from difflib import SequenceMatcher
from typing import List, Optional, Tuple, Dict, Any

import imageio_ffmpeg

from .models import Phrase

# биометрия кітапханалары
import face_recognition
try:
    from vosk import Model as VoskModel, KaldiRecognizer
except Exception:
    VoskModel = None
    KaldiRecognizer = None

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
TMP_DIR = BASE_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

# фразалармен жұмыс
DEFAULT_FALLBACK_PHRASES = {
    "ru": ["открой дверь", "мой ключ", "доступ открыт"],
    "kz": ["есікті аш", "менің кілтім", "кіруге рұқсат"],
    "en": ["open door", "my key", "access ok"],
}

def get_random_challenge(lang: str) -> str:
    phrases = Phrase.objects.filter(lang=lang, is_active=True).values_list('phrase', flat=True)
    if phrases:
        return random.choice(list(phrases))
    return random.choice(DEFAULT_FALLBACK_PHRASES.get(lang, DEFAULT_FALLBACK_PHRASES["ru"]))


# VOSK Сөзді тану
_VOSK_MODELS: Dict[str, Any] = {}
VOSK_MODEL_PATHS = {
    "ru": MODELS_DIR / "vosk-model-small-ru-0.22",
    "kz": MODELS_DIR / "vosk-model-small-kz-0.15",
    "en": MODELS_DIR / "vosk-model-small-en-us-0.15",
}

def is_valid_vosk_model_dir(p: Path) -> bool:
    if not p.exists() or not p.is_dir(): return False
    return (p / "conf" / "model.conf").exists() or (p / "am" / "final.mdl").exists()

def find_vosk_model_dir(base_path: Path) -> Optional[Path]:
    if is_valid_vosk_model_dir(base_path): return base_path
    if not base_path.exists() or not base_path.is_dir(): return None
    candidates = []
    for d1 in base_path.iterdir():
        if d1.is_dir():
            candidates.append(d1)
            for d2 in d1.iterdir():
                if d2.is_dir():
                    candidates.append(d2)
                    for d3 in d2.iterdir():
                        if d3.is_dir(): candidates.append(d3)
    for c in candidates:
        if is_valid_vosk_model_dir(c): return c
    return None

def get_vosk_model(lang: str):
    if VoskModel is None: raise RuntimeError("vosk не установлен.")
    lang = lang if lang in VOSK_MODEL_PATHS else "ru"
    requested_path = VOSK_MODEL_PATHS[lang]
    real_path = find_vosk_model_dir(requested_path)
    used_lang = lang

    if real_path is None:
        used_lang = "ru"
        real_path = find_vosk_model_dir(VOSK_MODEL_PATHS["ru"])
    if real_path is None: raise RuntimeError("VOSK ru model not found")

    cache_key = f"{used_lang}:{real_path.resolve()}"
    if cache_key not in _VOSK_MODELS:
        _VOSK_MODELS[cache_key] = VoskModel(str(real_path))
    return _VOSK_MODELS[cache_key], used_lang, real_path

def normalize_text(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^0-9a-zA-Zа-яА-ЯәіңғүұқөһӘІҢҒҮҰҚӨҺ\s\-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def convert_wav_to_16k_mono_pcm16(src_path: Path) -> Path:
    """
    Прямая конвертация через встроенный ffmpeg (без ffprobe и pydub).
    Жестко заставляет любой браузерный формат стать 16kHz Mono WAV.
    """
    try:
        out_path = TMP_DIR / f"{uuid.uuid4().hex}_16k.wav"
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        cmd = [
            ffmpeg_exe,
            "-y",                 
            "-i", str(src_path),   
            "-ar", "16000",        
            "-ac", "1",            
            "-c:a", "pcm_s16le",   
            str(out_path)          
        ]

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return out_path
        
    except subprocess.CalledProcessError as e:
        log.error(f"Ошибка ffmpeg: {e}")
        raise RuntimeError("Не удалось перекодировать звук с помощью ffmpeg.")
    except Exception as e:
        log.error(f"Неизвестная ошибка конвертации: {e}")
        raise RuntimeError(f"Системная ошибка аудио: {e}")

def transcribe_with_vosk(wav_path: Path, lang: str) -> Tuple[str, str]:
    model, used_lang, real_path = get_vosk_model(lang)
    fixed_path = convert_wav_to_16k_mono_pcm16(wav_path)
    try:
        with wave.open(str(fixed_path), "rb") as wf:
            rec = KaldiRecognizer(model, wf.getframerate())
            rec.SetWords(False)
            while True:
                data = wf.readframes(4000)
                if len(data) == 0: break
                rec.AcceptWaveform(data)
            try:
                text = json.loads(rec.FinalResult()).get("text", "")
            except Exception:
                text = ""
    finally:
        if fixed_path != wav_path:
            try: fixed_path.unlink(missing_ok=True)
            except Exception: pass
    return normalize_text(text), used_lang

def soft_phrase_score(transcribed: str, expected: str) -> float:
    a, b = normalize_text(transcribed), normalize_text(expected)
    if not a or not b: return 0.0
    return SequenceMatcher(None, a, b).ratio()

# бет Face Recognition
def _l2(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b): return 999.0
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

def compute_face_encoding(face_image_path: Path) -> List[float]:
    img = face_recognition.load_image_file(str(face_image_path))
    locs = face_recognition.face_locations(img, model="hog")
    if not locs: raise RuntimeError("Лицо не найдено на изображении")
    encs = face_recognition.face_encodings(img, known_face_locations=locs)
    if not encs: raise RuntimeError("Не удалось извлечь признаки лица")
    return [float(x) for x in encs[0].tolist()]

def compute_face_id_from_encoding(enc: List[float]) -> str:
    payload = json.dumps([round(x, 6) for x in enc], ensure_ascii=False)
    return uuid.uuid5(uuid.NAMESPACE_OID, payload).hex

# дуысты тану
def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b): return 0.0
    dot = sum(x*y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x*x for x in a)), math.sqrt(sum(y*y for y in b))
    if na == 0.0 or nb == 0.0: return 0.0
    return dot / (na * nb)

def compute_voice_print(wav_path: Path) -> List[float]:
    fixed = convert_wav_to_16k_mono_pcm16(wav_path)
    try:
        try:
            import numpy as np
            import librosa
            y, sr = librosa.load(str(fixed), sr=16000, mono=True)
            m = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            mean, std = m.mean(axis=1), m.std(axis=1)
            return [float(x) for x in np.concatenate([mean, std]).tolist()]
        except Exception as e:
            raise RuntimeError(f"Не могу посчитать voiceprint. Установи librosa. Ошибка: {e}")
    finally:
        if fixed != wav_path:
            try: fixed.unlink(missing_ok=True)
            except Exception: pass