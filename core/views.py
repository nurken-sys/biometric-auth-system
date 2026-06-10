import os
import json
import uuid
import shutil
import logging
from pathlib import Path

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt

from .models import User
from .services import (
    compute_face_encoding, compute_face_id_from_encoding,
    compute_voice_print, transcribe_with_vosk, soft_phrase_score,
    get_random_challenge, _l2, _cosine, TMP_DIR
)

log = logging.getLogger(__name__)

# ======================
# Аудармалар
# ======================
TRANSLATIONS = {
    "ru": {
        "title": "BiometricAuth", "pick_lang_hint": "Выберите язык", "welcome": "Добро пожаловать",
        "welcome_message": "Вход по лицу + проверка голоса (voiceprint). Текст VOSK — только для отображения.",
        "btn_home": "Главная", "btn_login": "Вход", "btn_register": "Регистрация", "btn_auto": "Авто",
        "label_name": "Имя пользователя", "ph_enter_username": "Введите имя пользователя",
        "camera_mic": "камера", "biometric_login": "Биометрический вход", "biometric_registration": "Биометрическая регистрация",
        "hint_enter_username_login": "Введите имя пользователя, затем нажмите Авто",
        "registration_info": "Информация о регистрации", "registration_face_info": "Лицо будет использовано для входа",
        "registration_voice_info": "Голос используется для проверки личности",
        "registration_security_info": "Данные сохраняются локально", "registration_name_hint": "Выберите уникальное имя",
        "registration_face_hint": "Смотрите в камеру", "registration_phrases": "Произнесите фразу",
        "retry": "Повторить", "back": "Назад", "face_status": "Лицо", "voice_status": "Голос",
        "phrase_status": "Фраза", "face_guide_hint": "Смотрите в камеру",
        "success_title": "Успешная аутентификация!", "welcome_back": "Добро пожаловать",
        "auth_success_message": "Вы успешно прошли биометрическую аутентификацию.",
        "face_match": "Сходство лица", "voice_match": "Сходство голоса",
        "auth_info": "Ваши биометрические данные успешно проверены.",
        "go_to_dashboard": "Перейти в кабинет", "logout": "Выход",
        "security_notice": "Сессия будет автоматически закрыта через 24 часа.",
        "redirect_countdown": "Автоматическое перенаправление через", "seconds": "секунд"
    },
    "kz": {
        "title": "BiometricAuth", "pick_lang_hint": "Тілді таңдаңыз", "welcome": "Қош келдіңіз",
        "welcome_message": "Бет арқылы кіру + дауыс (voiceprint) сәйкестігі. VOSK мәтіні — тек көрсету үшін.",
        "btn_home": "Басты бет", "btn_login": "Кіру", "btn_register": "Тіркелу", "btn_auto": "Авто",
        "label_name": "Пайдаланушы аты", "ph_enter_username": "Атыңызды енгізіңіз",
        "camera_mic": "камера", "biometric_login": "Биометриялық кіру", "biometric_registration": "Биометриялық тіркелу",
        "hint_enter_username_login": "Атыңызды енгізіп, Авто басыңыз",
        "registration_info": "Тіркелу туралы", "registration_face_info": "Бетіңіз кіру үшін қолданылады",
        "registration_voice_info": "Дауыс — voiceprint сәйкестігі үшін",
        "registration_security_info": "Деректер жергілікті сақталады", "registration_name_hint": "Бірегей атты таңдаңыз",
        "registration_face_hint": "Камераға қараңыз", "registration_phrases": "Фразаны айтыңыз",
        "retry": "Қайтадан", "back": "Артқа", "face_status": "Бет", "voice_status": "Дауыс",
        "phrase_status": "Фраза", "face_guide_hint": "Камераға қараңыз",
        "success_title": "Сәтті аутентификация!", "welcome_back": "Қош келдіңіз",
        "auth_success_message": "Сіз биометриялық аутентификациядан сәтті өттіңіз.",
        "face_match": "Бет ұқсастығы", "voice_match": "Дауыс ұқсастығы",
        "auth_info": "Сіздің биометриялық деректеріңіз расталды.",
        "go_to_dashboard": "Кабинетке өту", "logout": "Шығу",
        "security_notice": "Сессия 24 сағаттан кейін жабылады.",
        "redirect_countdown": "Автоматты түрде бағыттау", "seconds": "секундтан кейін"
    },
    "en": {
        "title": "BiometricAuth", "pick_lang_hint": "Pick language", "welcome": "Welcome",
        "welcome_message": "Face login + voiceprint match. VOSK text is only for display.",
        "btn_home": "Home", "btn_login": "Login", "btn_register": "Register", "btn_auto": "Auto",
        "label_name": "Username", "ph_enter_username": "Enter username",
        "camera_mic": "camera", "biometric_login": "Biometric login", "biometric_registration": "Biometric registration",
        "hint_enter_username_login": "Enter username and press Auto",
        "registration_info": "Registration info", "registration_face_info": "Face is used for login",
        "registration_voice_info": "Voice is used as voiceprint match",
        "registration_security_info": "Data stored locally", "registration_name_hint": "Choose unique username",
        "registration_face_hint": "Look at the camera", "registration_phrases": "Say the phrase",
        "retry": "Retry", "back": "Back", "face_status": "Face", "voice_status": "Voice",
        "phrase_status": "Phrase", "face_guide_hint": "Look at the camera",
        "success_title": "Authentication Successful!", "welcome_back": "Welcome back",
        "auth_success_message": "You have successfully passed biometric authentication.",
        "face_match": "Face similarity", "voice_match": "Voice similarity",
        "auth_info": "Your biometric data has been successfully verified.",
        "go_to_dashboard": "Go to Dashboard", "logout": "Logout",
        "security_notice": "Session will be automatically closed in 24 hours.",
        "redirect_countdown": "Automatic redirect in", "seconds": "seconds"
    }
}

def get_current_language(request):
    lang = request.session.get("lang", "ru")
    return lang if lang in ("ru", "kz", "en") else "ru"

def render_ctx(request, template, context=None):
    if context is None: context = {}
    lang = get_current_language(request)
    context['lang'] = lang
    context['t'] = TRANSLATIONS.get(lang, TRANSLATIONS["ru"])
    context['csrf_token'] = get_token(request)
    return render(request, template, context)

def save_tmp_upload(uploaded_file, filename):
    path = TMP_DIR / filename
    with open(path, 'wb+') as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)
    return path

def move_tmp_to_media(tmp_path, filename):
    dest_path = Path(settings.MEDIA_ROOT) / filename
    shutil.move(str(tmp_path), str(dest_path))
    return dest_path


# БАҒЫТТАР (БЕТТЕР)

def index(request):
    return render_ctx(request, "index.html")

def set_language(request, lang):
    if lang not in ("ru", "kz", "en"): lang = "ru"
    request.session["lang"] = lang
    next_url = request.GET.get("next", "index")
    return redirect(next_url if next_url in ['index', 'login', 'register', 'dashboard'] else 'index')

@csrf_exempt
def register_view(request):
    if request.method == "GET":
        return render_ctx(request, "register.html", {"prep": 1, "rec": 3})

    username = request.POST.get("username", "").strip()
    face_file = request.FILES.get("face_image")
    voice_file = request.FILES.get("voice_recording")

    if not username or not face_file or not voice_file:
        return JsonResponse({"success": False, "error": "Missing data"}, status=400)

    if User.objects.filter(username=username).exists():
        return JsonResponse({"success": False, "error": f"Никнейм '{username}' уже занят."}, status=409)

    uid = uuid.uuid4().hex
    tmp_face_path = save_tmp_upload(face_file, f"tmp_reg_{uid}_face.jpg")
    tmp_voice_path = save_tmp_upload(voice_file, f"tmp_reg_{uid}_voice.wav")

    try:
        enc = compute_face_encoding(tmp_face_path)
        face_id = compute_face_id_from_encoding(enc)
        vp = compute_voice_print(tmp_voice_path)

        for user in User.objects.filter(is_active=True).exclude(face_encoding__isnull=True):
            try:
                if _l2(enc, json.loads(user.face_encoding)) < 0.55:
                    return JsonResponse({
                        "success": False, 
                        "error": "Вы уже зарегистрированы в системе. Если вы забыли никнейм, обратитесь к администратору для восстановления."
                    }, status=409)
            except Exception: pass

        final_face_path = move_tmp_to_media(tmp_face_path, f"{username}_{uid}_face.jpg")
        final_voice_path = move_tmp_to_media(tmp_voice_path, f"{username}_{uid}_voice.wav")

        User.objects.update_or_create(
            username=username,
            defaults={
                "face_path": str(final_face_path.name), 
                "voice_path": str(final_voice_path.name),
                "face_id": face_id, 
                "voice_print": json.dumps(vp),
                "face_encoding": json.dumps(enc), 
                "is_active": True
            }
        )
        return JsonResponse({"success": True, "redirect": "/login/"})
        
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    finally:
        try: tmp_face_path.unlink(missing_ok=True)
        except: pass
        try: tmp_voice_path.unlink(missing_ok=True)
        except: pass


@csrf_exempt
def login_view(request):
    if request.method == "GET":
        return render_ctx(request, "login.html", {"prep": 1, "rec": 3})

    username = request.POST.get("username", "").strip()
    user = User.objects.filter(username=username, is_active=True).first()
    if not user: 
        return JsonResponse({"success": False, "error": f"Ошибка: Пользователь с никнеймом '{username}' не найден в базе."}, status=404)

    tmp_face = save_tmp_upload(request.FILES.get("face_image"), f"{uuid.uuid4().hex}_login_face.jpg")
    tmp_voice = save_tmp_upload(request.FILES.get("voice_recording"), f"{uuid.uuid4().hex}_login_voice.wav")

    try:
        incoming_enc = compute_face_encoding(tmp_face)
        saved_enc = json.loads(user.face_encoding) if user.face_encoding else []
        if _l2(incoming_enc, saved_enc) > 0.60:
            return JsonResponse({"success": False, "error": "Ошибка: Лицо не совпало"}, status=401)

        sim = _cosine(compute_voice_print(tmp_voice), json.loads(user.voice_print) if user.voice_print else [])
        if sim < 0.75:
            return JsonResponse({"success": False, "error": "Ошибка: Голос не совпал. Пожалуйста, подойдите ближе к микрофону и говорите четко."}, status=401)

        request.session["user"] = username
        return JsonResponse({"success": True, "redirect": "/dashboard/"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    finally:
        try: tmp_face.unlink(missing_ok=True)
        except: pass
        try: tmp_voice.unlink(missing_ok=True)
        except: pass

def dashboard_view(request):
    user = request.session.get("user")
    if not user: return redirect("login")
    lang = get_current_language(request)
    template_name = f"dashboard_{lang}.html"
    return render_ctx(request, template_name, {"user": user})

def logout_view(request):
    current_lang = request.session.get("lang", "ru")
    request.session.flush()
    request.session["lang"] = current_lang
    return redirect("index")

#  API Бағыты

def api_challenge(request):
    lang = get_current_language(request)
    ch = get_random_challenge(lang)
    request.session["challenge"] = ch
    return JsonResponse({"challenge": ch, "lang": lang})

def api_register_phrases(request):
    lang = get_current_language(request)
    phrase = get_random_challenge(lang)
    request.session["reg_phrase"] = phrase
    return JsonResponse({"phrases": [phrase], "lang": lang})

@csrf_exempt
def preview_asr(request):
    lang = get_current_language(request)
    reg_phrase = request.session.get("reg_phrase") or get_random_challenge(lang)
    tmp_path = save_tmp_upload(request.FILES.get("audio"), f"tmp_asr_{uuid.uuid4().hex}.wav")
    text, used_lang = transcribe_with_vosk(tmp_path, lang)
    score = soft_phrase_score(text, reg_phrase)
    try: tmp_path.unlink(missing_ok=True)
    except: pass
    return JsonResponse({"text": text, "expected": reg_phrase, "score": score, "reg_match": score >= 0.80, "lang_request": lang, "lang_used": used_lang})

@csrf_exempt
def verify_audio(request):
    username = request.POST.get("username", request.session.get("user", ""))
    lang = get_current_language(request)
    expected = request.session.get("challenge") or get_random_challenge(lang)
    tmp_path = save_tmp_upload(request.FILES.get("audio"), f"tmp_vrfy_{uuid.uuid4().hex}.wav")
    text, used_lang = transcribe_with_vosk(tmp_path, lang)
    phrase_score = soft_phrase_score(text, expected)
    incoming_vp = compute_voice_print(tmp_path)
    user = User.objects.filter(username=username, is_active=True).first()
    sim = _cosine(incoming_vp, json.loads(user.voice_print)) if user and user.voice_print else 0.0
    try: tmp_path.unlink(missing_ok=True)
    except: pass
    return JsonResponse({"text": text, "expected": expected, "phrase_score": phrase_score, "phrase_ok": phrase_score >= 0.80, "voice_score": sim, "voice_ok": sim >= 0.75, "lang_request": lang, "lang_used": used_lang})

from .models import RecoveryRequest 

@csrf_exempt
def recovery_view(request):
    if request.method == "GET":
        return render_ctx(request, "recovery.html")

    reason = request.POST.get("reason", "other")
    description = request.POST.get("description", "")
    face_file = request.FILES.get("face_image")

    if not face_file:
        return JsonResponse({"success": False, "error": "Необходимо сделать фото лица для идентификации."}, status=400)

    try:
        new_request = RecoveryRequest.objects.create(
            face_photo=face_file,
            reason=reason,
            description=description
        )
        return JsonResponse({"success": True, "request_id": new_request.id})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    
def check_recovery_status(request, req_id):
    try:
        req = RecoveryRequest.objects.get(id=req_id)
        return JsonResponse({
            'status': req.status,
            'message': req.admin_response_username if req.admin_response_username else '-'
        })
    except RecoveryRequest.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)