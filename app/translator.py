from deep_translator import GoogleTranslator

_translator = None


def _get_translator():
    global _translator
    if _translator is None:
        _translator = GoogleTranslator(source='en', target='ar')
    return _translator


def translate_batch(texts):
    texts = [t.strip() for t in texts if t and t.strip()]
    if not texts:
        return []
    translator = _get_translator()
    return translator.translate_batch(texts)
