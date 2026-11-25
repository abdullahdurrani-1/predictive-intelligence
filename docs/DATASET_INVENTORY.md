# Dataset Inventory — NASA C-MAPSS Turbofan Engine Degradation

**Inspected:** 2026-11-13
**Scope:** read-only inspection. No raw file was modified, moved, or renamed. No model was trained.

Every number in this document was measured from the files on disk, not copied from the README or from memory. Where the README disagrees with the files, that is flagged in section 7.

---

## 1. What this dataset is

C-MAPSS is a NASA **simulation** of a large commercial turbofan engine. NASA ran the simulator many times, each time letting a virtual engine wear out until it failed, and recorded the sensor readings along the way.

It is benchmark data. It is not telemetry from a real aircraft, and nothing in this project should describe it that way.

One row is one snapshot of one engine during one **operating cycle** (think of a cycle as one flight). Reading an engine's rows from top to bottom is like watching its health log from the first flight to the last.

---

## 2. File inventory

All 12 dataset files are present, correctly named, and have the `.txt` extension.

| File | Size (bytes) | Rows | Columns | Engines | SHA-256 (first 16 hex) |
|---|---:|---:|---:|---:|---|
| `train_FD001.txt` | 3,515,356 | 20,631 | 26 | 100 | `963b5e22825b34d8` |
| `test_FD001.txt` | 2,228,855 | 13,096 | 26 | 100 | `3cda7109ce17bafb` |
| `RUL_FD001.txt` | 429 | 100 | 1 | — | — |
| `train_FD002.txt` | 9,082,480 | 53,759 | 26 | 260 | `dac6c4dbc4e7c1bd` |
| `test_FD002.txt` | 5,734,587 | 33,991 | 26 | 259 | `de7b5bf7e998a985` |
| `RUL_FD002.txt` | 1,110 | 259 | 1 | — | — |
| `train_FD003.txt` | 4,213,862 | 24,720 | 26 | 100 | `2abbe9968cc5e8eb` |
| `test_FD003.txt` | 2,826,651 | 16,596 | 26 | 100 | `299babd63c8d987c` |
| `RUL_FD003.txt` | 428 | 100 | 1 | — | — |
| `train_FD004.txt` | 10,350,705 | 61,249 | 26 | 249 | `27ef6160b6a1dcb2` |
| `test_FD004.txt` | 6,957,759 | 41,214 | 26 | 248 | `1dc675fff0624bac` |
| `RUL_FD004.txt` | 1,084 | 248 | 1 | — | — |

Supporting files:

| File | Size (bytes) | Notes |
|---|---:|---|
| `readme.txt` | 2,442 | Dataset description. Encoded in Windows-1252, not UTF-8 (see 7.4). |
| `Damage Propagation Modeling.pdf` | 434,158 | 9 pages. Saxena, Goebel, Simon, Eklund, PHM08. Explains how the data was simulated. |
| `CMAPSSData.zip` | 12,425,978 | Original download. Its 14 entries match the extracted files byte-for-byte in size. SHA-256 `74BEF434…91A5A34F`. |

The hashes are a fingerprint of each file as downloaded. If a hash ever changes, the raw file has been altered.

**Location:** all of these files are in `data/raw/` (moved there on 2026-11-13 after this inspection; see 7.1). Full-length checksums are in `data/checksums.sha256`.

---

## 3. Readability checks

Each of the 8 train/test files was parsed line by line. Results were identical for all 8:

| Check | Result |
|---|---|
| Opens as plain ASCII text | Yes |
| Every row has exactly 26 values | Yes |
| Values that fail to parse as numbers | 0 |
| Missing values (NaN) | 0 |
| Engine IDs run 1, 2, 3 … with no gaps | Yes |
| Cycles for each engine run 1, 2, 3 … with no gaps | Yes |
| Header row | None — the files contain only numbers |

Each `RUL_FDxxx.txt` has exactly one integer per test engine, so labels and test engines line up one-to-one.

---

## 4. Column structure

All train and test files share the same 26 columns. The files have no header, so we have to name the columns ourselves.

| Column | Meaning | Plain-language explanation |
|---:|---|---|
| 1 | Engine (unit) number | Which engine this row belongs to. |
| 2 | Cycle | How many flights this engine has completed so far. |
| 3–5 | Operational settings 1–3 | The conditions the engine was flown in. |
| 6–26 | Sensor measurements 1–21 | Temperatures, pressures, speeds, and flows measured inside the engine. |

**Operational settings.** The paper says the simulator varied altitude (sea level to 40,000 ft), Mach number, and throttle resolver angle. The README does not say which setting is which. The values match the usual reading — setting 1 = altitude in thousands of feet, setting 2 = Mach number, setting 3 = throttle angle — but treat that mapping as an inference.

**Sensors.** The README only numbers the sensors. Table 2 of the paper lists 21 outputs in this order, and the standard convention maps them to sensors 1–21 in the same order. The first row of `train_FD001.txt` is consistent with it (for example sensor 1 = 518.67 °R, which is the standard sea-level air temperature, and sensor 5 = 14.62 psia, which is sea-level air pressure).

| Sensor | Symbol | Description | Unit |
|---:|---|---|---|
| 1 | T2 | Total temperature at fan inlet | °R |
| 2 | T24 | Total temperature at LPC outlet | °R |
| 3 | T30 | Total temperature at HPC outlet | °R |
| 4 | T50 | Total temperature at LPT outlet | °R |
| 5 | P2 | Pressure at fan inlet | psia |
| 6 | P15 | Total pressure in bypass duct | psia |
| 7 | P30 | Total pressure at HPC outlet | psia |
| 8 | Nf | Physical fan speed | rpm |
| 9 | Nc | Physical core speed | rpm |
| 10 | epr | Engine pressure ratio (P50/P2) | — |
| 11 | Ps30 | Static pressure at HPC outlet | psia |
| 12 | phi | Ratio of fuel flow to Ps30 | pps/psi |
| 13 | NRf | Corrected fan speed | rpm |
| 14 | NRc | Corrected core speed | rpm |
| 15 | BPR | Bypass ratio | — |
| 16 | farB | Burner fuel-air ratio | — |
| 17 | htBleed | Bleed enthalpy | — |
| 18 | Nf_dmd | Demanded fan speed | rpm |
| 19 | PCNfR_dmd | Demanded corrected fan speed | rpm |
| 20 | W31 | HPT coolant bleed | lbm/s |
| 21 | W32 | LPT coolant bleed | lbm/s |

Abbreviations: LPC/HPC = low/high-pressure compressor, HPT/LPT = high/low-pressure turbine. °R is degrees Rankine.

---

## 5. The three kinds of file

**Train files — complete life stories.** Each engine starts healthy, develops a fault at some unknown point, and the recording ends at the cycle where it fails. Because we know the final cycle is the failure, we can work out the Remaining Useful Life (RUL) for every row ourselves: `RUL = last cycle of that engine − current cycle`. There is no RUL column in the file.

**Test files — stories cut short.** Same format, but each engine's recording stops at some point *before* failure. The task is to predict how many more cycles that engine has left after its last recorded row.

**RUL files — the answer key.** One number per line. Line 1 is the true remaining life of test engine 1 at its last recorded cycle, line 2 is for engine 2, and so on. These are used only for final evaluation.

A maintenance analogy: the train files are like the complete service records of retired engines; the test files are the records of engines still in service; the RUL files are what later happened to those engines.

---

## 6. The four subsets

| Subset | Operating conditions | Fault modes | Train engines | Test engines | Difficulty |
|---|---|---|---:|---:|---|
| FD001 | 1 (sea level) | 1 — HPC degradation | 100 | 100 | Simplest |
| FD002 | 6 | 1 — HPC degradation | 260 | 259 | Harder: conditions change |
| FD003 | 1 (sea level) | 2 — HPC and fan degradation | 100 | 100 | Harder: two ways to fail |
| FD004 | 6 | 2 — HPC and fan degradation | 249 | 248 | Hardest: both at once |

- **Operating condition** = the flight situation (altitude, speed, throttle). With one condition, a sensor change means the engine is changing. With six, a sensor also jumps simply because the flight condition changed, which hides the wear signal.
- **Fault mode** = which part is wearing out. With two modes, engines can degrade in two different patterns.

Measured engine lifetimes and labels:

| Subset | Train life, cycles (min / median / max) | Test history length (min / median / max) | True test RUL (min – max) |
|---|---|---|---|
| FD001 | 128 / 199 / 362 | 31 / 134 / 303 | 7 – 145 |
| FD002 | 128 / 199 / 378 | 21 / 132 / 367 | 6 – 194 |
| FD003 | 145 / 221 / 525 | 38 / 149 / 475 | 6 – 145 |
| FD004 | 128 / 234 / 543 | 19 / 154 / 486 | 6 – 195 |

**Operating regimes found in FD002 and FD004.** Rounding the three settings gives exactly six combinations in both subsets, confirming the README:

| Setting 1 (altitude, kft) | Setting 2 (Mach) | Setting 3 (throttle) |
|---:|---:|---:|
| 0 | 0.00 | 100 |
| 10 | 0.25 | 100 |
| 20 | 0.70 | 100 |
| 25 | 0.62 | 60 |
| 35 | 0.84 | 100 |
| 42 | 0.84 | 100 |

The 42 kft regime has about 1.7 times as many rows as each of the others.

**Columns that never change** (exactly one distinct value in the file, identical in train and test):

| Subset | Constant columns |
|---|---|
| FD001 | Operational setting 3; sensors 1, 5, 10, 16, 18, 19 |
| FD003 | Operational setting 3; sensors 1, 5, 16, 18, 19 |
| FD002, FD004 | None |

A column that never changes carries no information about wear. These are candidates for removal in FD001, to be confirmed in the first notebook. In FD002/FD004 the same sensors vary only because the flight condition varies, so they need a different treatment there.

---

## 7. Issues found

None of these blocks work on FD001. Nothing has been changed.

### 7.1 Files are in the project root, not `data/raw/`
At inspection time all files sat in the project root. **Resolved 2026-11-13:** with the owner's approval they were moved to `data/raw/` and marked read-only. The checksums after the move match those taken before it, so the contents are unchanged (DECISIONS.md, D-001).

### 7.2 README has the FD004 engine counts the wrong way round
The README says FD004 has 248 train and 249 test trajectories. The files contain **249 train and 248 test**, and `RUL_FD004.txt` has 248 values, which matches the test file. The files are internally consistent; the README has a typo. Trust the files.

### 7.3 README column list says "sensor measurement 26"
Column 26 is sensor measurement **21**. There are 21 sensors, not 26.

### 7.4 README is not UTF-8
It uses Windows-1252 (curly quotes and a dash show as `�` in UTF-8 readers). Read it with `encoding="cp1252"`. It was left untouched.

### 7.5 Data lines end with trailing spaces
Each row ends with two spaces before the newline. Loading with `sep=" "` in pandas would create extra empty columns. Load with `sep=r"\s+"` and `header=None`.

### 7.6 Project scaffolding does not exist yet
At inspection time the folder contained only the dataset files. **Resolved 2026-11-13** by Milestone 1 (see PROGRESS.md).

---

## 8. Notes from the research paper

Points from the PDF that matter for later phases:

- **How failure is defined.** The simulator tracks a hidden "health index", the minimum of several safety margins (fan, HPC, and HPT stall margins and exhaust gas temperature). The engine is declared failed when that index reaches zero. These margins are **not** among the 21 sensors we are given, so the model has to infer health indirectly.
- **How wear grows.** Wear on flow and efficiency follows an exponential curve: slow at first, then accelerating. This is the reasoning behind capping RUL early in an engine's life, a decision to be made and documented in Phase 4.
- **Engines do not start identical.** Each begins with a different, unknown amount of initial wear and manufacturing variation, which is considered normal.
- **The data is noisy on purpose.** Both process noise and sensor noise were added.
- **The scoring function is asymmetric.** With `d = predicted RUL − true RUL`, each engine is penalised exponentially in the size of the error, and the paper states that late predictions (`d > 0`) are penalised more heavily than early ones. The reason: telling a maintainer an engine has more life than it really has is the dangerous mistake. Lower scores are better.
  - **To verify before Phase 5:** the paper prints the constants as `a1 = 10, a2 = 13`. The form used throughout the RUL literature is `exp(−d/13) − 1` for early predictions and `exp(d/10) − 1` for late ones, which matches the paper's stated intent. Equation 11 did not survive text extraction cleanly and the page could not be rendered on this machine, so which constant the paper attaches to which branch has not been confirmed by eye. Check equation 11 (in the performance-evaluation section near the end of the PDF) before implementing the metric.

---

## 9. FD001 readiness

**FD001 is ready for the first Jupyter Notebook.**

| Check | Result |
|---|---|
| `train_FD001.txt`, `test_FD001.txt`, `RUL_FD001.txt` present | Yes |
| Train shape | 20,631 rows × 26 columns (matches the expected figure) |
| Test shape | 13,096 rows × 26 columns |
| Engines | 100 train, 100 test |
| RUL labels | 100, one per test engine |
| Missing or unparseable values | 0 |
| Operating conditions | 1 |

Environment: see `requirements.txt` and the project `.venv` set up in Milestone 1.
