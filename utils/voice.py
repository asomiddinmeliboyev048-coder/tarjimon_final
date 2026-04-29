import os
import hashlib
import edge_tts
import asyncio
import time
from gtts import gTTS
from config import VOICE_MAP, GTTS_SUPPORTED_LANGS, MAX_TTS_TEXT_LENGTH
from utils.logger import log_voice_generation, log_error

VOICE_CACHE_DIR = "cache/voices"
os.makedirs(VOICE_CACHE_DIR, exist_ok=True)

# TTS timeout settings (increased for long texts)
EDGE_TTS_TIMEOUT = 60  # seconds (increased from default)
GTTS_TIMEOUT = 30      # seconds

voice_semaphore = asyncio.Semaphore(10)


def _ensure_cache_dir() -> None:
    os.makedirs(VOICE_CACHE_DIR, exist_ok=True)


def _get_voice_file_path(lang: str, text_hash: str) -> str:
    return os.path.join(VOICE_CACHE_DIR, f"{lang}_{text_hash}.mp3")


def _hash_text(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


async def _generate_edge_tts(text: str, voice_name: str, file_path: str) -> None:
    """Generate voice using edge-tts with robust error handling and timeout."""
    try:
        # Create communicate object with timeout
        communicate = edge_tts.Communicate(text, voice_name)

        # Use asyncio.wait_for to add timeout protection
        await asyncio.wait_for(
            communicate.save(file_path),
            timeout=EDGE_TTS_TIMEOUT
        )

        # Verify file was created and has content
        if not os.path.exists(file_path):
            raise Exception("Voice file was not created")

        if os.path.getsize(file_path) == 0:
            raise Exception("Voice file is empty")

        # Additional validation - check if file is actually an audio file
        # by checking file size (should be > 1000 bytes for meaningful audio)
        if os.path.getsize(file_path) < 1000:
            raise Exception("Voice file too small, likely corrupted")

    except asyncio.TimeoutError:
        raise Exception(f"edge-tts timeout after {EDGE_TTS_TIMEOUT} seconds")
    except Exception as e:
        # Clean up failed file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as cleanup_error:
                log_error(f"Failed to cleanup failed voice file: {cleanup_error}")

        # Provide more specific error messages
        error_msg = str(e).lower()
        if "403" in error_msg or "forbidden" in error_msg:
            raise Exception("Voice service temporarily unavailable (403 Forbidden)")
        elif "404" in error_msg or "not found" in error_msg:
            raise Exception("Voice model not found")
        elif "timeout" in error_msg:
            raise Exception("Voice generation timed out")
        else:
            raise Exception(f"edge-tts generation failed: {str(e)}")


def _generate_gtts(text: str, lang: str, file_path: str) -> None:
    """Generate voice using gTTS fallback (only for supported languages)."""
    # Map language codes to gTTS codes if needed
    gtts_lang_map = {
        'en': 'en',
        'ru': 'ru',
        'tr': 'tr',
        'ko': 'ko',
        'ar': 'ar',
        'uz': 'uz',
    }

    gtts_lang = gtts_lang_map.get(lang)
    if not gtts_lang:
        raise Exception(f"gTTS does not support language: {lang}")

    try:
        # Create gTTS object with timeout protection
        tts = gTTS(text=text, lang=gtts_lang, slow=False)
        tts.save(file_path)

        # Verify file was created and has content
        if not os.path.exists(file_path):
            raise Exception("gTTS file was not created")

        if os.path.getsize(file_path) == 0:
            raise Exception("gTTS file is empty")

        # Additional validation for gTTS files
        if os.path.getsize(file_path) < 500:
            raise Exception("gTTS file too small, likely corrupted")

    except Exception as e:
        # Clean up failed file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as cleanup_error:
                log_error(f"Failed to cleanup gTTS file: {cleanup_error}")

        raise Exception(f"gTTS generation failed: {str(e)}")


async def generate_voice(text: str, lang: str) -> str | None:
    """Generate voice for translated text with robust error handling.

    Args:
        text: Text to convert to speech
        lang: Language code (en, ru, tr, ko, ar, uz)

    Returns:
        Path to generated voice file or None if failed
    """
    start_time = time.time()
    async with voice_semaphore:
        if not isinstance(text, str):
            text = str(text)

        text = text.strip()
        if not text:
            log_error("Empty text provided for voice generation")
            return None

        # Validate text length for TTS
        if len(text) > MAX_TTS_TEXT_LENGTH:
            # Truncate text to maximum length
            original_length = len(text)
            text = text[:MAX_TTS_TEXT_LENGTH]
            log_error(f"Text truncated from {original_length} to {MAX_TTS_TEXT_LENGTH} characters for TTS")

        _ensure_cache_dir()
        text_hash = _hash_text(text)
        file_path = _get_voice_file_path(lang, text_hash)

        # Check cache first
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            duration = time.time() - start_time
            log_voice_generation(0, lang, True, cached=True, duration=duration)
            return file_path

        # Get voice name with Uzbek-specific handling
        voice_name = None
        if lang == 'uz':
            # Explicit Uzbek voice handling - try MadinaNeural first
            voice_name = 'uz-UZ-MadinaNeural'
            log_error(f"Using Uzbek voice: {voice_name}")
        else:
            voice_name = VOICE_MAP.get(lang)

        if not voice_name:
            log_error(f"Voice mapping not found for language: {lang}")
            return None

        success = False
        error_message = None
        user_friendly_error = None

        try:
            # Primary attempt with edge-tts
            try:
                log_error(f"Attempting edge-tts generation for {lang} with voice: {voice_name}")
                await _generate_edge_tts(text, voice_name, file_path)
                success = True
                duration = time.time() - start_time
                log_voice_generation(0, lang, True, cached=False, duration=duration)
                log_error(f"edge-tts generation successful for {lang}")

            except Exception as edge_error:
                error_message = str(edge_error)
                log_error(f"edge_tts error for {lang}: {edge_error}")

                # Attempt gTTS fallback in case of edge-tts failure (especially 403)
                if lang in GTTS_SUPPORTED_LANGS:
                    log_error(f"Attempting gTTS fallback for {lang} after edge-tts failure")
                    try:
                        await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(None, _generate_gtts, text, lang, file_path),
                            timeout=GTTS_TIMEOUT
                        )
                        success = True
                        duration = time.time() - start_time
                        log_voice_generation(0, lang, True, cached=False, duration=duration)
                        log_error(f"gTTS fallback successful for {lang}")
                    except Exception as gtts_error:
                        error_message = f"gTTS fallback failed: {str(gtts_error)}"
                        log_error(f"gTTS fallback error for {lang}: {gtts_error}")
                        user_friendly_error = "Hozircha ovozli xizmatda vaqtinchalik uzilish bor, matnli tarjimadan foydalanib turing"
                        success = False
                else:
                    user_friendly_error = "Hozircha ovozli xizmatda vaqtinchalik uzilish bor, matnli tarjimadan foydalanib turing"
                    log_error(f"No gTTS fallback available for {lang}")
                    success = False

        except Exception as e:
            error_message = f"Unexpected voice generation error: {str(e)}"
            log_error(f"Voice generation unexpected error for {lang}: {e}")
            success = False

        finally:
            # Clean up failed files
            if not success:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        log_error(f"Cleaned up failed voice file for {lang}")
                    except Exception as cleanup_error:
                        log_error(f"Failed to cleanup voice file for {lang}: {cleanup_error}")

        # Final validation
        if success:
            # Double-check file exists and has content
            if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
                log_error(f"Voice generation completed successfully for {lang}")
                return file_path
            else:
                log_error(f"Voice file validation failed for {lang} - file missing or too small")
                success = False

        # Log final failure
        final_error = user_friendly_error or error_message or "unknown error"
        duration = time.time() - start_time
        log_error(f"Voice generation failed for {lang}: {final_error} (duration: {duration:.2f}s)")

        # Return None - let the handler display appropriate message to user
        # gTTS doesn't support Uzbek well, so we return None and handler shows:
        # "Hozircha ushbu til uchun ovozli xizmatda uzilish bor"
        return None


def cleanup_old_cache(max_age_days: int = 7) -> int:
    import time
    _ensure_cache_dir()
    current_time = time.time()
    deleted_count = 0

    try:
        for filename in os.listdir(VOICE_CACHE_DIR):
            filepath = os.path.join(VOICE_CACHE_DIR, filename)
            if os.path.isfile(filepath):
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > max_age_days * 86400:
                    os.remove(filepath)
                    deleted_count += 1
    except Exception as e:
        log_error(f"Cache cleanup error: {e}")
    return deleted_count


def get_cache_stats() -> dict:
    _ensure_cache_dir()
    try:
        files = [f for f in os.listdir(VOICE_CACHE_DIR) if os.path.isfile(os.path.join(VOICE_CACHE_DIR, f))]
        total_size = sum(os.path.getsize(os.path.join(VOICE_CACHE_DIR, f)) for f in files)
        return {
            "file_count": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }
    except Exception as e:
        log_error(f"Error getting cache stats: {e}")
        return {"file_count": 0, "total_size_mb": 0}

