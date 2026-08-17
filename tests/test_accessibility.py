"""
test_accessibility.py
=====================
Tests for the accessibility properties the interface claims,
covering colour contrast, the redundant encoding of the confidence bands, and
the completeness of the translation catalogue.

Testing rationale:
test_pipeline.py tests whether the software computes the right answer. This
module tests whether a student can actually read it. Both are correctness
questions, but the second one is easy to assert in a comment and never check,
which is exactly what had happened: the original implementation carried a
comment stating that the Low band met the WCAG 2.2 AA minimum, and it did not.
Tol's red #BB5566 measures 4.44:1 against the light page background, and as
chip text over its own tint on a card it fell to 4.15:1.

Two of the defects this suite now guards against were only visible once the
figures were computed rather than described:

  The Low band failed SC 1.4.3 on the light theme. The comment
           claimed 4.7:1; the measured value was 4.44:1. Tol quotes his
           figures against pure white, where the same colour reaches 4.53:1,
           and the slightly tinted page background was enough to push it under.

  Contrast was being checked against the page background only. A
           confidence chip is read against its own tinted fill, and that chip
           can sit on a card or in the sidebar rather than on the page. The
           Medium band passed at 4.79:1 against the page and failed at 3.97:1
           as chip text on a card surface, because the tint is drawn in the
           band's own hue and so always closes the gap between text and
           background. test_band_contrast_worst_case checks every combination
           of band, surface and tint rather than the most flattering one.

The greyscale test encodes a negative result rather than a guarantee. Medium
and Low are separated by 0.011 relative luminance in the light theme and 0.005
in the dark, so colour alone does not distinguish them once desaturated. The
test asserts that the non-colour channels are all distinct instead, which is
the property the interface actually relies on when it is printed in a
dissertation that is marked in greyscale.

Usage:
    py -m pip install pytest
    py -m pytest test_accessibility.py -v

Expected result: all tests pass.

References:
W3C (2023). Web Content Accessibility Guidelines (WCAG) 2.2.
    SC 1.4.1 Use of Colour, SC 1.4.3 Contrast (Minimum), SC 1.4.11 Non-text
    Contrast. The 4.5:1 and 3:1 thresholds asserted below are taken from these.
Tol, P. (2021). Colour schemes. SRON Technical Note SRON/EPS/TN/09-002.
    Source of the palette, and of the pure-white reference figures that did not
    transfer to this interface's backgrounds.
"""

import re

import pytest

from ui.ui_theme import (
    BAND_STYLE, BAND_ORDER, BAND_SURFACES, BAND_TINT_ALPHA, TOKENS,
)
from ui import i18n
from ui.mcq_i18n import localised_questions, MCQ_TRANSLATIONS
from core.prerequisite_check import MCQ_BANK

#WCAG 2.2 thresholds
AA_TEXT = 4.5          #SC 1.4.3, body text
AA_NON_TEXT = 3.0      #SC 1.4.11, user interface components


#Colour helpers
#
#Implemented here from the WCAG definition rather than imported from a
#library, so the suite has no dependency beyond pytest and the numbers in the
#comments can be re-derived from this file alone.

def to_rgb(hex_colour: str) -> tuple[float, float, float]:
    h = hex_colour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    """WCAG 2.x relative luminance of an sRGB triple."""
    channels = []
    for value in rgb:
        v = value / 255
        channels.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b) -> float:
    """WCAG 2.x contrast ratio between two colours, given as hex or rgb."""
    la = relative_luminance(to_rgb(a) if isinstance(a, str) else a)
    lb = relative_luminance(to_rgb(b) if isinstance(b, str) else b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def composite(fg_hex: str, bg_hex: str, alpha: float):
    """Flatten a semi-transparent fill over an opaque background."""
    fg, bg = to_rgb(fg_hex), to_rgb(bg_hex)
    return tuple(fg[i] * alpha + bg[i] * (1 - alpha) for i in range(3))


def band_hex(band: str, theme: str) -> str:
    style = BAND_STYLE[band]
    return style["colour_dark"] if theme == "dark" else style["colour"]


THEMES = ("light", "dark")


#Contrast: confidence bands

class TestBandContrast:
    """SC 1.4.3 for the band colours, in the conditions they are actually
    rendered in."""

    @pytest.mark.parametrize("theme", THEMES)
    @pytest.mark.parametrize("band", BAND_ORDER)
    def test_band_on_page_background(self, band, theme):
        """Baseline: the band colour against its theme's page background."""
        page = BAND_SURFACES[theme][0]
        assert contrast(band_hex(band, theme), page) >= AA_TEXT

    @pytest.mark.parametrize("theme", THEMES)
    @pytest.mark.parametrize("band", BAND_ORDER)
    def test_band_contrast_worst_case(self, band, theme):
        """
        The case that matters, and the one the original code missed.

        A chip's text is read against the chip's own tinted fill, over whichever
        surface the chip is sitting on. Because the tint is the band's own hue,
        it always moves the background towards the text. Every surface the chip
        can appear on is checked, not just the page.
        """
        colour = band_hex(band, theme)
        alpha = BAND_TINT_ALPHA[theme]

        for surface in BAND_SURFACES[theme]:
            tinted = composite(colour, surface, alpha)
            ratio = contrast(colour, tinted)
            assert ratio >= AA_TEXT, (
                f"{band} ({colour}) on tinted fill over {surface} in the "
                f"{theme} theme is {ratio:.2f}:1, below {AA_TEXT}:1"
            )

    def test_tol_original_red_would_fail(self):
        """
        Regression guard for the Low band contrast failure.

        Pins the reason the light theme does not use Tol's published red. If
        someone restores #BB5566 on the assumption that the palette values are
        safe as given, test_band_on_page_background fails; this test documents
        why by asserting the measurement directly.
        """
        page = BAND_SURFACES["light"][0]
        assert contrast("#BB5566", page) < AA_TEXT
        assert contrast("#BB5566", "#FFFFFF") >= AA_TEXT   #Tol's own reference

    @pytest.mark.parametrize("theme", THEMES)
    def test_tint_alpha_is_at_its_ceiling(self, theme):
        """
        The tint alpha is a contrast budget, not a style preference.

        Asserts that raising it by a small step would break at least one band,
        so a later change to soften or strengthen the fill cannot be made
        without the suite objecting.
        """
        alpha = BAND_TINT_ALPHA[theme] + 0.05
        worst = min(
            contrast(band_hex(band, theme),
                     composite(band_hex(band, theme), surface, alpha))
            for band in BAND_ORDER
            for surface in BAND_SURFACES[theme]
        )
        assert worst < AA_TEXT


#Contrast: text and controls

class TestTokenContrast:

    @pytest.mark.parametrize("theme", THEMES)
    @pytest.mark.parametrize("token", ["text", "text_muted", "text_subtle"])
    def test_text_tokens_meet_aa(self, token, theme):
        """
        Every text token is used at small sizes somewhere in the interface, so
        the 3:1 large-text allowance in SC 1.4.3 does not apply to any of them.
        text_subtle is the one that previously failed, at 3.40:1 on the light
        theme, where it sets source metadata, tags and captions.
        """
        tokens = TOKENS[theme]
        assert contrast(tokens[token], tokens["bg"]) >= AA_TEXT

    @pytest.mark.parametrize("theme", THEMES)
    def test_control_border_meets_non_text_contrast(self, theme):
        """SC 1.4.11: the boundary that identifies a control needs 3:1."""
        tokens = TOKENS[theme]
        assert contrast(tokens["border_control"], tokens["bg"]) >= AA_NON_TEXT

    @pytest.mark.parametrize("theme", THEMES)
    def test_accent_meets_aa(self, theme):
        """The accent sets link text and primary button labels."""
        tokens = TOKENS[theme]
        assert contrast(tokens["accent"], tokens["bg"]) >= AA_TEXT


#Redundant encoding (SC 1.4.1)

class TestRedundantEncoding:

    def test_every_band_has_all_four_channels(self):
        """Colour, shape, ordinal position, and a label supplied by i18n."""
        for band in BAND_ORDER:
            style = BAND_STYLE[band]
            assert style["colour"] and style["colour_dark"]
            assert style["marker"]
            assert style["segments"] in (1, 2, 3)
            assert i18n.STRINGS[f"band.{band}"]["en"]

    def test_markers_are_distinct(self):
        markers = [BAND_STYLE[b]["marker"] for b in BAND_ORDER]
        assert len(set(markers)) == len(markers)

    def test_meter_segments_are_distinct_and_ordered(self):
        """High fills 3, Medium 2, Low 1: a count, readable without colour."""
        segments = [BAND_STYLE[b]["segments"] for b in BAND_ORDER]
        assert segments == [3, 2, 1]

    @pytest.mark.parametrize("theme", THEMES)
    def test_colour_alone_does_not_survive_greyscale(self, theme):
        """
        Encodes the negative result the meter exists to answer.

        Medium and Low differ by 0.011 relative luminance in the light theme
        and 0.005 in the dark, which no reader resolves on a greyscale print.
        This is asserted rather than hidden, so the docstring in ui_theme.py
        cannot drift back to claiming that lightness carries the ordering. If a
        future palette change does separate them, this test fails and the claim
        can be updated deliberately.
        """
        lums = {b: relative_luminance(to_rgb(band_hex(b, theme)))
                for b in BAND_ORDER}
        assert abs(lums["Medium"] - lums["Low"]) < 0.05

    @pytest.mark.parametrize("theme", THEMES)
    def test_non_colour_channels_do_survive_greyscale(self, theme):
        """The three channels that carry the band when colour cannot."""
        markers = {BAND_STYLE[b]["marker"] for b in BAND_ORDER}
        segments = {BAND_STYLE[b]["segments"] for b in BAND_ORDER}
        labels = {i18n.STRINGS[f"band.{b}"]["en"] for b in BAND_ORDER}
        assert len(markers) == len(segments) == len(labels) == 3


#Translation catalogue

class TestTranslationCatalogue:

    @pytest.mark.parametrize("lang", i18n.LANGUAGE_ORDER)
    def test_no_missing_translations(self, lang):
        """
        A missing entry falls back to English rather than raising, so a gap is
        invisible at runtime to anyone who reads English. It has to be caught
        here instead.
        """
        missing = [key for key, entry in i18n.STRINGS.items() if not entry.get(lang)]
        assert not missing, f"missing {lang}: {missing}"

    @pytest.mark.parametrize("lang", ["it", "fr"])
    def test_format_placeholders_survive_translation(self, lang):
        """
        t() swallows a formatting failure to avoid losing a student's answer to
        a cosmetic defect, which means a dropped {score} placeholder would show
        an unformatted string rather than crash. Compared against English here.
        """
        for key, entry in i18n.STRINGS.items():
            english = set(re.findall(r"\{(\w+)\}", entry["en"]))
            translated = set(re.findall(r"\{(\w+)\}", entry[lang]))
            assert translated == english, f"{key} ({lang})"

    def test_english_prompt_clause_is_empty(self):
        """
        The gold-set evaluation was scored on the English prompt. An empty
        clause keeps that prompt byte-identical, so the multilingual work
        cannot have shifted the accuracy figures.
        """
        assert i18n.answer_language_instruction("en") == ""

    @pytest.mark.parametrize("lang", ["it", "fr"])
    def test_non_english_clause_names_its_language(self, lang):
        clause = i18n.answer_language_instruction(lang)
        assert i18n.LANGUAGES[lang]["name_in_english"] in clause
        assert "CONFIDENCE" in clause   #the parsed line must stay in English


#Translated MCQ bank

class TestLocalisedMCQ:

    @pytest.mark.parametrize("lang", ["it", "fr"])
    @pytest.mark.parametrize("topic", sorted(MCQ_BANK))
    def test_answer_key_is_never_translated(self, lang, topic):
        """
        The property that makes scoring language-independent by construction:
        display text comes from the overlay, the answer always comes from the
        canonical bank.
        """
        for localised, canonical in zip(localised_questions(topic, lang),
                                        MCQ_BANK[topic]):
            assert localised["answer"] == canonical["answer"]
            assert set(localised["options"]) == set(canonical["options"])

    @pytest.mark.parametrize("lang", ["it", "fr"])
    @pytest.mark.parametrize("topic", sorted(MCQ_BANK))
    def test_every_question_is_actually_translated(self, lang, topic):
        """
        localised_questions() falls back to English per question, so an absent
        or malformed overlay degrades silently to an English item. That is the
        right runtime behaviour and the wrong thing to ship, so it is caught
        here.
        """
        for localised, canonical in zip(localised_questions(topic, lang),
                                        MCQ_BANK[topic]):
            assert localised["question"] != canonical["question"]
            assert localised["explanation"] != canonical["explanation"]

    @pytest.mark.parametrize("lang", ["it", "fr"])
    def test_overlay_covers_every_topic(self, lang):
        assert set(MCQ_TRANSLATIONS[lang]) == set(MCQ_BANK)

    @pytest.mark.parametrize("lang", ["it", "fr"])
    @pytest.mark.parametrize("topic", sorted(MCQ_BANK))
    def test_overlay_length_matches_canonical(self, lang, topic):
        """
        The two lists are zipped positionally, so an overlay with an extra or
        missing entry would attach the wrong stem to an answer key without any
        fallback noticing. Ordering is the one thing the merge cannot check
        for itself.
        """
        assert len(MCQ_TRANSLATIONS[lang][topic]) == len(MCQ_BANK[topic])

    def test_unknown_language_falls_back_to_english(self):
        assert localised_questions("ARP protocol", "de") == MCQ_BANK["ARP protocol"]
