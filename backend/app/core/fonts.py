from pathlib import Path
import re

import matplotlib
from matplotlib import font_manager


_REGISTERED = False

SERIF_FONTS = [
    "Times New Roman",
    "Tinos",
    "Liberation Serif",
    "Nimbus Roman",
    "DejaVu Serif",
]

CJK_FONTS = [
    "Noto Serif CJK SC",
    "Noto Sans CJK SC",
    "Microsoft YaHei",
    "SimHei",
    "WenQuanYi Micro Hei",
    "Arial Unicode MS",
    "DejaVu Sans",
]

_CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


def register_project_fonts() -> set[str]:
    global _REGISTERED
    font_dir = Path(__file__).resolve().parents[1] / "fonts"
    if not _REGISTERED and font_dir.exists():
        for font_path in list(font_dir.glob("*.ttf")) + list(font_dir.glob("*.ttc")) + list(font_dir.glob("*.otf")):
            try:
                font_manager.fontManager.addfont(str(font_path))
            except Exception:
                pass
    _REGISTERED = True
    return {font.name for font in font_manager.fontManager.ttflist}


def configure_matplotlib_fonts(font_family: str = "Times New Roman", pdf_fonttype: int = 3):
    available = register_project_fonts()

    preferred = [font_family] if font_family else []
    preferred.extend(SERIF_FONTS)
    serif = []
    for name in preferred:
        if name and name not in serif:
            serif.append(name)

    selected_serif = next((name for name in serif if name in available), "DejaVu Serif")
    cjk = [name for name in CJK_FONTS if name in available]
    family_stack = [selected_serif] + [name for name in serif if name != selected_serif] + cjk

    matplotlib.rcParams.update({
        "font.family": family_stack,
        "font.serif": family_stack,
        "font.sans-serif": cjk + family_stack,
        "mathtext.fontset": "custom",
        "mathtext.rm": selected_serif,
        "mathtext.it": selected_serif,
        "mathtext.bf": selected_serif,
        "axes.unicode_minus": False,
        "pdf.fonttype": pdf_fonttype,
        "ps.fonttype": pdf_fonttype,
        "svg.fonttype": "none",
    })
    return selected_serif


def apply_font_to_figure(fig, font_family: str = "Times New Roman"):
    selected = configure_matplotlib_fonts(font_family)
    available = register_project_fonts()
    selected_cjk = next((name for name in CJK_FONTS if name in available), selected)
    for text in fig.findobj(match=matplotlib.text.Text):
        content = text.get_text() or ""
        text.set_fontfamily(selected_cjk if _CJK_RE.search(content) else selected)
    return selected
