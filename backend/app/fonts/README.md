# Optional local fonts

The backend automatically loads `.ttf`, `.ttc`, and `.otf` files from this directory before drawing Matplotlib figures.

Times New Roman is a proprietary Microsoft font, so it is not committed to this repository. If you have a valid license and want exact Times New Roman output on Linux servers, place the font files here before building:

- `times.ttf`
- `timesbd.ttf`
- `timesi.ttf`
- `timesbi.ttf`

Without these files, Docker installs open Linux alternatives and the backend uses Tinos/Liberation Serif as the Times-compatible fallback, plus Noto CJK to avoid Chinese square boxes.
