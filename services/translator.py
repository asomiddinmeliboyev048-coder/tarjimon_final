from deep_translator import GoogleTranslator
from deep_translator.exceptions import TranslationNotFound, RequestError, LanguageNotSupportedException
from langdetect import detect, LangDetectException
import asyncio
import time
import sys
from config import TRANSLATION_MAX_RETRIES, TRANSLATION_TIMEOUT, DEFAULT_SOURCE_LANG
from utils.logger import log_translation, log_error

# Simple in-memory cache for translations with TTL
translation_cache = {}
CACHE_TTL = 3600  # 1 hour

# Semaphore for concurrent translation requests - increased to 40 for high concurrency
translation_semaphore = asyncio.Semaphore(40)

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


async def translate_text(text: str, target_lang: str, user_id: int = None) -> tuple[str, str] | None:
    """
    Translate text using automatic source language detection with optimizations.

    If the incoming text is Uzbek, it is translated into the user's selected foreign language.
    If the incoming text is non-Uzbek, it is translated into Uzbek.
    
    Features:
    - Slang/dialect normalization for Uzbek
    - Technical term preservation
    - Async translation with asyncio.to_thread
    - Comprehensive error handling
    - Performance monitoring

    Args:
        text: Text to translate
        target_lang: User-selected foreign language code
        user_id: Optional user ID for logging

    Returns:
        Tuple of (translated_text, actual_target_lang) or None if translation failed
    """
    global performance_stats
    start_time = time.time()
    
    # Update total requests counter
    performance_stats['total_requests'] += 1
    
    async with translation_semaphore:
        if not isinstance(text, str):
            text = str(text)

        text = text.strip()
        if not text:
            return None

        if target_lang not in SUPPORTED_LANGUAGES:
            log_error(f"Unsupported target language: {target_lang}", user_id)
            return None

        # Normalize Uzbek slang before translation
        source_lang = await detect_language(text, user_id)
        if source_lang == DEFAULT_SOURCE_LANG:
            text = normalize_uzbek_text(text)

        if target_lang == DEFAULT_SOURCE_LANG:
            if source_lang == DEFAULT_SOURCE_LANG:
                log_error("Selected Uzbek while input is Uzbek: no translation needed", user_id)
                return None
            destination_lang = DEFAULT_SOURCE_LANG
        else:
            destination_lang = target_lang if source_lang == DEFAULT_SOURCE_LANG else DEFAULT_SOURCE_LANG

        # Preserve technical terms before translation
        modified_text, term_map = _preserve_technical_terms(text)

        cache_key = _get_cache_key(modified_text, destination_lang)
        if cache_key in translation_cache:
            cache_entry = translation_cache[cache_key]
            if time.time() - cache_entry['timestamp'] < CACHE_TTL:
                translated_text = cache_entry['result']
                # Restore technical terms
                translated_text = _restore_technical_terms(translated_text, term_map)
                duration = time.time() - start_time
                # Update performance stats for cached request
                performance_stats['cached_requests'] += 1
                performance_stats['successful_requests'] += 1
                # Update average response time
                prev_avg = performance_stats['avg_response_time']
                total_success = performance_stats['successful_requests']
                performance_stats['avg_response_time'] = (prev_avg * (total_success - 1) + duration) / total_success
                log_translation(user_id or 0, source_lang, destination_lang, True, duration=duration, cached=True)
                return translated_text, destination_lang
            else:
                del translation_cache[cache_key]

        last_error = None
        for attempt in range(TRANSLATION_MAX_RETRIES):
            try:
                # Use auto source detection in the translator to avoid echo when our heuristic misclassifies the language.
                translator = GoogleTranslator(source='auto', target=destination_lang)
                
                # Use asyncio.to_thread for Python 3.9+ (better performance) or fallback to run_in_executor
                if sys.version_info >= (3, 9):
                    result = await asyncio.wait_for(
                        asyncio.to_thread(translator.translate, modified_text),
                        timeout=TRANSLATION_TIMEOUT
                    )
                else:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, translator.translate, modified_text),
                        timeout=TRANSLATION_TIMEOUT
                    )

                if result and isinstance(result, str) and result.strip():
                    translated_text = result.strip()
                    # Restore technical terms
                    translated_text = _restore_technical_terms(translated_text, term_map)
                    _add_to_cache(cache_key, translated_text)
                    duration = time.time() - start_time
                    # Update performance stats for successful request
                    performance_stats['successful_requests'] += 1
                    # Update average response time
                    prev_avg = performance_stats['avg_response_time']
                    total_success = performance_stats['successful_requests']
                    performance_stats['avg_response_time'] = (prev_avg * (total_success - 1) + duration) / total_success
                    log_translation(user_id or 0, source_lang, destination_lang, True, duration=duration, cached=False)
                    return translated_text, destination_lang

            except asyncio.TimeoutError:
                last_error = f"Timeout on attempt {attempt + 1}"
                log_error(f"Translation timeout (attempt {attempt + 1})", user_id)

            except TranslationNotFound:
                last_error = "Tarjima topilmadi"
                log_error("Translation not found", user_id)
                return None

            except (RequestError, LanguageNotSupportedException) as e:
                last_error = f"API xatosi: {e}"
                log_error(f"Translation API error: {e}", user_id)

            except Exception as e:
                last_error = f"Kutilmagan xato: {e}"
                log_error(f"Translation unexpected error: {e}", user_id)

            if attempt < TRANSLATION_MAX_RETRIES - 1:
                wait_time = min(2 ** attempt, 8)
                await asyncio.sleep(wait_time)

        duration = time.time() - start_time
        # Update performance stats for failed request
        performance_stats['failed_requests'] += 1
        log_error(f"Translation failed after {TRANSLATION_MAX_RETRIES} attempts: {last_error}", user_id)
        log_translation(user_id or 0, source_lang, destination_lang, False, duration=duration)
        return None


def clear_translation_cache():
    """Clear the translation cache"""
    global translation_cache
    translation_cache = {}


def get_cache_stats():
    """Get cache statistics"""
    current_time = time.time()
    valid_entries = sum(1 for entry in translation_cache.values() if current_time - entry['timestamp'] < CACHE_TTL)
    return {
        "size": len(translation_cache),
        "valid_entries": valid_entries,
        "ttl_seconds": CACHE_TTL
    }


def get_performance_stats():
    """Get performance statistics for monitoring"""
    total = performance_stats['total_requests']
    success = performance_stats['successful_requests']
    failed = performance_stats['failed_requests']
    cached = performance_stats['cached_requests']
    
    success_rate = (success / total * 100) if total > 0 else 0
    cache_hit_rate = (cached / total * 100) if total > 0 else 0
    
    return {
        "total_requests": total,
        "successful_requests": success,
        "failed_requests": failed,
        "cached_requests": cached,
        "success_rate_percent": round(success_rate, 2),
        "cache_hit_rate_percent": round(cache_hit_rate, 2),
        "avg_response_time_seconds": round(performance_stats['avg_response_time'], 3),
        "concurrent_limit": 40,
        "current_concurrent": 40 - translation_semaphore._value if hasattr(translation_semaphore, '_value') else 'N/A'
    }