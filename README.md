# ADV 9672

Coursework for ADV 9672 at the Harvard Graduate School of Design, fall 2026.
Each week gets a folder here and a page on the site.

Site: **[madebyrayz.github.io/adv9672](https://madebyrayz.github.io/adv9672/)**

## Weeks

| Week | Page | What it asks |
| --- | --- | --- |
| 02 | [The Post-Original Holbein](week-02/) | Where you have to stand for the skull in *The Ambassadors* to resolve, and whether a single-image reconstruction model (Apple's SHARP) puts its best viewpoint anywhere near that spot. |

## Layout

```
week-02/      source for that week: the essay, the study, the app
shared/ui/    CSS tokens and components every week shares
docs/         the published site, one folder per week. GitHub Pages serves it from main.
tools/        build_static.py turns a week's app into static files under docs/
```

## Publishing

```bash
python3 tools/build_static.py      # rebuilds docs/week-02/
git add docs && git commit -m "Publish week 2"
git push
```

Pages picks the commit up within a minute or two. `docs/index.html` is written by
hand; add a row there when a new week goes up.

## Notes

- `ml-sharp/` and `splat-viewer/` are clones of Apple's SHARP and antimatter15's
  splat viewer. They are not committed; `week-02/README.md` has the clone commands.
- TWK Lausanne is licensed to me, so the font files stay out of the repo. The site
  falls back to the system sans when they are missing.
- Run any week's app with the commands in that week's README.
