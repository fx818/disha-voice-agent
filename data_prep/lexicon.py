"""Romanized-text lexicons shared by the evidence analysis and the live agent.

Sellers' speech in the transcripts is romanized (Hinglish, Tamil in Latin script, ...),
so language and signal detection are keyword based.
"""
import re

# Distinctive romanized words per language. Words shared with Hindi are left out.
LANG_WORDS = {
    "ta-IN": {"illa", "illai", "enna", "sollunga", "vendaam", "vendam", "irukku", "inga", "aamaa", "aama",
              "ungalukku", "enakku", "naan", "pannunga", "theriyum", "seri", "sari", "romba", "ippo",
              "nalaikku", "vaanga", "anga", "enga", "eppo", "konjam", "paarunga", "ponga"},
    "te-IN": {"ledu", "cheppandi", "avunu", "enti", "emi", "meeru", "nenu", "kaadu", "unnaru", "andi",
              "cheyyandi", "kavali", "ippudu", "repu", "chestanu", "chestha", "raa", "vasthanu", "ekkada",
              "baagundi", "sare"},
    "kn-IN": {"beda", "beku", "heli", "nimma", "naanu", "maadi", "gottilla", "houdu", "swalpa", "yaake",
              "banni", "aagutte", "illri", "naale", "eega", "yenu", "elli", "hogi", "madtini"},
    "ml-IN": {"alla", "enthu", "entha", "venda", "ningal", "njan", "undu", "parayu", "sheri", "cheyyam",
              "aano", "illallo", "evide", "nale", "ippol", "kollam", "manassilayilla"},
    "gu-IN": {"chhe", "che", "nathi", "tame", "tamaru", "kem", "maru", "shu", "avjo", "saru", "kaale",
              "pachi", "hamna", "karjo", "aapo", "joie", "bhai", "barabar", "hoon"},
    "mr-IN": {"aahe", "ahe", "kay", "bola", "mala", "tumhi", "tumhala", "kaay", "zala", "hoy", "udya",
              "sanga", "naahi", "nako", "karto", "bagha", "aata", "kuthe", "pahije"},
    "bn-IN": {"ami", "apni", "achhe", "ache", "bolchi", "bolun", "hobe", "kotha", "ekhon", "korbo", "amar",
              "apnar", "bolchen", "korun", "lagbe", "parbo", "kal", "bujhte", "thik"},
    "pa-IN": {"tusi", "tuhanu", "tuhada", "sanu", "kidda", "menu", "gal", "karo", "dasso", "hunda",
              "kithe", "assi", "haige"},
    "od-IN": {"mu", "kana", "achhi", "apana", "kahinki", "heba", "karibi", "kahibe", "nahin"},
}
HI_WORDS = {"hai", "hain", "nahi", "nahin", "kya", "haan", "aap", "mujhe", "hoon", "baat", "abhi",
            "theek", "boliye", "karenge", "chahiye", "mera", "mere", "kaun", "kar", "raha", "rahe", "ji",
            "toh", "bhi", "kaise", "kab", "kahan", "kyun", "matlab", "bataiye"}
# Ambiguous words that appear in Hindi too: drop them from the regional lists.
for _w in ("kal", "karo", "gal", "hoon", "thik", "bhai", "che", "mu", "kana", "nahin", "menu"):
    for _s in LANG_WORDS.values():
        _s.discard(_w)

EN_WORDS = {"the", "is", "please", "call", "meeting", "busy", "sorry", "okay", "ok", "time", "yes", "no",
            "tomorrow", "today", "office", "sir", "madam", "mam", "actually", "already", "not", "interested",
            "what", "who", "are", "you", "i", "am", "will", "later", "after", "morning", "evening",
            "business", "product", "service", "price", "details", "send", "number", "thank", "thanks",
            "right", "now", "free", "but", "and", "my", "we", "our", "your", "requirement", "online"}

SIGNALS = {
    "rush": [r"\bbusy\b", r"abhi time nahi", r"time nahi hai", r"\bjaldi\b", r"baad (mein|me)\b",
             r"call back", r"\bdriv", r"gaadi chala", r"meeting (mein|me) hoon", r"bahar hoon",
             r"short (mein|me)", r"abhi nahi", r"kya kaam hai", r"seedha bol", r"point pe", r"2 minute",
             r"do minute", r"later\b", r"call later", r"free nahi"],
    "frustration": [r"baar baar", r"bar bar", r"kitni baar", r"pareshan", r"dimag", r"mat karo",
                    r"call mat", r"band karo", r"faltu", r"bakwas", r"irritat", r"disturb", r"gussa",
                    r"\broz\b", r"har din", r"kitne call", r"block", r"complaint", r"kitni bar",
                    r"pagal", r"dobara call mat", r"phone mat"],
    "confusion": [r"samajh nahi", r"samjha nahi", r"samjhi nahi", r"kya bola", r"kya bol rah",
                  r"kaun bol", r"kis baare", r"kiske liye", r"phir se", r"dobara bol", r"repeat",
                  r"kaunsa", r"clear nahi", r"awaaz nahi", r"sunai nahi", r"kya matlab", r"matlab\?",
                  r"\bwhat\?", r"kya\?$", r"\bhaan\?$", r"\bji\?$", r"kaun sa"],
    "interest": [r"kitna", r"\bprice\b", r"\brate\b", r"charge", r"kaise (hoga|milega|kaam)", r"details",
                 r"zaroor", r"kab aayenge", r"aa jaiye", r"aa jao", r"address", r"kya fayda",
                 r"leads? mil", r"\bbuyer", r"enquiry", r"inquiry", r"bhej (do|dijiye)", r"kitne baje",
                 r"theek hai.*(kal|baje)", r"chalega", r"ho jayega"],
    "bot_question": [r"\bai\b", r"robot", r"\bbot\b", r"recorded", r"recording", r"machine", r"computer",
                     r"automatic", r"insaan", r"real (person|insaan)"],
}
SIGNAL_RE = {k: re.compile("|".join(v), re.I) for k, v in SIGNALS.items()}
_TOK = re.compile(r"[a-z]+")


def tokens(text):
    return _TOK.findall(str(text).lower())


def detect_language(text):
    """Return (code, score) for a romanized utterance; hi-IN default, None when too short."""
    toks = tokens(text)
    if not toks:
        return None, 0
    scores = {code: sum(t in words for t in toks) for code, words in LANG_WORDS.items()}
    best = max(scores, key=scores.get)
    hi = sum(t in HI_WORDS for t in toks)
    if scores[best] >= 1 and scores[best] > hi:
        return best, scores[best]
    if hi:
        return "hi-IN", hi
    en = sum(t in EN_WORDS for t in toks)
    if en >= 2 and en / len(toks) > 0.6:
        return "en-IN", en
    return None, 0


def english_share(text):
    toks = tokens(text)
    return (sum(t in EN_WORDS for t in toks) / len(toks)) if toks else None


def signals_in(text):
    return [k for k, rx in SIGNAL_RE.items() if rx.search(str(text))]
