# ADV9672

Coursework repository. One folder per weekly artifact, one shared interface shell,
one set of conventions so a week can be picked up months later and still run.

## Weeks

| # | Artifact | Question | Set reading |
|---|---|---|---|
| 02 | [The Post-Original Holbein](week-02-post-original-holbein/) | Where must you stand for the skull in Holbein's *The Ambassadors* to resolve, and does a monocular reconstruction model put its best viewpoint anywhere near the geometric answer? | Benjamin, Baudrillard, Davis |

## Layout

```
ADV9672/
├── shared/ui/                     interface shell reused by every week
│   ├── tokens.css                 typeface, type scale, weight, spacing
│   ├── shadcn.css                 components
│   └── fonts/                     not committed, see shared/ui/README.md
└── week-NN-<slug>/
    ├── README.md                  what it is, how to run it, what it found
    ├── writing/                   the essay, in Markdown
    ├── <study>/                   scripts, figures, measurements
    └── <app>/                     the prototype, if the week has one
```

## Conventions

- A week is self-contained apart from `shared/ui/`. Nothing reaches sideways into another week.
- Measurements live beside the code that produced them. Every figure is regenerable from a script in the week folder; none are hand-edited.
- Large reconstruction output (`.ply`, `.splat`, scored render sets) is excluded. The metadata beside it is committed, because that is what the figures and the app actually read.
- The essay is written in Markdown and mirrored into the app, not the other way round.
