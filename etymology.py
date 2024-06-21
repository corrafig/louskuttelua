#!/usr/bin/env python3
"""Fetch word etymologies from Kotus for each epithet."""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from finnsyll import FinnSyll

# Input file
EPITHETS = "epithets.json"

# Output file
ETYMOLOGIES = "etymologies.json"

# Re-fetch and update existing etymologies and not only missing ones
OVERWRITE_EXISTING = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)
finn_syll = FinnSyll()

__version__ = "0.0.1"


@dataclass
class Etymology:
    """Etymology entity."""

    definition: str
    url: str


class Kotus:
    """Service class for the Institute for the Languages of Finland."""

    _ajax_url = "https://kaino.kotus.fi/ses/ajax.php"
    _etym_link = "https://kaino.kotus.fi/ses/?p=article&etym_id={etym_id}"
    _timeout = 10
    _headers = {
        "User-Agent": f"LouskuBot/{__version__} https://github.com/corrafig/louskuttelua"
    }

    def word_exists(self, word: str) -> bool:
        """Check if word exists in Kotus."""
        params = {"m": "qs-ajax-results", "query": word}
        response = requests.get(
            self._ajax_url,
            params=params,
            timeout=self._timeout,
            headers=self._headers,
        )
        return any(e["value"] == word for e in response.json()["record"])

    def search(self, word: str) -> Optional[Etymology]:
        """Search etymology for a word."""
        logger.info("Searching word '%s'", word)
        if not self.word_exists(word):
            logger.info("There is no etymology for the word '%s'", word)
            return None

        params = {"m": "qs-results", "prefix": word, "list_id": 1}
        response = requests.get(
            self._ajax_url,
            params=params,
            timeout=self._timeout,
            headers=self._headers,
        )
        response.raise_for_status()

        data = response.json()
        record = next((e for e in data["record"] if e["hakusana"] == word), None)
        if not record:
            logger.warning("Word '%s' should exist but result is missing", word)
            return None

        return Etymology(
            definition=record["selite"],
            url=self._etym_link.format(etym_id=record["etym_id"]),
        )


def clean_epithet(epithet: str) -> str:
    """Clean epithet from unwanted characters."""
    return re.sub(r"[^a-zäåö -]", "", epithet.lower())


def to_words(epithet: str) -> set[str]:
    """Return all segments of a compound word(s)."""
    segments = set(epithet.split(" "))

    for segment in list(segments):
        compound_words = finn_syll.split(segment).split("=")
        if len(compound_words) > 1:
            segments.update(compound_words)

    return segments


def update_etymologies(etymologies_root: dict, epithets_root: dict) -> None:
    """Add (or update) etymologies to the etymologies-dictionary."""

    etymologies = etymologies_root.setdefault("etymologies", {})
    epithets = epithets_root["epithets"]

    for epithet in epithets:
        epithet_etymologies = etymologies.get(epithet, {})
        etymologies[epithet] = search_etymologies(epithet, epithet_etymologies)

        # Persist etymologies after each epithet
        with open(ETYMOLOGIES, "w", encoding="utf-8") as file:
            file.write(json.dumps(etymologies_root, indent=2, ensure_ascii=False))


def search_etymologies(epithet, epithet_etymologies):
    """Search etymologies for an epithet."""

    cleaned_epithet = clean_epithet(epithet)
    words = to_words(cleaned_epithet)

    for word in words:
        if word in epithet_etymologies and not OVERWRITE_EXISTING:
            logger.debug(
                "Word '%s' is already in etymology data, hence skipping it.", word
            )
            continue

        etymology = Kotus().search(word)

        epithet_etymologies[word] = (
            {
                "definition": etymology.definition,
                "url": etymology.url,
            }
            if etymology
            else None
        )

    return dict(sorted(epithet_etymologies.items()))


def main():
    """The main application class."""

    with open(EPITHETS, "r", encoding="utf-8") as file:
        epithets_root = json.load(file)

    if Path(ETYMOLOGIES).is_file():
        with open(ETYMOLOGIES, "r", encoding="utf-8") as file:
            etymologies_root = json.load(file)
    else:
        etymologies_root = {}

    update_etymologies(etymologies_root, epithets_root)


if __name__ == "__main__":
    main()
