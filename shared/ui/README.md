# shared/ui

The interface shell. A weekly artifact styles itself by overriding tokens, not by
rewriting components, so the site design does not have to be reinvented each week.

## Files

| File | Contents |
|---|---|
| `tokens.css` | `@font-face` declarations, type scale, weights, leading, tracking, spacing, measure |
| `shadcn.css` | Components: buttons, badges, inputs, tabs, dialog, switch, table, toast |
| `fonts/` | woff2 subset — **not committed**, see below |

## Using it

Load in this order. Tokens come after the components so a token override wins:

```html
<link rel="stylesheet" href="/ui/shadcn.css" />
<link rel="stylesheet" href="/ui/tokens.css" />
<link rel="stylesheet" href="your-artifact.css" />
```

Then reference tokens rather than literals:

```css
.thing { font-size: var(--text-lg); font-weight: var(--weight-medium); letter-spacing: var(--tracking-snug); }
```

## Typeface

TWK Lausanne, by Nizar Kazan for TYPE.WELTKERN®. Licensed to the author for
personal use, which does not extend to this repository, so the font files are
gitignored.

`tokens.css` tries `local()` first, so on a machine with the family installed
nothing is downloaded and the page renders correctly with no `fonts/` directory
at all. On a machine without it the stack falls back to the system sans.

To restore the local copies on a machine that has the family installed:

```bash
cp ~/Library/Fonts/TWKLausanne-{400,400Italic,500,600,700}.woff2 shared/ui/fonts/
```

Four weights and one italic are used. The family ships 50–1000; the subset is
deliberate, since each additional face is another request for a hierarchy that
four weights already carry.
