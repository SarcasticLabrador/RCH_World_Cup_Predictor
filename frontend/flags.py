"""Team emoji flags, SVG URLs and group mappings for the 2026 World Cup."""
from __future__ import annotations

FLAGS: dict[str, str] = {
    "Mexico": "🇲🇽", "South Korea": "🇰🇷", "Czechia": "🇨🇿", "South Africa": "🇿🇦",
    "Canada": "🇨🇦", "Bosnia & Herzegovina": "🇧🇦", "Qatar": "🇶🇦", "Switzerland": "🇨🇭",
    "Brazil": "🇧🇷", "Morocco": "🇲🇦", "Haiti": "🇭🇹", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "USA": "🇺🇸", "Paraguay": "🇵🇾", "Australia": "🇦🇺", "Turkiye": "🇹🇷",
    "Germany": "🇩🇪", "Curacao": "🇨🇼", "Ivory Coast": "🇨🇮", "Ecuador": "🇪🇨",
    "Netherlands": "🇳🇱", "Japan": "🇯🇵", "Sweden": "🇸🇪", "Tunisia": "🇹🇳",
    "Belgium": "🇧🇪", "Egypt": "🇪🇬", "Iran": "🇮🇷", "New Zealand": "🇳🇿",
    "Spain": "🇪🇸", "Cape Verde": "🇨🇻", "Saudi Arabia": "🇸🇦", "Uruguay": "🇺🇾",
    "France": "🇫🇷", "Senegal": "🇸🇳", "Iraq": "🇮🇶", "Norway": "🇳🇴",
    "Argentina": "🇦🇷", "Algeria": "🇩🇿", "Austria": "🇦🇹", "Jordan": "🇯🇴",
    "Portugal": "🇵🇹", "DR Congo": "🇨🇩", "Uzbekistan": "🇺🇿", "Colombia": "🇨🇴",
    "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Croatia": "🇭🇷", "Ghana": "🇬🇭", "Panama": "🇵🇦",
}

# SVG flag URLs from flagcdn.com — matches what is stored in the teams.flag_url column.
FLAG_URLS: dict[str, str] = {
    "Mexico": "https://flagcdn.com/mx.svg",
    "South Korea": "https://flagcdn.com/kr.svg",
    "Czechia": "https://flagcdn.com/cz.svg",
    "South Africa": "https://flagcdn.com/za.svg",
    "Canada": "https://flagcdn.com/ca.svg",
    "Bosnia & Herzegovina": "https://flagcdn.com/ba.svg",
    "Qatar": "https://flagcdn.com/qa.svg",
    "Switzerland": "https://flagcdn.com/ch.svg",
    "Brazil": "https://flagcdn.com/br.svg",
    "Morocco": "https://flagcdn.com/ma.svg",
    "Haiti": "https://flagcdn.com/ht.svg",
    "Scotland": "https://flagcdn.com/gb-sct.svg",
    "USA": "https://flagcdn.com/us.svg",
    "Paraguay": "https://flagcdn.com/py.svg",
    "Australia": "https://flagcdn.com/au.svg",
    "Turkiye": "https://flagcdn.com/tr.svg",
    "Germany": "https://flagcdn.com/de.svg",
    "Curacao": "https://flagcdn.com/cw.svg",
    "Ivory Coast": "https://flagcdn.com/ci.svg",
    "Ecuador": "https://flagcdn.com/ec.svg",
    "Netherlands": "https://flagcdn.com/nl.svg",
    "Japan": "https://flagcdn.com/jp.svg",
    "Sweden": "https://flagcdn.com/se.svg",
    "Tunisia": "https://flagcdn.com/tn.svg",
    "Belgium": "https://flagcdn.com/be.svg",
    "Egypt": "https://flagcdn.com/eg.svg",
    "Iran": "https://flagcdn.com/ir.svg",
    "New Zealand": "https://flagcdn.com/nz.svg",
    "Spain": "https://flagcdn.com/es.svg",
    "Cape Verde": "https://flagcdn.com/cv.svg",
    "Saudi Arabia": "https://flagcdn.com/sa.svg",
    "Uruguay": "https://flagcdn.com/uy.svg",
    "Senegal": "https://flagcdn.com/sn.svg",
    "Iraq": "https://flagcdn.com/iq.svg",
    "Norway": "https://flagcdn.com/no.svg",
    "Argentina": "https://flagcdn.com/ar.svg",
    "Algeria": "https://flagcdn.com/dz.svg",
    "Austria": "https://flagcdn.com/at.svg",
    "Jordan": "https://flagcdn.com/jo.svg",
    "Portugal": "https://flagcdn.com/pt.svg",
    "DR Congo": "https://flagcdn.com/cd.svg",
    "Uzbekistan": "https://flagcdn.com/uz.svg",
    "Colombia": "https://flagcdn.com/co.svg",
    "England": "https://flagcdn.com/gb-eng.svg",
    "Croatia": "https://flagcdn.com/hr.svg",
    "Ghana": "https://flagcdn.com/gh.svg",
    "Panama": "https://flagcdn.com/pa.svg",
}

GROUP_MAP: dict[str, str] = {
    "Mexico": "A", "South Korea": "A", "Czechia": "A", "South Africa": "A",
    "Canada": "B", "Bosnia & Herzegovina": "B", "Qatar": "B", "Switzerland": "B",
    "Brazil": "C", "Morocco": "C", "Haiti": "C", "Scotland": "C",
    "USA": "D", "Paraguay": "D", "Australia": "D", "Turkiye": "D",
    "Germany": "E", "Curacao": "E", "Ivory Coast": "E", "Ecuador": "E",
    "Netherlands": "F", "Japan": "F", "Sweden": "F", "Tunisia": "F",
    "Belgium": "G", "Egypt": "G", "Iran": "G", "New Zealand": "G",
    "Spain": "H", "Cape Verde": "H", "Saudi Arabia": "H", "Uruguay": "H",
    "France": "I", "Senegal": "I", "Iraq": "I", "Norway": "I",
    "Argentina": "J", "Algeria": "J", "Austria": "J", "Jordan": "J",
    "Portugal": "K", "DR Congo": "K", "Uzbekistan": "K", "Colombia": "K",
    "England": "L", "Croatia": "L", "Ghana": "L", "Panama": "L",
}


def get_flag(team_name: str | None) -> str:
    if not team_name:
        return "🏳"
    return FLAGS.get(team_name, "🏳")


def get_flag_img(team_name: str | None, height: int = 18) -> str:
    """Return an HTML <img> tag for the team's SVG flag, or empty string if unknown."""
    if not team_name:
        return ""
    url = FLAG_URLS.get(team_name)
    if not url:
        return ""
    return (
        f'<img src="{url}" '
        f'style="height:{height}px;vertical-align:middle;'
        f'border-radius:2px;margin-right:4px">'
    )
