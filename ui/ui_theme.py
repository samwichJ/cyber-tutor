'''
this .py holds every colour, design token and piece of markup the front end
draws with, so the accessibility work sits in one file
instead of being spread through streamlit_app.py

the confidence band is what this file exists for. it is communicated four
redundant ways and any one of them identifies the band on its own:

  1. colour, the Paul Tol high contrast qualitative scheme (Tol, 2021)
  2. shape, a different marker glyph per band, circle, triangle, square
  3. text, the band written out, High, Medium or Low
  4. position, a three segment meter filled 3, 2 or 1

the fourth is new and the measurements are the reason it had to be. colour,
shape and text all say which band it is, but none of them says where that band
sits in the order, nothing about a triangle tells you it belongs between a
circle and a square. the meter is a count of filled bars, so it carries the
ordering, and it keeps carrying it once the colour is gone

that greyscale point is not theoretical. the comment this replaced claimed the
three bands differ in lightness so the ordering survives desaturation, and
measured that is simply not true of Medium and Low:

    light theme   High 0.059    Medium 0.163    Low 0.152
    dark theme    High 0.379    Medium 0.444    Low 0.439

(WCAG relative luminance.) Medium and Low are 0.011 and 0.005 apart, which
nobody is resolving on a greyscale print, and the interface goes into a
dissertation that gets marked in greyscale. three hues taken from one
qualitative palette are picked to be equally salient rather than to form a
lightness ramp, so no rearranging of them would have fixed it. what does
survive is the marker, the label and the bar count, three channels out of four

red/amber/green would have been the obvious palette and is the wrong one, since
red/green is the most common confusion axis in colour vision deficiency and
affects roughly 8% of males (World Health Organization, 2023). Tol's high
contrast scheme is built to stay separable under deuteranopia, protanopia and
tritanopia

each band carries two hex values because one set does not work on both themes.
Tol's published values are tuned for light backgrounds and drop below the WCAG
2.2 SC 1.4.3 minimum of 4.5:1 on the dark one (#004488 on #0F141A measures
1.92:1), so band_colour() swaps in a lightened variant at render time. it goes
the other way for the amber, #DDAA33 measures 2.07:1 on the light page

two things came out of measuring rather than assuming, both on the light theme,
and both are written down because the previous comments said the opposite

first, Tol's red #BB5566 measures 4.44:1 on this background, under the 4.5:1 AA
minimum rather than over it. Tol quotes his figures against pure white where the
same colour makes 4.53:1, and the very slightly tinted page here is enough to
push it under

second, and less obvious, a band colour is never read against the page. it is
read against its own tinted chip fill, and that chip can be sitting on a card or
in the sidebar. checking against the page only flattered everything, #8A6D00
passed at 4.79:1 on the page and failed at 3.97:1 as chip text on a card,
because the tint is drawn in the band's own hue and so always closes the gap
between the text and its background. the light values are now chosen against the
worst surface and tint combination instead of the best, which is what moved
Medium to #785E00 and Low to #A24051

every ratio in this file was computed rather than estimated, each one is written
next to the value it belongs to, and test_accessibility.py recomputes all of
them, so a later change to a colour, a surface or a tint cannot quietly break
the accessibility claim
'''

import html
from string import Template

import streamlit as st

from config import APP_ICON

#Confidence bands

#the ratio quoted against each value is its worst case: the band colour read against its own tinted chip fill, over the darkest surface that chip can
#sit on.
BAND_STYLE: dict[str, dict] = {
    "High": {
        "colour":      "#004488",   #Tol high-contrast blue,   6.97:1 worst case
        "colour_dark": "#77AADD",   #lightened blue,           4.64:1 worst case
        "marker":      "●",    #filled circle
        "segments":    3,
    },
    "Medium": {
        #Tol's #DDAA33 is 2.07:1 on a light page. darkened for the light theme, then darkened again from #8A6D00, which passed against the page but
        #not against a tinted chip on a card
        "colour":      "#785E00",   #darkened Tol amber,       4.62:1 worst case
        "colour_dark": "#DDAA33",   #Tol high-contrast yellow, 5.29:1 worst case
        "marker":      "▲",    #filled triangle
        "segments":    2,
    },
    "Low": {
        #Tol's own #BB5566 measures 4.44:1 even against the page background and fails AA outright. see the module docstring
        "colour":      "#A24051",   #darkened Tol red,         4.61:1 worst case
        "colour_dark": "#EE99AA",   #lightened red,            5.23:1 worst case
        "marker":      "■",    #filled square
        "segments":    1,
    },
}

BAND_ORDER = ("High", "Medium", "Low")

#alpha of the tint behind a confidence chip or a review row.
BAND_TINT_ALPHA = {"light": 0.10, "dark": 0.13}

#every surface a band colour can be drawn on, per theme.
BAND_SURFACES = {
    "light": ("#FBFCFD", "#F2F5F8", "#F4F7FA", "#E8EEF3"),
    "dark":  ("#0F141A", "#19212A", "#212B36", "#0B1015"),
}


#Neutral ramps Deliberately near-achromatic.

#text colours carry their measured ratio against that theme's page background.
TOKENS: dict[str, dict[str, str]] = {
    "light": {
        "bg":             "#FBFCFD",
        "surface":        "#FFFFFF",
        "surface_2":      "#F2F5F8",
        "surface_3":      "#E8EEF3",
        "border":         "#D7DFE7",
        "border_strong":  "#B9C6D2",
        "border_control": "#7B95B0",   #3.02:1, for control boundaries
        "text":           "#141D26",   #16.57:1
        "text_muted":     "#586A7B",   #5.43:1
        #was #7C8B99, which measured 3.40:1 and failed AA for the small text it is used on (source metadata, tags, captions). darkened to clear 4.5:1
        "text_subtle":    "#667583",   #4.61:1
        "accent":         "#004488",
        "accent_soft":    "#E4EDF6",
        "shadow":         "0 1px 2px rgba(20, 29, 38, 0.05), 0 4px 12px rgba(20, 29, 38, 0.04)",
    },
    "dark": {
        "bg":             "#0F141A",
        "surface":        "#161E26",
        "surface_2":      "#19212A",
        "surface_3":      "#212B36",
        "border":         "#2B3540",
        "border_strong":  "#3D4A57",
        "border_control": "#5E6E7D",   #3.53:1, for control boundaries
        "text":           "#E9EEF3",   #15.85:1
        "text_muted":     "#9DACBA",   #7.97:1
        "text_subtle":    "#7A8998",   #5.16:1
        "accent":         "#77AADD",
        "accent_soft":    "#132433",
        "shadow":         "0 1px 2px rgba(0, 0, 0, 0.35), 0 4px 14px rgba(0, 0, 0, 0.25)",
    },
}


#Theme resolution

#the browser key Streamlit stores its active theme under.
THEME_STORAGE_KEY = "stActiveTheme-/-v2"

def client_theme() -> str:
    """
    The theme the browser is actually rendering.

    st.context.theme reports what the client resolved, which is the source of
    truth: since the theme lives in the browser's own storage, the server does
    not decide it. Falls back to the configured default in
    .streamlit/config.toml.
    """
    try:
        return "dark" if st.context.theme.type == "dark" else "light"
    except Exception:
        #older Streamlit, or a context where the property is unavailable
        return "dark"


def active_theme() -> str:
    """
    Return "light" or "dark" for the theme the components should be drawn in.

    This is simply what the client reports, which is worth a note because the
    obvious alternative is wrong. The earlier implementation switched themes by
    setting the private st._config option theme.base, and reading that back
    would have been reading a process-global value: with the app served from
    one process behind a shared link, every participant in the user study would
    have shared one theme, and one of them changing it would have changed it
    for the others.

    That is not merely an unpleasant default, it also no longer works. Once
    .streamlit/config.toml defines both [theme.light] and [theme.dark], the
    frontend resolves the active theme from the browser's own storage and
    ignores a runtime change to theme.base, so the old toggle moved the
    confidence colours while leaving the page chrome behind. render_theme_toggle
    in streamlit_app.py now writes the browser's stored preference instead,
    which is per browser by construction, and this function reads the result.
    """
    return client_theme()


def tokens() -> dict[str, str]:
    """Neutral design tokens for the active theme."""
    return TOKENS[active_theme()]

def band_colour(band: str) -> str:
    """
    Return the contrast-safe hex for a band under the active theme.

    Accepts either a band name ("High") or a BAND_STYLE entry, since callers in
    the sidebar hold the style dict already.
    """
    style = BAND_STYLE[band] if isinstance(band, str) else band
    if active_theme() == "dark":
        return style.get("colour_dark", style["colour"])
    return style["colour"]


#the app mark, inlined as a data URI the PNG is roughly 230 KB, which is far more than a 56 px mark needs, and Streamlit will not serve a local file
#to an <img> tag unless static serving is switched on.
@st.cache_data(show_spinner=False)
def app_icon_data_uri(size: int = 112) -> str:
    """Return the app icon as a base64 data URI, downscaled to size px."""
    import base64
    import io

    try:
        from PIL import Image

        with Image.open(APP_ICON) as source:
            icon = source.convert("RGBA")
            icon.thumbnail((size, size), Image.LANCZOS)
            buffer = io.BytesIO()
            icon.save(buffer, format="PNG", optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        #a missing or unreadable icon must not take the page down with it. the masthead checks for an empty string and falls back to the title alone
        return ""

    return f"data:image/png;base64,{encoded}"

def app_mark_html(size: int = 56, extra_class: str = "") -> str:
    """
    The icon as an <img>, or an empty string if it could not be loaded.

    alt is deliberately empty. The mark always sits directly beside the app
    name, so giving it alt text would make a screen reader announce the name
    twice; an empty alt marks it as decorative, which is what WAI-ARIA expects
    for an image whose meaning is already carried by adjacent text.
    """
    uri = app_icon_data_uri(size * 2)      #2x for high-density displays
    if not uri:
        return ""
    classes = f"ns-mark {extra_class}".strip()
    return (f'<img class="{classes}" src="{uri}" alt="" '
            f'style="width:{size}px;height:{size}px;">')

def _rgba(hex_colour: str, alpha: float) -> str:
    """
    Convert #RRGGBB to an rgba() string.

    Tints are produced here rather than with the CSS color-mix() function so
    that the interface renders identically in older browsers, which matters
    when the demonstration is recorded on a lab machine.
    """
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def band_tint(band: str) -> str:
    """
    Low-alpha fill for a band chip or review row.

    The tint is the band's own colour, so it always moves the background
    towards the text and always costs contrast. BAND_TINT_ALPHA holds the
    highest value that keeps every band above 4.5:1 on every surface it can
    appear on; raising it is not a free cosmetic change.
    """
    return _rgba(band_colour(band), BAND_TINT_ALPHA[active_theme()])


#Markup builders
#
#These return HTML strings rather than calling st.markdown themselves, so the caller decides where the fragment lands (thread, sidebar, dialog) and
#the builders stay unit-testable without a Streamlit runtime.

def confidence_meter_html(band: str, colour: str) -> str:
    """
    Three-segment signal-strength meter: High fills 3, Medium 2, Low 1.

    Marked aria-hidden because the adjacent text label already conveys the band
    to a screen reader; announcing it twice would be noise.
    """
    filled = BAND_STYLE[band]["segments"]
    segs = "".join(
        f'<i class="ns-meter__seg{" is-on" if i < filled else ""}"></i>'
        for i in range(3)
    )
    return (
        f'<span class="ns-meter" style="color:{colour};" aria-hidden="true">'
        f'{segs}</span>'
    )


def band_chip_html(band: str, label: str) -> str:
    """
    The confidence chip: tinted pill carrying all four encoding channels.

    The fill is what visually separates a chip from ordinary chrome. The page
    accent is also Tol blue, so an outline-only High chip could be mistaken for
    a link or a button; a filled pill with a marker glyph reads as a status.
    """
    colour = band_colour(band)
    return (
        f'<span class="ns-band" style="'
        f'color:{colour};'
        f'background:{band_tint(band)};'
        f'border-color:{_rgba(colour, 0.55)};">'
        f'<span class="ns-band__marker" aria-hidden="true">'
        f'{BAND_STYLE[band]["marker"]}</span>'
        f'<span class="ns-band__label">{label}</span>'
        f'{confidence_meter_html(band, colour)}'
        f'</span>'
    )



def relevance_bar_html(relevance: float) -> str:
    """
    Horizontal bar for a single retrieved chunk's relevance.

    Drawn in the neutral accent rather than a band colour: it describes one
    source, not the answer's overall confidence, and reusing a band hue here
    would imply a per-source band that the pipeline does not compute.
    """
    pct = max(0.0, min(1.0, relevance)) * 100
    return (
        f'<span class="ns-rel" aria-hidden="true">'
        f'<span class="ns-rel__fill" style="width:{pct:.0f}%;"></span></span>'
    )


#Glyphs for the prerequisite review.
CORRECT_MARK = "✓"     #check mark
INCORRECT_MARK = "✗"   #ballot X


def review_item_html(item: dict, labels: dict, correct: bool = False,
                     week_note: str | None = None) -> str:
    """
    One reviewed question from a prerequisite probe, as a single card.

    Colour is doing real work here, which it was not before: the chosen answer
    and the correct answer were previously two plain lines of body text, so a
    student scanning the review had to read both in full to work out which was
    which. They are now separated by hue (Tol red for the mistake, Tol blue for
    the correct option), by a tick/cross glyph, by a coloured left rule and by
    an explicit text label. That is the same four-channel discipline used for
    the confidence bands, and for the same reason: colour carries the meaning
    faster, and the other three channels carry it at all when colour cannot.

    Red is used for the mistake rather than for the correct answer even though
    red also marks the Low confidence band. The two never appear in the same
    component, and "red means the thing that went wrong" is the reading a
    student will already bring to a marked answer.

    Structurally this replaces four separate Streamlit calls per question - two
    markdown lines, an st.info box and a horizontal rule. Those produced a lot
    of vertical space and heavy full-width tinted panels for what is a short
    piece of feedback; the whole item is now one bordered card whose explanation
    reads as a note rather than as an alert.

    labels supplies the localised strings, so this stays free of any dependency
    on the translation catalogue: {"you_chose", "correct", "no_answer"}.

    correct=True is the quiz case. The prerequisite review only ever shows
    questions the student got wrong, but a quiz review shows the whole paper,
    and a correctly answered item should not be laid out as a mistake. In that
    case a single row is drawn in the High colour with a tick, rather than the
    wrong-then-right pair.
    """
    theme = active_theme()
    wrong_colour = BAND_STYLE["Low"]["colour_dark" if theme == "dark" else "colour"]
    right_colour = BAND_STYLE["High"]["colour_dark" if theme == "dark" else "colour"]

    def row(colour, mark, text):
        return (
            f'<div class="ns-review__row" style="'
            f'color:{colour};background:{_rgba(colour, 0.10)};'
            f'border-left-color:{colour};">'
            f'<span class="ns-review__mark">{mark}</span>'
            f'<span class="ns-review__text">{text}</span></div>'
        )

    #a question left blank is scored as incorrect, so it appears in the review, but reporting it as "you chose -" would be both wrong and confusing
    if item["chosen_label"] == "-":
        chosen = f'<em>{html.escape(labels["no_answer"])}</em>'
    else:
        chosen = (
            f'<strong>{html.escape(item["chosen_label"])})</strong> '
            f'{html.escape(item["chosen_text"])}'
        )

    answer_text = (
        f'{html.escape(labels["correct"])}: '
        f'<strong>{html.escape(item["answer_label"])})</strong> '
        f'{html.escape(item["answer_text"])}'
    )

    if correct:
        rows = row(right_colour, CORRECT_MARK, answer_text)
    else:
        rows = (row(wrong_colour, INCORRECT_MARK,
                    f'{html.escape(labels["you_chose"])}: {chosen}')
                + row(right_colour, CORRECT_MARK, answer_text))

    note = ""
    if week_note:
        note = (f'<p class="ns-review__why" style="border:0;padding:0;'
                f'margin-top:0.35rem;font-size:0.74rem;">'
                f'{html.escape(week_note)}</p>')

    return (
        f'<div class="ns-review">'
        f'  <p class="ns-review__q">'
        f'    <span class="ns-review__n">{item["number"]}</span>'
        f'    {html.escape(item["question"])}'
        f'  </p>'
        f'  {rows}'
        f'  <p class="ns-review__why">{html.escape(item["explanation"])}</p>'
        f'  {note}'
        f'</div>'
    )


def stat_row_html(label: str, value: str) -> str:
    """One label/value row in the sidebar progress panel."""
    return (
        f'<div class="ns-stat">'
        f'<span class="ns-stat__label">{label}</span>'
        f'<span class="ns-stat__value">{value}</span>'
        f'</div>'
    )



def confidence_mix_html(counts: dict[str, int]) -> str:
    """
    Stacked bar showing how many answers landed in each band this session.

    Each segment carries its band's marker glyph as well as its colour, so the
    breakdown is readable without the key and without colour perception. A
    segment is only labelled when it is wide enough for the glyph to fit;
    narrow ones fall back to colour plus the tooltip.
    """
    total = sum(counts.values())
    if not total:
        return ""

    parts = []
    for band in BAND_ORDER:
        n = counts.get(band, 0)
        if not n:
            continue
        pct = n / total * 100
        colour = band_colour(band)
        glyph = BAND_STYLE[band]["marker"] if pct >= 18 else ""
        parts.append(
            f'<span class="ns-mix__seg" style="width:{pct:.2f}%;background:{colour};" '
            f'title="{band}: {n}">{glyph}</span>'
        )
    return f'<span class="ns-mix">{"".join(parts)}</span>'


#Stylesheet

_CSS = Template("""
<style>
/* Custom properties. Streamlit 1.59 compiles its own theme into generated
   emotion class names rather than CSS variables, so there is nothing to hook
   into; the tokens the bespoke components need are republished here. */
.stApp {
  --ns-bg: $bg;
  --ns-surface: $surface;
  --ns-surface-2: $surface_2;
  --ns-surface-3: $surface_3;
  --ns-border: $border;
  --ns-border-strong: $border_strong;
  --ns-border-control: $border_control;
  --ns-text: $text;
  --ns-muted: $text_muted;
  --ns-subtle: $text_subtle;
  --ns-accent: $accent;
  --ns-accent-soft: $accent_soft;
  --ns-shadow: $shadow;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Page frame */
[data-testid="stMainBlockContainer"] {
  padding-top: 2.25rem;
  padding-bottom: 8rem;
  max-width: 50rem;          /* ~85 characters: comfortable for long prose */
}
[data-testid="stHeader"] { background: transparent; }

/* Prose rhythm. Technical explanations run long, and the Streamlit default
   line-height is tuned for dashboard labels rather than paragraphs. */
[data-testid="stChatMessage"] .stMarkdown p,
[data-testid="stChatMessage"] .stMarkdown li {
  line-height: 1.68;
}
[data-testid="stChatMessage"] .stMarkdown li + li { margin-top: 0.3rem; }

/* Keyboard focus. Streamlit's default ring is easy to lose against a dark
   surface; WCAG 2.2 SC 2.4.7 (Focus Visible) requires a visible indicator, and
   SC 2.4.13 sets out what an adequate one looks like. */
.stApp *:focus-visible {
  outline: 3px solid var(--ns-accent);
  outline-offset: 2px;
  border-radius: 6px;
}

/* SC 1.4.11 wants 3:1 for the visual information that identifies a control.
   Streamlit applies one border token to controls and to decorative containers
   alike, and pushing that token to 3:1 would box every expander and card in a
   heavy rule. The controls are therefore given the stronger colour directly,
   and the lighter token is left to the decorative edges, which are not what
   the criterion is about. */
[data-testid="stChatInput"],
[data-testid="stForm"],
.stTextInput input,
.stTextArea textarea,
.stSelectbox [data-baseweb="select"] > div {
  border-color: var(--ns-border-control) !important;
}

/* Masthead */
.stApp .ns-masthead { margin: 0 0 1.75rem; }
.stApp .ns-masthead__row {
  display: flex;
  align-items: center;
  gap: 0.95rem;
}
.stApp .ns-masthead__text { min-width: 0; flex: 1 1 auto; }
.stApp .ns-masthead__line {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  flex-wrap: wrap;
}

/* The mark carries its own dark rounded-square field, so it needs a hairline
   rather than a heavy container: on the dark theme the artwork nearly meets the
   page and the ring is what stops it dissolving into the background. */
.stApp .ns-mark {
  flex: 0 0 auto;
  display: block;
  border-radius: 13px;
  box-shadow:
    0 0 0 1px var(--ns-border),
    0 2px 10px rgba(0, 0, 0, 0.22);
}
.stApp .ns-mark--sm { border-radius: 8px; box-shadow: 0 0 0 1px var(--ns-border); }
.stApp .ns-masthead__title {
  font-size: 1.7rem;
  font-weight: 700;
  letter-spacing: -0.021em;
  color: var(--ns-text);
  /* Streamlit gives h1 a generous vertical padding meant for a page heading
     standing on its own. Here the heading sits in a row beside the mark, and
     that padding pushes it out of alignment with it. */
  margin: 0;
  padding: 0;
  line-height: 1.15;
}
.stApp .ns-masthead__sub {
  color: var(--ns-muted);
  font-size: 0.94rem;
  margin: 0.45rem 0 0;
  line-height: 1.55;
  max-width: 42rem;
}
.stApp .ns-scope {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.2rem 0.6rem;
  border: 1px solid var(--ns-border);
  border-radius: 999px;
  background: var(--ns-surface-2);
  color: var(--ns-muted);
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
}
.stApp .ns-rule {
  height: 1px;
  background: var(--ns-border);
  margin: 1.4rem 0 0;
}

/* Welcome panel */
.stApp .ns-hero {
  border: 1px solid var(--ns-border);
  border-radius: 14px;
  background: var(--ns-surface-2);
  padding: 1.3rem 1.4rem 1.4rem;
  margin: 0.25rem 0 1.1rem;
}
.stApp .ns-hero__lead {
  color: var(--ns-text);
  font-size: 0.97rem;
  line-height: 1.6;
  margin: 0 0 1.15rem;
}
.stApp .ns-hero__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: 0.9rem;
}
.stApp .ns-feature {
  border-top: 2px solid var(--ns-accent);
  padding-top: 0.6rem;
}
.stApp .ns-feature__title {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--ns-text);
  letter-spacing: -0.005em;
  margin: 0 0 0.25rem;
}
.stApp .ns-feature__body {
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--ns-muted);
  margin: 0;
}

/* Confidence chip */
.stApp .ns-band {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.24rem 0.62rem;
  border: 1px solid;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  line-height: 1.35;
  white-space: nowrap;
  vertical-align: middle;
}
.stApp .ns-band__marker { font-size: 0.78em; line-height: 1; }
.stApp .ns-band__label { letter-spacing: 0.002em; }

/* Signal-strength meter: a count of filled bars, so the ordinal position of
   the band is legible in greyscale and without the key. */
.stApp .ns-meter {
  display: inline-flex;
  align-items: flex-end;
  gap: 2px;
  height: 11px;
  margin-left: 0.1rem;
}
.stApp .ns-meter__seg {
  display: block;
  width: 3px;
  border: 1px solid currentColor;
  border-radius: 1px;
  background: transparent;
  opacity: 0.55;
}
.stApp .ns-meter__seg.is-on { background: currentColor; opacity: 1; }
.stApp .ns-meter__seg:nth-child(1) { height: 5px; }
.stApp .ns-meter__seg:nth-child(2) { height: 8px; }
.stApp .ns-meter__seg:nth-child(3) { height: 11px; }

/* Source cards */
.stApp .ns-source {
  border: 1px solid var(--ns-border);
  border-radius: 10px;
  background: var(--ns-surface-2);
  padding: 0.7rem 0.85rem 0.75rem;
  margin-bottom: 0.6rem;
}
.stApp .ns-source__head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}
.stApp .ns-week {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  color: var(--ns-accent);
  background: var(--ns-accent-soft);
  border-radius: 5px;
  padding: 0.12rem 0.4rem;
  white-space: nowrap;
}
.stApp .ns-source__topic {
  font-size: 0.86rem;
  font-weight: 600;
  color: var(--ns-text);
  flex: 1 1 auto;
  min-width: 0;
}
.stApp .ns-tag {
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  color: var(--ns-subtle);
  border: 1px solid var(--ns-border);
  border-radius: 5px;
  padding: 0.1rem 0.36rem;
  white-space: nowrap;
}
.stApp .ns-source__meta {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  font-size: 0.73rem;
  color: var(--ns-subtle);
  font-variant-numeric: tabular-nums;
}
.stApp .ns-rel {
  flex: 1 1 auto;
  height: 5px;
  min-width: 3rem;
  background: var(--ns-surface-3);
  border-radius: 3px;
  overflow: hidden;
}
.stApp .ns-rel__fill {
  display: block;
  height: 100%;
  background: var(--ns-accent);
  border-radius: 3px;
}

/* Native <details> rather than a nested st.expander, which Streamlit forbids.
   It is keyboard operable and screen-reader announced without extra ARIA. */
.stApp .ns-source details { margin-top: 0.6rem; }
.stApp .ns-source summary {
  cursor: pointer;
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--ns-accent);
  list-style: none;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.1rem 0;
}
.stApp .ns-source summary::-webkit-details-marker { display: none; }
.stApp .ns-source summary::before {
  content: "\\25B8";
  font-size: 0.8em;
  transition: transform 0.15s ease;
}
.stApp .ns-source details[open] summary::before { transform: rotate(90deg); }
.stApp .ns-excerpt {
  margin: 0.5rem 0 0;
  padding: 0.15rem 0 0.15rem 0.75rem;
  border-left: 2px solid var(--ns-border-strong);
  font-size: 0.82rem;
  line-height: 1.6;
  color: var(--ns-muted);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 15rem;
  overflow-y: auto;
}

/* Prerequisite review

   One card per question answered incorrectly. The chosen answer and the
   correct answer are separated by hue, glyph, coloured rule and text label,
   so which is which is legible at a glance and still legible without colour. */
.stApp .ns-review {
  border: 1px solid var(--ns-border);
  border-radius: 10px;
  background: var(--ns-surface-2);
  padding: 0.8rem 0.9rem 0.85rem;
  margin-bottom: 0.7rem;
}
.stApp .ns-review:last-child { margin-bottom: 0.2rem; }
.stApp .ns-review__q {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  font-size: 0.9rem;
  font-weight: 600;
  line-height: 1.5;
  color: var(--ns-text);
  margin: 0 0 0.65rem;
}
.stApp .ns-review__n {
  flex: 0 0 auto;
  min-width: 1.35rem;
  height: 1.35rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--ns-surface-3);
  border: 1px solid var(--ns-border);
  color: var(--ns-muted);
  font-size: 0.72rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.stApp .ns-review__row {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  border-left: 3px solid;
  border-radius: 0 6px 6px 0;
  padding: 0.4rem 0.6rem;
  margin-bottom: 0.35rem;
  font-size: 0.84rem;
  line-height: 1.5;
}
.stApp .ns-review__mark {
  flex: 0 0 auto;
  font-weight: 700;
  line-height: 1.5;
}
.stApp .ns-review__text { min-width: 0; }
/* The option text inherits the row colour; the label prefix carries the same
   hue at full weight so the pairing survives if the tint is lost in print. */
.stApp .ns-review__text strong { font-weight: 700; }
.stApp .ns-review__why {
  margin: 0.6rem 0 0;
  padding-left: 0.7rem;
  border-left: 2px solid var(--ns-border-strong);
  font-size: 0.82rem;
  line-height: 1.6;
  color: var(--ns-muted);
}

/* Quiz

   The results review deliberately reuses .ns-review above rather than
   introducing a second visual language for "you got this wrong and here is
   why". A student who has met the prerequisite probe already knows how to
   read it. */
.stApp .ns-quiz-eyebrow {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--ns-subtle);
  margin: 0 0 0.35rem;
}
.stApp .ns-quiz-q {
  font-size: 1.06rem;
  font-weight: 600;
  line-height: 1.5;
  color: var(--ns-text);
  margin: 0 0 0.2rem;
}

/* Thin progress rule under the question count. Position is the only channel
   here, but it is decorative: the "Question 3 of 10" label carries the same
   information in words directly above it. */
.stApp .ns-progress {
  height: 4px;
  width: 100%;
  background: var(--ns-surface-3);
  border-radius: 2px;
  overflow: hidden;
  margin: 0.2rem 0 1rem;
}
.stApp .ns-progress__fill {
  display: block;
  height: 100%;
  background: var(--ns-accent);
  border-radius: 2px;
}

.stApp .ns-timer {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.22rem 0.6rem;
  border-radius: 999px;
  border: 1px solid;
  font-size: 0.82rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
/* Running low is signalled by the word "left" changing to a warning label and
   by the band marker, not by colour alone. */
.stApp .ns-timer__mark { font-size: 0.8em; }

.stApp .ns-result {
  border: 1px solid var(--ns-border);
  border-radius: 14px;
  background: var(--ns-surface-2);
  padding: 1.2rem 1.3rem;
  margin-bottom: 1rem;
  text-align: center;
}
.stApp .ns-result__score {
  font-size: 2.6rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.05;
  margin: 0;
}
.stApp .ns-result__of {
  font-size: 0.95rem;
  color: var(--ns-muted);
  margin: 0.3rem 0 0.7rem;
}
.stApp .ns-result__bar {
  height: 10px;
  width: 100%;
  max-width: 22rem;
  margin: 0 auto;
  background: var(--ns-surface-3);
  border: 1px solid var(--ns-border);
  border-radius: 5px;
  overflow: hidden;
}
.stApp .ns-result__fill { display: block; height: 100%; }

/* Completed quiz attempts, listed under the start button. Each row leads with
   its score so the column of percentages can be scanned down without reading
   the rest, which is what a history is for. */
.stApp .ns-hist {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--ns-border);
  border-radius: 8px;
  background: var(--ns-surface-2);
  margin-bottom: 0.35rem;
  font-size: 0.8rem;
}
.stApp .ns-hist__score {
  flex: 0 0 auto;
  min-width: 3.6rem;
  text-align: center;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  border: 1px solid;
  border-radius: 6px;
  padding: 0.1rem 0.35rem;
}
.stApp .ns-hist__meta {
  color: var(--ns-muted);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.stApp .ns-hist__when {
  margin-left: auto;
  flex: 0 0 auto;
  color: var(--ns-subtle);
  font-size: 0.74rem;
  font-variant-numeric: tabular-nums;
}
.stApp .ns-hist-summary {
  display: flex;
  gap: 1.2rem;
  flex-wrap: wrap;
  margin: 0.55rem 0 0.2rem;
  font-size: 0.78rem;
  color: var(--ns-muted);
}
.stApp .ns-hist-summary b {
  color: var(--ns-text);
  font-variant-numeric: tabular-nums;
}

.stApp .ns-quiz-note {
  font-size: 0.76rem;
  line-height: 1.5;
  color: var(--ns-subtle);
  border-left: 2px solid var(--ns-border-strong);
  padding-left: 0.7rem;
  margin: 0.9rem 0 0;
}
.stApp .ns-setup-label {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--ns-text);
  margin: 0.9rem 0 0.3rem;
}
.stApp .ns-setup-hint {
  font-size: 0.76rem;
  line-height: 1.45;
  color: var(--ns-muted);
  margin: 0 0 0.4rem;
}

/* Checkpoint (prerequisite probe) */
.stApp .ns-checkpoint {
  border: 1px solid var(--ns-border);
  border-left: 3px solid var(--ns-accent);
  border-radius: 10px;
  background: var(--ns-surface-2);
  padding: 0.85rem 1rem;
  margin-bottom: 0.85rem;
}
.stApp .ns-checkpoint__eyebrow {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--ns-accent);
  margin: 0 0 0.35rem;
}
.stApp .ns-checkpoint__body {
  font-size: 0.92rem;
  line-height: 1.55;
  color: var(--ns-text);
  margin: 0;
}
.stApp .ns-qcount {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ns-subtle);
  margin: 0 0 0.2rem;
}

/* Sidebar */
[data-testid="stSidebarUserContent"] { padding-top: 1.25rem; }
.stApp .ns-side-head {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.4rem;
}
.stApp .ns-side-title {
  font-size: 0.98rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--ns-text);
  margin: 0;
}
.stApp .ns-side-sub {
  font-size: 0.76rem;
  line-height: 1.5;
  color: var(--ns-muted);
  margin: 0 0 0.2rem;
}
.stApp .ns-section {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--ns-subtle);
  margin: 1.35rem 0 0.55rem;
}
.stApp .ns-stat {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.2rem 0;
  font-size: 0.8rem;
}
.stApp .ns-stat__label { color: var(--ns-muted); }
.stApp .ns-stat__value {
  color: var(--ns-text);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.stApp .ns-mix {
  display: flex;
  height: 14px;
  width: 100%;
  border-radius: 4px;
  overflow: hidden;
  margin: 0.45rem 0 0.15rem;
  border: 1px solid var(--ns-border);
}
.stApp .ns-mix__seg {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.58rem;
  color: var(--ns-bg);
  line-height: 1;
}
.stApp .ns-chips { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-top: 0.15rem; }
.stApp .ns-chip {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--ns-muted);
  background: var(--ns-surface-2);
  border: 1px solid var(--ns-border);
  border-radius: 5px;
  padding: 0.12rem 0.4rem;
  white-space: nowrap;
}
.stApp .ns-key {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.22rem 0;
  font-size: 0.79rem;
}
.stApp .ns-key__name { font-weight: 600; }
.stApp .ns-key__note { color: var(--ns-subtle); font-size: 0.73rem; }
.stApp .ns-prereq {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.79rem;
  padding: 0.2rem 0;
  color: var(--ns-text);
}
.stApp .ns-prereq__state { color: var(--ns-subtle); font-size: 0.73rem; }
.stApp .ns-note {
  font-size: 0.72rem;
  line-height: 1.5;
  color: var(--ns-subtle);
  margin: 0.5rem 0 0;
}

/* Widgets */
.stButton > button {
  font-weight: 500;
  transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}
[data-testid="stBaseButton-secondary"]:hover {
  border-color: var(--ns-accent);
  color: var(--ns-accent);
}
/* Archived conversations and follow-up chips read as lists, not as buttons
   competing with the primary action, so their labels are left-aligned. */
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
  justify-content: flex-start;
  text-align: left;
  font-size: 0.8rem;
  padding-top: 0.3rem;
  padding-bottom: 0.3rem;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] p {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

[data-testid="stExpander"] summary { font-size: 0.84rem; font-weight: 600; }
[data-testid="stExpander"] details { border-radius: 10px; }

[data-testid="stChatInput"] { border-radius: 12px; }
[data-testid="stBottomBlockContainer"] { padding-bottom: 1.25rem; }

/* User turns read as quoted input; assistant turns carry the page background so
   the answer, which is the primary content, is not boxed in. */
[data-testid="stChatMessage"] { background: transparent; padding: 0.4rem 0 0.5rem; }
.stChatMessage:has([data-testid="stChatMessageAvatarUser"]) {
  background: var(--ns-surface-2);
  border: 1px solid var(--ns-border);
  border-radius: 12px;
  padding: 0.6rem 0.9rem;
  margin-bottom: 0.4rem;
}

/* Alerts sit inside chat turns; the default margin double-spaces them there. */
[data-testid="stChatMessage"] [data-testid="stAlert"] { margin-bottom: 0.5rem; }

/* Motion and print */
@media (prefers-reduced-motion: reduce) {
  .stApp *, .stApp *::before, .stApp *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}

/* Screenshots of the interface are reproduced in the dissertation, which is
   marked in greyscale. Backgrounds are dropped so the chip is carried by its
   border, marker and meter, all of which survive desaturation. */
@media print {
  .stApp .ns-band { background: transparent !important; border-width: 1.5px; }
  .stApp .ns-source, .stApp .ns-hero, .stApp .ns-checkpoint { break-inside: avoid; }
  [data-testid="stSidebar"] { display: none; }
}
</style>
""")


def inject_css() -> None:
    """Emit the stylesheet for the active theme. Call once, early in main()."""
    st.markdown(_CSS.substitute(tokens()), unsafe_allow_html=True)


'''References

Tol, P. (2021). Colour schemes. SRON Technical Note SRON/EPS/TN/09-002.
https://personal.sron.nl/~pault/
-Source of the high-contrast qualitative palette used for the confidence
bands, selected for separability under all three forms of colour vision
deficiency and under greyscale conversion.

World Health Organization (2023). Blindness and vision impairment: colour
blindness.
-Prevalence figures motivating the redundant encoding of the bands.

W3C (2023). Web Content Accessibility Guidelines (WCAG) 2.2.
-SC 1.4.1 Use of Colour: satisfied by the marker, label and meter.
-SC 1.4.3 Contrast (Minimum), 4.5:1 for body text: motivates the
per-theme colour variants, the darkened Low band and the darkened
light-theme subtle text.
-SC 1.4.11 Non-text Contrast, 3:1 for controls: motivates border_control.
-SC 2.4.7 Focus Visible: motivates the focus ring.
'''
