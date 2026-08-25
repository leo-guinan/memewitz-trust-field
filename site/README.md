# Picture-book publisher

The public picture book is generated from the canonical `101_THINGS_BEFORE_BUYING_THE_DEX.md` source and the 101 reviewed collection images.

Build locally:

```bash
python3 site/build.py
python3 -m http.server 4173 --directory public
```

The generated `public/` directory is the only deployment artifact. It is intentionally not mixed with the repository's research receipts.
