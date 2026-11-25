# PREDICTIVE INTELLIGENCE — From Engine Degradation to Intelligent Decisions

Script and storyboard for the technical walkthrough. Target length: 14 to 16 minutes.

## Ground rules for recording

- **Everything on screen is real.** Record the actual notebooks, the running dashboard and the terminal. No mock-ups, no invented numbers. Every figure quoted in the narration appears in a notebook output; the source is listed beside each scene.
- **Say "simulated" early and again at the end.** The data is the NASA C-MAPSS benchmark, not readings from a real aircraft.
- **Two audiences.** Each scene has one plain-language sentence a non-specialist can follow, then the technical detail.
- **Visual style.** The project's dark navy theme with teal, blue, silver and amber. Notebook cells zoomed to a readable size. Slow, deliberate cursor movement.
- **Before recording:** run `python -m pytest -q`, start the API and dashboard, and open notebooks 01 to 10 already executed. Re-check any number in this script against the notebook if a notebook has been re-run since.

## Scene list

| # | Scene | Length | On screen | Source |
|---:|---|---|---|---|
| 1 | The problem | 0:50 | Title card, then the lifetime histogram | Notebook 01 |
| 2 | The dataset | 1:00 | Data table, sensor reference table | Notebook 01 |
| 3 | Seeing wear | 1:20 | Fleet grid, 3D trajectory | Notebook 02 |
| 4 | How early can we know? | 1:10 | Drift-detection chart | Notebook 03 |
| 5 | Honest validation and features | 1:30 | Leak table, feature bar chart | Notebook 04 |
| 6 | Traditional models | 1:00 | Results table, scatter plots | Notebook 05 |
| 7 | Deep learning | 1:20 | Learning curves, comparison chart | Notebook 06 |
| 8 | Stress-testing the results | 1:10 | Seed table, frozen-sensor chart | Notebook 07 |
| 9 | Why the model says what it says | 1:10 | SHAP bars, two-engine comparison | Notebook 08 |
| 10 | How sure is it? | 1:10 | Range chart with misses marked | Notebook 09 |
| 11 | The harder subsets | 1:10 | Regime chart, transfer heat map | Notebook 10 |
| 12 | The assistant and the dashboard | 1:40 | Live dashboard | Running app |
| 13 | Deployment and monitoring | 0:50 | Terminal: stream replay, drift alert | Scripts |
| 14 | What we learned, and the limits | 1:00 | Summary card | All |

---

## Scene 1 — The problem (0:50)

**On screen:** Title card "PREDICTIVE INTELLIGENCE — From Engine Degradation to Intelligent Decisions". Cut to the lifetime histogram from notebook 01.

**Narration:**
"An aircraft engine does not fail on a schedule. In this dataset, engines of exactly the same type last anywhere from 128 to 362 flights. If you service every engine after a fixed number of flights, you are too late for some and wasting good life on others.

Predictive maintenance asks a different question: not 'how old is this engine?' but 'what are its sensors telling us?' This project builds a system that answers that question, says how sure it is, explains its reasoning, and puts all of it in plain language.

One thing to be clear about from the start: the data is a NASA simulation. This is a research demonstration, not a tool for real aircraft."

## Scene 2 — The dataset (1:00)

**On screen:** `train.head()` in notebook 01, then the sensor reference table, then the data-quality table.

**Narration:**
"The data is NASA's C-MAPSS benchmark. Each row is one engine on one flight: three flight settings and twenty-one sensor readings, covering temperatures, pressures, speeds and flows.

We start with the simplest subset, FD001: 100 engines recorded from new until failure for training, and 100 more whose records stop at some point before failure. The task is to predict how many flights each of those has left.

Before any modelling we checked the basics. No missing values, no duplicates, no gaps. We also found that six of the twenty-one sensors never change at all, and a seventh barely does. A gauge whose needle never moves cannot tell you anything."

## Scene 3 — Seeing wear (1:20)

**On screen:** The 14-panel fleet grid from notebook 02. Then rotate the 3D degradation trajectory slowly.

**Narration:**
"Here is every training engine, lined up so that failure is at the right-hand edge. Each thin line is one engine; the bold line is the fleet average.

The pattern is the same for almost every sensor: flat for most of the engine's life, then bending away, faster and faster. Temperatures rise. Pressures at the compressor outlet fall. That is what a compressor losing efficiency looks like.

This 3D view takes three sensors that measure different things and uses them as axes. Each line is one engine travelling from healthy, in teal, to failure, in amber. They all take the same road. In fact a single direction accounts for 64 percent of all the variation across fourteen sensors. On this subset, wear is essentially one process seen through many noisy instruments."

## Scene 4 — How early can we know? (1:10)

**On screen:** The drift-from-healthy chart in notebook 03, then the per-engine table below it.

**Narration:**
"How far ahead can we honestly predict? We measured each engine's drift from its own healthy baseline, in units of sensor noise.

A single sensor only rises clearly above the noise in roughly the last 70 to 110 flights. Combining twelve sensors, the red line, buys more warning, because their noise is independent and averages away.

But beyond about 125 to 150 flights before failure there is very little signal. An engine with 200 flights left looks the same as one with 300. So we made a deliberate choice: the model is not asked to distinguish them. Anything above 125 flights is labelled simply as healthy. That choice means the system will say 'at least' for a healthy engine, and it will say so openly."

## Scene 5 — Honest validation and features (1:30)

**On screen:** The leakage table in notebook 04. Then the feature comparison bar chart.

**Narration:**
"This is the most important methodological point in the project. When you hold back data to check a model, you must hold back whole engines, not random rows. Neighbouring flights of the same engine are nearly identical, so a model checked on random rows is being asked about engines it has already seen.

We measured the effect. With history-based features, checking on random rows reports an error of 8.9 flights. Checking properly, on unseen engines, gives 13.5. The careless method understates the error by a third. Every number in this project uses the honest method.

Then the features. We compared seven options the same way. The one that mattered most is simple: for each sensor, the change from that engine's own level when it was new. Engines start at different levels, and this removes the difference. It cut the error near failure by about a quarter. A later experiment confirmed it: remove that one group of features and the model loses 3.7 flights of accuracy; remove any other group and it loses less than half a flight."

## Scene 6 — Traditional models (1:00)

**On screen:** Test results table in notebook 05, then the three predicted-versus-true scatter plots.

**Narration:**
"With the features fixed, we trained three kinds of model, from simple to flexible, and scored each once on the 100 test engines.

Always guessing the average is off by 43 flights. Linear regression: 18. Random Forest: about 14. XGBoost: about 15.

Two things to notice. The more complex model did not automatically win; Random Forest and XGBoost are level in cross-validation. And the tree models are most accurate where it matters most: for engines within 30 flights of failure, XGBoost is typically off by about three."

## Scene 7 — Deep learning (1:20)

**On screen:** Learning curves in notebook 06. Then the horizontal comparison bar chart.

**Narration:**
"Next, four neural networks that read thirty flights of raw sensor history directly: a plain network, an LSTM, a GRU and a temporal convolutional network. Same engines, same rules, three random seeds each.

On the engines held back during training, the networks looked better than XGBoost: around 10 to 11 flights against 12.8.

On the untouched test set, they were not. Single networks scored 16.3 to 17; XGBoost trained on the same engines scored 14.6. The four architectures could not be told apart.

This is a genuine finding, and an instructive one. The held-back engines had been used to decide when each network should stop training, which flattered them. Only the test set told the truth. On this simple subset, good features and a tree model were enough."

## Scene 8 — Stress-testing the results (1:10)

**On screen:** Seed table in notebook 07, the Optuna chart, then the frozen-sensor bar chart.

**Narration:**
"A result is only worth reporting if you know how much it moves. So we pushed on it.

Changing nothing but the random seed, XGBoost's test error ranges from 14.3 to 15.1. Systematic tuning with Optuna, nineteen minutes of search, improved it by about a third of a flight. Real, but small. Features mattered roughly ten times more than tuning.

The more important result is this one. We froze one sensor at its healthy value, as if it had stopped responding. Every time, the model became more optimistic. With the main sensor frozen, the number of engines predicted badly late went from 7 to 24. The model gives no warning. That is a weakness any real system would have to guard against separately."

## Scene 9 — Why the model says what it says (1:10)

**On screen:** Global SHAP bar chart in notebook 08. Then the side-by-side chart for test engines 54 and 37.

**Narration:**
"A number without a reason is hard to act on. SHAP takes one prediction and divides it among the sensors: this one lowered the estimate by so many flights, that one raised it.

Overall, the model leans most on the static pressure at the compressor outlet, then a turbine temperature and the fuel-flow ratio. Those are also the three sensors with the strongest trends in the raw data, which is reassuring.

Here are two test engines that have each flown exactly 121 flights. The model gives one about 120 flights and the other about 22. For the first, every sensor sits near its starting level. For the second, several have drifted, the pressure sensor most of all. The truth was 97 and 21.

A caution we repeat throughout: this shows what the model relied on. It does not diagnose a faulty part."

## Scene 10 — How sure is it? (1:10)

**On screen:** The sorted range chart in notebook 09, pausing on the red crosses. Then the table of misses.

**Narration:**
"Every estimate comes with a range. We built it with a method called conformalized quantile regression, and then did the essential thing: checked it on engines the model had never seen.

The promise was 90 percent. On the test set the true value was inside the range for 95 of 100 engines. The range is tight near failure, about 26 flights wide, and wide in mid-life, where the model genuinely knows less.

Now the five misses. Two engines lasted longer than expected. Three failed sooner than their range allowed, and all three had 21 or fewer flights left. So the range is narrowest exactly where a mistake is most serious. A prediction is not a guarantee, and the system is built to say so."

## Scene 11 — The harder subsets (1:10)

**On screen:** The raw-versus-normalised chart for FD002 in notebook 10. Then the within-subset results table and the transfer heat map.

**Narration:**
"So far, the easy subset. The other three add six flight conditions, a second way of failing, or both.

With six flight conditions, a sensor reading jumps every time the altitude or speed changes, and the jumps swamp the wear signal. On the left, raw readings from one engine: six bands and no visible trend. The fix is to judge each reading against what is normal for its own flight condition. On the right, the same sensor afterwards: the drift is back. Without this step the error is 19.5 flights instead of 14.2, and giving the model the flight settings as extra inputs did not help at all.

With that one addition, the recipe built on the simple subset carries over unchanged: 12 to 14 flights of error on all four, on the comparable measure. Scored against the raw truth, two of the subsets look much worse, about 25, and the reason is instructive: a quarter of their test engines have more life left than the model's 125-flight limit can express.

Then we moved models between subsets. Moving from six flight conditions to one costs almost nothing. But a model that has only ever seen one kind of fault is 8 flights worse on a fleet with a second kind. You can normalise away a flight condition. You cannot normalise away a way of failing the model has never seen.

We also gave the neural networks, including a small Transformer, their chance on these harder subsets. No architecture won consistently, and the Transformer was best on none. And the checked ranges held overall, 87 to 95 percent, but fell to about 76 percent for near-failure engines on the hardest subset. We report that, because that is exactly where it matters."

## Scene 12 — The assistant and the dashboard (1:40)

**On screen:** The live dashboard. Select Engine 37. Show the status banner, the three headline numbers, the estimate-over-time chart. Open "Ask a question" and ask the four questions below. Then select Engine 54 and ask "How long will it last?". Then ask "Is it safe to fly?".

**Narration:**
"All of this comes together here. Choose an engine and you see its status, the estimate, the range, how the estimate has changed over its life, and the measurements behind it.

And you can simply ask. 'Is this engine healthy?' … 'How much longer can it work?' … 'Why does the model think so?' … 'What should we do now?'

Listen to how it answers. It gives the range with the estimate. It says 'consider'. It says the readings suggest a wear pattern but cannot prove the cause.

The assistant can only speak from a fact sheet produced by the model for that engine. If a language model writes the answer, every number in it is checked against that fact sheet, and the answer is thrown away if one does not match. Without a language model, a built-in layer answers from the same facts.

For this healthier engine it says 'at least', because the model cannot see further. And asked whether an engine is safe to fly, it declines. That decision belongs to qualified people following approved procedures."

**Recording note:** State on screen which answer source is shown ("Answer source" caption under each reply). If no API key is configured, the rule-based layer is what is being demonstrated; say so.

## Scene 13 — Deployment and monitoring (0:50)

**On screen:** Terminal. Run `python scripts/simulate_stream.py --engine 37 --every 15`. Then `python scripts/monitor_report.py`, then again with `--inject-drift`. Briefly show `python -m pytest -q` passing and the `/docs` page of the API.

**Narration:**
"Behind the dashboard is an API with tests, a container definition and a retraining script that only promotes a new model if it is not worse than the current one.

Here we replay an engine flight by flight, as if each had just landed. The estimate falls from over a hundred flights to twenty-two as wear sets in.

And here is the monitor. It compares incoming readings with the data the model learned from. On normal data it reports no change. When we inject a fault into one sensor, it raises an alert. That is the separate safeguard the frozen-sensor experiment showed we need."

## Scene 14 — What we learned, and the limits (1:00)

**On screen:** Summary card with the five points below, then the limitations list, then the title card.

**Narration:**
"Five things this project found.

One: check models on whole engines, or your numbers will flatter you by a third.
Two: one good feature, the change from each engine's own baseline, was worth more than any choice of algorithm or any amount of tuning.
Three: on this benchmark's simplest subset, deep learning did not beat a well-built tree model, and the validation set said otherwise until the test set corrected it.
Four: a range you have checked is worth more than a confident single number.
Five: an explanation should come from the model, and an assistant should be unable to say what the model did not find.

And the limits. This is simulated data from one engine model. Nothing here has been validated on a real engine. The model cannot see beyond 125 flights, it can be fooled by a faulty sensor, and its status labels are our own conventions, not aviation standards.

It is a demonstration of how to turn complex engine data into something a person can understand and question. The decision stays with the people responsible for the aircraft."

---

# Short version for LinkedIn (60 to 75 seconds)

**Visuals, in order:** 3D degradation trajectory rotating (0:00–0:10) → fleet grid (0:10–0:20) → feature bar chart (0:20–0:30) → model comparison bar chart (0:30–0:40) → range chart with misses (0:40–0:50) → dashboard with a question being asked (0:50–1:05) → closing card (1:05–1:12).

**Narration:**
"Aircraft engines of the same type can last 128 flights or 362. I built a system that estimates how long one has left from its sensor data, and explains itself.

It uses NASA's simulated C-MAPSS benchmark. Three things I learned.

First, validate on whole engines. Checking on random rows made the error look a third smaller than it really was.

Second, features beat architecture. One idea, measuring each sensor against the engine's own starting level, mattered more than the choice between XGBoost, an LSTM, a GRU or a convolutional network. On this subset the tree model matched or beat all four networks.

Third, be honest about uncertainty. Every estimate comes with a range, checked on unseen engines: it held for 95 of 100. Three of the five misses were engines that failed sooner than predicted, and the system says so.

On top sits an assistant that answers plain questions and can only state what the model actually found.

It is a research demonstration on simulated data, not a tool for real aircraft. Notebooks, code and paper are in the repository."

**On-screen caption throughout:** "Research demonstration · NASA C-MAPSS simulated data".

---

# Recording checklist

- [ ] All ten notebooks executed, outputs visible, no error cells.
- [ ] `python -m pytest -q` passes on camera.
- [ ] API and dashboard running; engines 37 and 54 load.
- [ ] Each number spoken matches the notebook output shown at that moment.
- [ ] The word "simulated" appears in scenes 1, 12 and 14 and in the LinkedIn caption.
- [ ] The answer-source caption is visible in every assistant reply shown.
- [ ] No footage implies a real aircraft, airline or maintenance organisation.
