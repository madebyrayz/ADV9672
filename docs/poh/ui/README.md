# shared/ui

Interface files common to every week.

The typeface is TWK Lausanne, licensed to the author, so the font files are not
committed. They load from an installed copy when there is one, and fall back to
the system sans when there is not. To restore the local copies:

```bash
cp ~/Library/Fonts/TWKLausanne-{400,400Italic,500,600,700}.woff2 shared/ui/fonts/
```
