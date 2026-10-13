"""Render social preview and PNG icons for widest crawler/browser compatibility."""
from pathlib import Path
import cairosvg

root = Path(__file__).resolve().parent / "docs"
cairosvg.svg2png(url=str(root / "social-card.svg"),write_to=str(root / "social-card.png"),output_width=1200,output_height=630)
cairosvg.svg2png(url=str(root / "favicon.svg"),write_to=str(root / "apple-touch-icon.png"),output_width=180,output_height=180)
cairosvg.svg2png(url=str(root / "favicon.svg"),write_to=str(root / "favicon-32.png"),output_width=32,output_height=32)
print("Rendered social-card.png, apple-touch-icon.png, favicon-32.png")
