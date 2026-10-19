from langdetect import detect, LangDetectException
import asyncio
import time
import sys
import os
import requests
from config import TRANSLATION_MAX_RETRIES, TRANSLATION_TIMEOUT, DEFAULT_SOURCE_LANG
from utils.logger import log_translation, log_error

# Simple in-memory cache for translations with TTL
translation_cache = {}
CACHE_TTL = 3600  # 1 hour

# Semaphore for concurrent translation requests - increased to 40 for high concurrency
translation_semaphore = asyncio.Semaphore(1)

# Performance tracking
performance_stats = {
    'total_requests': 0,
    'successful_requests': 0,
    'failed_requests': 0,
    'cached_requests': 0,
    'avg_response_time': 0.0
}

SUPPORTED_LANGUAGES = {'en', 'ru', 'tr', 'ko', 'ar', 'uz'}

# Cybersecurity and programming terms to preserve during translation
TECHNICAL_TERMS = {
    'malware', 'ransomware', 'phishing', 'trojan', 'virus', 'worm',
    'firewall', 'antivirus', 'encryption', 'decryption', 'hash',
    'password', 'username', 'login', 'logout', 'authentication',
    'authorization', 'token', 'cookie', 'session', 'cache', 'proxy',
    'vpn', 'ip', 'dns', 'http', 'https', 'ssl', 'tls', 'ssh',
    'ftp', 'sftp', 'api', 'rest', 'json', 'xml', 'html', 'css',
    'javascript', 'python', 'java', 'c++', 'c#', 'ruby', 'php',
    'sql', 'database', 'server', 'client', 'backend', 'frontend',
    'framework', 'library', 'module', 'package', 'function', 'method',
    'class', 'object', 'variable', 'constant', 'array', 'list',
    'dictionary', 'tuple', 'string', 'integer', 'float', 'boolean',
    'loop', 'condition', 'exception', 'error', 'debug', 'compile',
    'runtime', 'syntax', 'algorithm', 'binary', 'hexadecimal',
    'kubernetes', 'docker', 'container', 'virtualization', 'cloud',
    'aws', 'azure', 'gcp', 'linux', 'windows', 'macos', 'ubuntu',
    'debian', 'centos', 'redhat', 'bash', 'shell', 'script',
    'penetration', 'vulnerability', 'exploit', 'payload', 'backdoor',
    'rootkit', 'keylogger', 'spyware', 'adware', 'botnet', 'ddos',
    'brute force', 'social engineering', 'zero day', 'cve', 'owasp'
}

# Slang/dialect words mapping to standard Uzbek
UZBEK_SLANG_MAP = {
    'qandesan': 'qandaysan',
    'qalesan': 'qandaysan',
    'qalaysan': 'qandaysan',
    'qanday': 'qanday',
    'qani': 'qani',
    'nima gap': 'nima gap',
    'salomat': 'salomat',
    'hop': 'ha',
    'xa': 'ha',
    'bopti': 'bo\'ldi',
    'mayli': 'mayli',
    'rahmat': 'rahmat',
    'xayr': 'xayr',
    'ertaga': 'ertaga',
    'kechqurun': 'kechqurun',
    'tong': 'tong',
    'payt': 'payt',
    'zur': 'zo\'r',
    'zor': 'zo\'r',
    'bomba': 'a\'lo',
    'chotki': 'zo\'r',
    'gap yo\'q': 'a\'lo',
}


def _get_cache_key(text: str, target_lang: str) -> str:
    """Generate cache key for translation"""
    return f"{text}:{target_lang}"


def _add_to_cache(cache_key: str, result: str):
    """Add translation result to cache with TTL"""
    global translation_cache
    translation_cache[cache_key] = {
        'result': result,
        'timestamp': time.time()
    }


def normalize_uzbek_text(text: str) -> str:
    """Normalize Uzbek slang/dialect words to standard form for better translation."""
    words = text.lower().split()
    normalized_words = []
    for word in words:
        # Remove punctuation for lookup
        clean_word = word.strip('.,!?;:"()[]{}')
        if clean_word in UZBEK_SLANG_MAP:
            normalized_words.append(UZBEK_SLANG_MAP[clean_word])
        else:
            normalized_words.append(word)
    return ' '.join(normalized_words)


async def detect_language(text: str, user_id: int = None) -> str:
    """Detect source language for incoming text using langdetect (free, no API keys needed).
    
    Special handling for Uzbek to distinguish it from Turkish and other similar languages.
    Includes slang/dialect detection and normalization.
    """
    if not isinstance(text, str):
        text = str(text)

    text = text.strip()
    if not text:
        return DEFAULT_SOURCE_LANG

    # Check for Uzbek-specific patterns before running langdetect
    # Uzbek text often contains specific word patterns and Cyrillic variants.
    uzbek_indicators = [
        "bo'lib", "qilish", "iltimos", "xo'jalik", "o'rganish",
        "salom", "qanday", "nimada", "qayer", "nima", "kim",
        "men", "siz", "bu", "u", "yaxshi", "qayerda", "qachon",
        "har", "o'zbek", "uzbek", "qandaydir", "qanchalik",
        # Slang/dialect additions
        "qandesan", "qalesan", "qalaysan", "nima gap", "bopti",
        "hop", "xa", "mayli", "zur", "zor", "bomba", "chotki",
        "gap yo'q", "kechqurun", "tong", "payt"
    ]
    uzbek_cyrillic_chars = set('ғқҳўӣ')
    text_lower = text.lower()

    if any(indicator in text_lower for indicator in uzbek_indicators):
        return DEFAULT_SOURCE_LANG

    if any(ch in text for ch in uzbek_cyrillic_chars):
        return DEFAULT_SOURCE_LANG

    try:
        # Use asyncio.to_thread for Python 3.9+ or fallback to run_in_executor
        if sys.version_info >= (3, 9):
            detected = await asyncio.wait_for(
                asyncio.to_thread(detect, text),
                timeout=TRANSLATION_TIMEOUT
            )
        else:
            loop = asyncio.get_event_loop()
            detected = await asyncio.wait_for(
                loop.run_in_executor(None, detect, text),
                timeout=TRANSLATION_TIMEOUT
            )
        if isinstance(detected, str) and detected:
            detected_lang = detected.lower()
            # Normalize language codes (e.g., 'zh-cn' -> 'zh')
            if '-' in detected_lang:
                detected_lang = detected_lang.split('-')[0]

            # If Uzbek markers appear in a Turkish/Azeri detection, treat it as Uzbek.
            if detected_lang in {'tr', 'az', 'ru', 'en'}:
                uzbek_markers = ["o'", "g'", "sh", "ch", "q", "yo", "yu", "ya", "ng"]
                if any(marker in text_lower for marker in uzbek_markers):
                    return DEFAULT_SOURCE_LANG

            # If Turkish appears but Uzbek indicators exist, preserve Turkish only if no Uzbek signs exist.
            return detected_lang
    except asyncio.TimeoutError:
        log_error("Language detection timeout", user_id)
    except LangDetectException as e:
        log_error(f"Language detection failed: {e}", user_id)
    except Exception as e:
        log_error(f"Language detection error: {e}", user_id)

    return DEFAULT_SOURCE_LANG


def _preserve_technical_terms(text: str) -> tuple[str, dict]:
    """
    Preserve technical terms by replacing them with placeholders before translation.
    Returns modified text and mapping of placeholders to original terms.
    """
    import re
    
    text_lower = text.lower()
    term_map = {}
    placeholder_count = 0
    modified_text = text
    
    # Find and replace technical terms with placeholders
    for term in TECHNICAL_TERMS:
        # Match whole words only (case insensitive)
        pattern = r'\b' + re.escape(term) + r'\b'
        matches = list(re.finditer(pattern, text_lower))
        
        for match in matches:
            original_start = match.start()
            original_end = match.end()
            original_term = text[original_start:original_end]
            
            placeholder = f"__TERM_{placeholder_count}__"
            term_map[placeholder] = original_term
            placeholder_count += 1
            
            # Replace in modified text (preserve case in original text)
            modified_text = modified_text[:original_start] + placeholder + modified_text[original_end:]
            text_lower = modified_text.lower()
    
    return modified_text, term_map


def _restore_technical_terms(text: str, term_map: dict) -> str:
    """Restore technical terms from placeholders after translation."""
    for placeholder, original_term in term_map.items():
        text = text.replace(placeholder, original_term)
    return text


HF_MODEL_ID = "facebook/nllb-200-distilled-600M"
HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{HF_MODEL_ID}"
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()

# NLLB-200 language tags. Uzbek is uzn_Latn (not the short code "uz").
NLLB_LANG_CODES = {
    "uz": "uzn_Latn", "uzn": "uzn_Latn",
    "en": "eng_Latn", "ru": "rus_Cyrl", "tr": "tur_Latn",
    "ar": "arb_Arab", "ko": "kor_Hang",
}


def _hf_nllb_request(text: str, source_code: str, target_code: str) -> str:
    """Call Hugging Face's hosted inference router. Requires HF_TOKEN."""
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN Render Environment variable sozlanmagan")
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "inputs": text,
        "parameters": {
            "src_lang": source_code,
            "tgt_lang": target_code,
            "max_new_tokens": 512,
        },
        "options": {"wait_for_model": True},
    }
    response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=90)
    if response.status_code >= 400:
        # Don't log or expose the secret token.
        raise RuntimeError(f"Hugging Face API HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    if isinstance(data, list) and data:
        item = data[0]
        if isinstance(item, dict):
            result = item.get("translation_text") or item.get("generated_text")
            if result:
                return str(result).strip()
    if isinstance(data, dict):
        result = data.get("translation_text") or data.get("generated_text")
        if result:
            return str(result).strip()
        if data.get("error"):
            raise RuntimeError(str(data["error"]))
    raise RuntimeError(f"Unexpected Hugging Face response: {str(data)[:250]}")


async def translate_text(text: str, target_lang: str, user_id: int = None, source_lang: str = None) -> tuple[str, str] | None:
    """Translate with NLLB-200 via Hugging Face Inference API.

    If selected target is Uzbek, translate foreign text to Uzbek.
    Otherwise translate Uzbek to the selected language.
    Returns (translated_text, actual_target_short_code).
    """
    if not isinstance(text, str):
        text = str(text)
    text = text.strip()
    if not text or target_lang not in SUPPORTED_LANGUAGES:
        return None

    detected = (source_lang or await detect_language(text, user_id) or DEFAULT_SOURCE_LANG).lower()
    if detected not in NLLB_LANG_CODES:
        # langdetect can guess unsupported languages; bot's common workflow assumes Uzbek source.
        detected = DEFAULT_SOURCE_LANG

    if target_lang == DEFAULT_SOURCE_LANG:
        if detected == DEFAULT_SOURCE_LANG:
            # If detector is uncertain, still allow an attempt only when text isn't obviously Uzbek.
            return None
        destination = DEFAULT_SOURCE_LANG
    else:
        destination = target_lang if detected == DEFAULT_SOURCE_LANG else DEFAULT_SOURCE_LANG

    src_code = NLLB_LANG_CODES.get(detected)
    tgt_code = NLLB_LANG_CODES.get(destination)
    if not src_code or not tgt_code:
        raise RuntimeError(f"NLLB language mapping missing: {detected}->{destination}")
    if src_code == tgt_code:
        return None

    key = _get_cache_key(text, destination)
    cached = translation_cache.get(key)
    if cached and time.time() - cached.get("timestamp", 0) < CACHE_TTL:
        performance_stats["cached_requests"] += 1
        return cached["result"], destination

    start = time.time()
    async with translation_semaphore:
        # Keep concurrency low to avoid exhausting free inference quota.
        result = await asyncio.wait_for(
            asyncio.to_thread(_hf_nllb_request, text, src_code, tgt_code),
            timeout=TRANSLATION_TIMEOUT + 15,
        )

    if not result:
        raise RuntimeError("Hugging Face returned an empty translation")
    _add_to_cache(key, result)
    performance_stats["total_requests"] += 1
    performance_stats["successful_requests"] += 1
    duration = time.time() - start
    prev = performance_stats["avg_response_time"]
    successes = performance_stats["successful_requests"]
    performance_stats["avg_response_time"] = (prev * (successes - 1) + duration) / successes
    log_translation(user_id or 0, detected, destination, True, duration=duration, cached=False)
    return result, destination
