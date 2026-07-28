# Repository Cleanup Design

## Objective

Keep one authoritative manuscript and the complete reproducibility record while
removing only regenerated QA output, build caches, and superseded publication
artifacts.

## Retention boundary

The cleanup retains all source code, tests, public manifests, protocol files,
annotation guidance, plans, design specifications, aggregate tables and
figures. It also retains ignored local research evidence under
`artifacts/private/` and the machine-specific `configs/local.yaml`.

## Deletion boundary

The cleanup removes explicitly enumerated DOCX QA render directories,
LibreOffice temporary directories, Python caches, package metadata, the
ignored `tmp/` directory, and the superseded tracked manuscript
`output/word/When_Does_Evidence_Expansion_Help.docx`.

## Documentation changes

`README.md` will describe the completed Pilot, its NO-GO outcome, the current
manuscript, and the current verification commands. `.gitignore` will prevent
future Word lock files and manuscript QA directories from appearing as
untracked changes.

## Validation

After cleanup, the repository must retain the revised Word manuscript, pass the
full test suite, pass configuration and privacy checks, contain no tracked
private data, and show no unexpected untracked files.
