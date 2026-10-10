"""Text clean-up just before TTS.

Sarvam reads a hyphenated range like "15-20" digit by digit ("ek paanch do shunya"),
while plain numbers ("15", "4 baje") are read fine. So ranges become "15 se 20" etc.
in the language currently being spoken.
"""

import re

from pipecat.utils.text.base_text_filter import BaseTextFilter

RANGE = re.compile(r"(\d+(?:\s*(?:AM|PM|am|pm|बजे|baje))?)\s*[-–—]\s*(\d+)")
CONNECTOR = {"hi-IN": ("से", "se"), "ta-IN": ("முதல்", "mudhal"), "en-IN": ("to", "to")}


class SpokenNumbersFilter(BaseTextFilter):
    def __init__(self, state):
        super().__init__()
        self.state = state

    async def update_settings(self, settings):
        pass

    async def filter(self, text: str) -> str:
        lang = self.state.live["language_code"]
        native, roman = CONNECTOR.get(lang, ("to", "to"))
        latin = not re.search(r"[ऀ-෿]", text)
        word = roman if latin and lang != "en-IN" else native
        return RANGE.sub(lambda m: f"{m.group(1)} {word} {m.group(2)}", text)

    async def handle_interruption(self):
        pass

    async def reset_interruption(self):
        pass
