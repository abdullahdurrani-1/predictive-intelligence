# Data

## `raw/` — original NASA files, never edited

Contents: the four C-MAPSS subsets (`train_`, `test_`, `RUL_` for FD001–FD004), the dataset `readme.txt`, the paper `Damage Propagation Modeling.pdf`, and the original `CMAPSSData.zip`.

Source: NASA Prognostics Center of Excellence Data Set Repository, "Turbofan Engine Degradation Simulation Data Set" (C-MAPSS).

Rules:

- Nothing in `raw/` is edited, renamed, or overwritten. The files are marked read-only as a guard against accidents.
- Code reads from `raw/` and writes anything it produces to `processed/`.
- `raw/` is not committed to Git. To rebuild it, download the zip from NASA, extract it into `data/raw/`, and verify the checksums.

## Verifying the raw files

`checksums.sha256` holds the SHA-256 fingerprint of every raw file as downloaded. Run this from the project root; it prints nothing when every file is unchanged:

```powershell
Get-Content data\checksums.sha256 | ForEach-Object {
    $hash, $name = $_ -split '  ', 2
    if ((Get-FileHash "data\raw\$name" -Algorithm SHA256).Hash.ToLower() -ne $hash) { "CHANGED: $name" }
}
```

## `processed/` — created by our code

Does not exist yet. It will hold cleaned and feature-engineered data from Phase 4 onward, and can always be regenerated from `raw/`.

## Loading notes

- No header row; 26 space-separated numeric columns.
- Rows end with trailing spaces, so load with `sep=r"\s+"` and `header=None`.
- `readme.txt` is Windows-1252 encoded: open it with `encoding="cp1252"`.

Full description of the files: [docs/DATASET_INVENTORY.md](../docs/DATASET_INVENTORY.md).
