#!/usr/bin/env python3
"""
Erstellt ein realistisches Test-PDF wie aus Word exportiert:
- Echter Text (extrahierbar via pypdf)
- Echte eingebettete Bilder (Diagramme/Screenshots)
- Seite 1: Nur Text
- Seite 2: Nur Text
- Seite 3: Text, dann Bild, dann wieder Text (gemischt auf einer Seite)
- Seite 4: Dominantes Bild (mit etwas Text drumherum)

Das PDF hat einen echten Text-Layer + XObject-Bilder.
Perfekt zum Testen der verbesserten Bild-Erkennung (_is_meaningful_image)
und des Vision-OCR-Flows für mixed content.

Voraussetzungen:
  pip install fpdf2 pillow

Ausführen:
  python create_mixed_hybrid_test_pdf.py

Die Datei wird als test_mixed_hybrid.pdf im aktuellen Verzeichnis gespeichert.
Danach einfach in den Zielordner auf G: kopieren.
"""

import io
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF


def get_font(size=18):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()


def create_flowchart_image(width=520, height=280) -> bytes:
    """Ein typisches Diagramm / Screenshot-ähnliches Bild."""
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # Rahmen
    draw.rectangle([5, 5, width-5, height-5], outline="#333333", width=2)

    # Boxen + Pfeile (wie in echten Dokumenten)
    boxes = [
        (30, 30, "Start / Eingang"),
        (30, 110, "Verarbeitung\nSchritt 1"),
        (200, 110, "Entscheidung"),
        (370, 110, "Schritt 2"),
        (200, 200, "Ergebnis / Ausgabe"),
    ]

    font = get_font(14)
    for x, y, text in boxes:
        draw.rectangle([x, y, x+140, y+55], outline="#1a73e8", width=2, fill="#e8f0fe")
        lines = text.split("\n")
        for i, line in enumerate(lines):
            draw.text((x + 10, y + 12 + i*18), line, fill="#202124", font=font)

    # Pfeile
    draw.line([100, 85, 100, 110], fill="#333", width=2)
    draw.polygon([(95, 105), (105, 105), (100, 115)], fill="#333")

    draw.line([170, 137, 200, 137], fill="#333", width=2)
    draw.polygon([(195, 132), (195, 142), (205, 137)], fill="#333")

    draw.line([340, 137, 370, 137], fill="#333", width=2)
    draw.polygon([(365, 132), (365, 142), (375, 137)], fill="#333")

    draw.line([440, 165, 440, 200], fill="#333", width=2)
    draw.polygon([(435, 195), (445, 195), (440, 205)], fill="#333")

    draw.line([270, 255, 270, 275], fill="#333", width=2)  # dummy

    # Kleiner Text unten
    draw.text((20, height - 25), "Abb. 1: Typischer Prozess mit Verzweigung", fill="#5f6368", font=get_font(11))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def create_screenshot_like_image(width=520, height=220) -> bytes:
    """Ein weiteres Bild, z.B. UI-Screenshot oder Tabelle."""
    img = Image.new("RGB", (width, height), "#f8f9fa")
    draw = ImageDraw.Draw(img)

    # Fenster-Rahmen
    draw.rectangle([10, 10, width-10, height-10], outline="#dadce0", width=1, fill="white")

    # Titelzeile
    draw.rectangle([10, 10, width-10, 40], fill="#1a73e8")
    draw.text((20, 15), "Beispiel: Tabelle oder UI-Ausschnitt", fill="white", font=get_font(13))

    # Tabellen-ähnliche Inhalte
    font = get_font(12)
    y = 55
    for i, row in enumerate(["Kunde", "Betrag", "Status", "Datum"], 1):
        draw.text((25, y), f"{i}. {row}", fill="#202124", font=font)
        y += 22

    draw.line([20, 52, width-20, 52], fill="#dadce0", width=1)
    draw.line([20, y+5, width-20, y+5], fill="#dadce0", width=1)

    # Kleines Diagramm-Element
    draw.rectangle([320, 60, 490, 180], outline="#34a853", width=2, fill="#e6f4ea")
    draw.text((330, 70), "Umsatz-Trend", fill="#1e8e3e", font=get_font(11))
    # Balken
    for i, h in enumerate([40, 75, 55, 110, 90]):
        x = 340 + i * 28
        draw.rectangle([x, 175-h, x+18, 175], fill="#34a853")

    draw.text((20, height - 30), "Abb. 2: Ergänzende Grafik / Screenshot", fill="#5f6368", font=get_font(11))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def create_pdf():
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Seite 1: Nur Text (mehrere Absätze)
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, "Seite 1 - Nur Text\n\n")
    for i in range(6):
        text = (
            f"Absatz {i+1}: Dies ist ein Beispieltext, wie er in Word geschrieben und dann als PDF exportiert wird. "
            "Er enthält mehrere Sätze, um einen realistischen Textfluss zu erzeugen. "
            "Es gibt keine Bilder auf dieser Seite. Der Text sollte vollständig extrahierbar sein."
        )
        pdf.multi_cell(0, 6, text + "\n\n")

    # Seite 2: Nur Text (etwas anders)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, "Seite 2 - Nur Text (Fortsetzung)\n\n")
    for i in range(5):
        text = (
            f"Weiterer Absatz {i+1}: Hier geht der Text weiter. In einem echten Dokument würde man hier "
            "Richtlinien, Tabellenbeschreibungen oder Erklärungen finden. "
            "Wieder kein Bild - nur Text. Ziel ist es, zu prüfen, ob der Text-Layer korrekt erhalten bleibt."
        )
        pdf.multi_cell(0, 6, text + "\n\n")

    # Seite 3: Text - Bild - Text (gemischt auf einer Seite)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, "Seite 3 - Text, dann Bild, dann wieder Text\n\n")
    pdf.multi_cell(0, 6,
        "Erster Textabschnitt auf dieser Seite. Hier wird erklärt, worum es geht, bevor das Bild kommt. "
        "Der Text sollte extrahierbar bleiben, während das folgende Bild separat erkannt und optional per Vision-OCR verarbeitet werden kann.\n\n"
    )

    # Bild 1 einfügen
    img1 = create_flowchart_image()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(img1)
        tmp_path = tmp.name
    pdf.image(tmp_path, x=25, w=160)
    Path(tmp_path).unlink(missing_ok=True)

    pdf.ln(8)
    pdf.multi_cell(0, 6,
        "Text nach dem Bild: Hier wird die Bedeutung des Diagramms erklärt. "
        "In einem realen Dokument stehen hier oft Erläuterungen, Hinweise oder Fortsetzungen des Textes. "
        "Dies testet die Fähigkeit, Text vor und nach einem Bild korrekt zu extrahieren und das Bild als separates Element zu behandeln.\n\n"
    )

    # Seite 4: Dominantes Bild (mit etwas Text)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, "Seite 4 - Hauptsächlich Bild (mit erklärendem Text)\n\n")

    img2 = create_screenshot_like_image()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(img2)
        tmp_path = tmp.name
    pdf.image(tmp_path, x=25, w=160)
    Path(tmp_path).unlink(missing_ok=True)

    pdf.ln(6)
    pdf.multi_cell(0, 6,
        "Dieser kurze Text steht unter dem Bild und beschreibt es. "
        "Auf dieser Seite dominiert das Bild, der Text ist nur ergänzend. "
        "Gut geeignet, um zu testen, ob ein 'nur Bild'-Seite korrekt als bildlastig erkannt wird."
    )

    out_path = Path("test_mixed_hybrid.pdf").resolve()
    pdf.output(str(out_path))
    print(f"Test-PDF erstellt: {out_path}")
    print("Struktur:")
    print("  Seite 1: Nur Text (mehrere Absätze)")
    print("  Seite 2: Nur Text (Fortsetzung)")
    print("  Seite 3: Text → Bild (Flowchart) → Text (gemischt auf einer Seite)")
    print("  Seite 4: Bild-dominant + erklärender Text")
    print("\nDas PDF hat echten Text-Layer + eingebettete Bilder.")
    print("Ideal zum Testen von Text-Extraktion + selektiver Vision-OCR.")


if __name__ == "__main__":
    create_pdf()
