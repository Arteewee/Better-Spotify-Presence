import re


def clean_title(title: str) -> str:
    """
    Bersihkan judul lagu Spotify
    agar lebih mudah dicari di LRCLIB.
    """

    patterns = [
        r"\(.*?remaster.*?\)",
        r"\(.*?live.*?\)",
        r"\(.*?version.*?\)",
        r"\(feat\..*?\)",
        r"\(ft\..*?\)",
        r"\[.*?remaster.*?\]",
        r"\[.*?live.*?\]",
        r"\[.*?version.*?\]",
        r"\- Remastered.*",
        r"\- Live.*",
        r"\- Radio Edit.*",
        r"\- Extended.*"
    ]

    result = title

    for pattern in patterns:

        result = re.sub(
            pattern,
            "",
            result,
            flags=re.IGNORECASE
        )

    return result.strip()


def format_time(ms: int):

    total = int(ms / 1000)

    minute = total // 60

    second = total % 60

    return f"{minute:02}:{second:02}"