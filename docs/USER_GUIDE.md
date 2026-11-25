# Predictive Intelligence — User Guide

A guide for the person using the application. You do not need to know anything about computers, statistics or artificial intelligence to use it.

---

## 1. What this tool is

This tool looks at the readings an engine's sensors recorded on each flight and estimates **how many more flights the engine has left** before it would wear out.

Think of it like the wear indicator on a brake pad or the tread on a tyre. Parts wear a little every time they are used. This tool watches for the signs of that wear in the engine's measurements.

It tells you four things about an engine:

1. **How many flights it probably has left** (the estimate).
2. **How sure it is** (a range, for example "21 to 50 flights").
3. **Which measurements made it think so.**
4. **What you might consider doing next.**

## 2. What this tool is NOT

Please read this part carefully.

- **It is a demonstration.** It was built and tested on practice data made by a NASA computer simulation. It has **never been tested on a real aircraft engine**.
- **It cannot tell you an engine is safe to fly.** Only qualified staff following approved procedures can decide that.
- **It cannot tell you which part is faulty.** It sees that readings have changed. It does not know why.
- **Its estimate is a best guess, not a promise.** Some engines wear out sooner than it predicts.

Use it to decide **which engines to look at first**. Never use it instead of an inspection.

---

## 3. Starting the application

Someone who set up the computer needs to do this once per session. It takes two windows.

1. Open the project folder `E:\CMAPPS NASA`.
2. Open a PowerShell window in that folder and type:
   ```
   .venv\Scripts\Activate.ps1
   uvicorn api.main:app
   ```
   Leave this window open.
3. Open a second PowerShell window in the same folder and type:
   ```
   cd frontend
   npm run dev
   ```
   Leave this window open too.
4. Open a web browser (Chrome or Edge) and go to:

   **http://localhost:5173**

Type the address exactly like that. To stop the application, close the two PowerShell windows.

---

## 4. The main screen

The screen has four areas.

| Area | Where | What it shows |
|---|---|---|
| Engine list | Left | All the engines you can look at. Click one to select it. |
| 3D engine | Middle | A model of a jet engine you can turn and zoom. |
| Results | Right | The estimate, the range and the reasons. |
| History | Bottom | How the engine's readings and its estimate changed over time. |

### The engine list (left)

Each engine has a coloured dot and a number.

| Dot colour | Meaning |
|---|---|
| Green | No wear the tool can measure yet |
| Light brown | Early signs of wear |
| Yellow-gold | Clear signs of wear |
| Red | Close to the end of its predicted life |

The number is the estimated flights left. A number with a plus sign, such as **93+**, means "at least 93".

### The 3D engine (middle)

- **Drag** with the mouse to turn the engine. **Scroll** to zoom.
- The buttons at the top change what you see:
  - **3D view** — the engine by itself.
  - **Components** — click a part to read what it does.
  - **Sensors** — shows the readings at the places where they are measured.
  - **Model influence** — colours those places by how much they affected the estimate. Yellow-gold means the reading made the estimate lower. Green means it made it higher.
- **Cutaway** opens the casing so you can see inside. **Pause** stops the spinning.

The engine picture is a drawing to help you understand. It is not a camera view of a real engine, and the spinning is only an animation.

### The results (right)

**Estimated flights remaining** — the tool's best guess.

**90% range** — where the true answer usually falls. Out of every ten engines, about nine fall inside the range and about one does not. So:

- "21 to 50" means: most likely between 21 and 50 flights, but it could be fewer.
- "at least 93" means: the tool sees no wear yet and cannot tell how much longer the engine will last. It can only see about 125 flights ahead.

**The lower number is not a safety limit.** Some engines have failed sooner than their lower number.

**What moved the estimate** — the measurements that mattered most. For each one you see what it reads now compared with when the engine was new. Yellow-gold bars lowered the estimate. Green bars raised it.

**Download report (PDF)** — saves a short PDF report of this engine to your computer. See section 7.

**Something to consider** — a suggestion, such as "consider planning an inspection". These suggestions are this project's own guide. They are not official aviation rules.

### The history (bottom)

- The **orange line** is the estimate at each point in the engine's life.
- The **shaded band** around it is the range.
- The **yellow line** is one sensor's readings. Use the **Sensor** menu to choose which.
- Drag the **Flight** slider to go back in time and see what the tool would have said then.

---

## 5. Checking an engine from your own file

Click **Upload Engine Data** in the top menu.

### What the file needs

- **One row for each flight**, starting at the engine's very first flight. No flights missing.
- A column called `cycle` with the flight number: 1, 2, 3 and so on.
- Columns called `sensor_1` up to `sensor_21`.
- Save it as a **CSV** file. (A NASA text file also works.)

Not sure about the layout? Click **Download an example file** and copy it.

### Steps

1. Click **Choose a file** (or drag the file onto the box).
2. Wait a few seconds.
3. Read the result.

### What can happen

| You see | What it means | What to do |
|---|---|---|
| **File accepted and analysed** (green) | The file is fine. The results are shown below. | Read the results as in section 4. |
| **Analysed, with warnings** (red banner) | An answer was given, but something in the data looks wrong, for example a sensor that has stopped changing. | Check that sensor is working before trusting the answer. A stuck sensor makes an engine look healthier than it is. |
| **This file was not accepted** | No answer was given. The screen tells you why. | Fix the file and try again. |
| **This file contains several engines** | The file holds more than one engine. | Pick one from the menu. |

### Why a file may be refused

- A column is missing, or a value is not a number.
- Flights are missing, repeated, or do not start at 1.
- **The readings do not look like the engine type this tool knows.** For example, temperatures in different units, or a different kind of engine.

That last one is important. **This tool only understands one kind of engine**: the NASA practice engine it learned from. If you give it readings from a different engine, any number it gave would mean nothing, so it refuses instead of guessing. To use it on a different engine, the tool would first have to be taught with many past records of that engine type, including engines that ran until they wore out.

Your file is not saved. It is read, checked, and forgotten.

---

## 6. Asking questions

Click **AI Assistant** in the top menu. Type a question in ordinary words, or click one of the suggested questions.

Questions you can ask:

- Is this engine healthy?
- How much longer can this engine work?
- Why do you think this engine is wearing out?
- What does sensor 11 mean?
- How sure are you?
- What should the maintenance team look at?
- Compare this engine with engine 54.

### Helpful switches

- **Explain like I'm new to aviation** — turn this on for simpler words and everyday comparisons.
- **Use language model** — leave this on. If it is off, or the internet is down, you still get an answer from the tool's built-in rules.

### How to read an answer

- Under each answer it says **who wrote it** and lets you open **Evidence used**. The evidence is the real information the answer was built from.
- The assistant can only talk about what the tool actually worked out for that engine. It is checked before you see it. That is why an answer can take up to a minute and appears all at once.
- If you ask "Is it safe to fly?", it will tell you it cannot decide that. That is correct. It is not a fault.

The box on the right, **Maintenance briefing**, gives a short summary of the selected engine without you having to ask.

---

## 7. Downloading a report

You can save a short PDF report (about two pages) for any engine, to keep, print or send to someone.

There is also a **test report** in the project folder, `reports\FD001_test_report.pdf`. It shows how the tool did on 100 practice engines whose true answers are known (section 9 summarises it).

- **For an engine in the list:** select it, then click **Download report** in the results area on the right. If you have moved the Flight slider back, the report is for that earlier flight.
- **For your own file:** after uploading, click **Download report** next to the results.
- **From the AI Assistant page:** use the **Download report** link in the Maintenance briefing.

The report is saved to your Downloads folder as a **PDF** file. Double-click it to open it. You can print it or attach it to an email like any other PDF.

The report contains the status, the estimate and range, a chart of how the estimate changed, the measurements that mattered, the suggestion, how far to trust it, and the limits. It says the same things the screen says, nothing more.

## 8. The other pages

| Page | What it is for |
|---|---|
| **Sensor Intelligence** | Look at any of the 21 sensors, and compare two engines side by side. |
| **Research Lab** | The test results that show how accurate the tool is. Mostly for engineers. |
| **Model Center** | What the tool is, how it was checked, and its limits. |
| **Monitoring** | Checks whether new readings still look like the ones the tool learned from. A red banner means they do not, and results should be reviewed before use. |
| **Settings** | Shows how the tool is set up. |

---

## 9. How accurate is it?

Measured on 100 practice engines the tool had never seen before:

- Its estimate was typically off by **about 7 to 11 flights**.
- For engines close to wearing out (30 flights or fewer left), it was typically off by **about 3 flights**.
- The true answer was inside the stated range for **about 95 out of 100** engines.
- It did **not** raise a false "close to end of life" alarm on any healthy engine in the test.
- A few engines failed **sooner** than the range said they would.

These figures are for the practice data only. Nobody knows how well it would do on a real engine.

---

## 10. Common problems

| Problem | What to try |
|---|---|
| The page will not open | Check both PowerShell windows are still open. Use `http://localhost:5173`, typed exactly. |
| "The analysis service is not reachable" | The first window (`uvicorn`) has stopped. Start it again. |
| The 3D engine is missing | Your browser cannot show 3D graphics. Everything else still works. Try Chrome or Edge. |
| The assistant is slow | It can take up to a minute. It is checking its answer. |
| The answer says "rule-based" | The online language service was not available, so the built-in rules answered. The information is still from the tool's own results. |
| My file is refused | Read the reason on screen. Compare your file with the example file. |

---

## 11. Words used in this tool

| Word | Meaning |
|---|---|
| **Cycle / flight** | One take-off and landing. |
| **Remaining useful life (RUL)** | How many more flights the engine can make before it wears out. |
| **Estimate** | The tool's best guess. |
| **Range** | The span the true answer usually falls in. |
| **Sensor** | A measuring device on the engine, for temperature, pressure, speed and so on. |
| **Model** | The part of the tool that learned from past engines and makes the estimate. |
| **Simulated data** | Data produced by a computer program that imitates an engine, not measured on a real one. |
| **Baseline** | What the engine's readings were when it was new. |

---

## 12. The one rule to remember

**This tool helps you decide where to look. It does not decide what to do.**

Always follow approved maintenance procedures and the judgement of qualified engineers.
