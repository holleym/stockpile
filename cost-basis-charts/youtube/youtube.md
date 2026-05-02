# YouTube Script: "Visualize Your Position's Cost Basis with Claude Code"


TODO:
- HOOK — solid, good energy. One note: "used up my weekly allowance
  of Claude Design usage" sounds slightly negative on camera. Consider
  framing it as "I've been experimenting with Claude Design" without
  the limitation detail.

Summary of things still needing your attention before recording:
  1. Line 91: "see a some" → "see some"
  2. Line 184: "or find" → "or finding"
  3. Line 193: placeholder text "make a line showing this, etc..."
     needs real narration
  4. Line 196: "black sholes" → "Black-Scholes"
  5. Line 241: remove or rewrite the "and 4th" — it's orphaned
  6. Line 242: "claude code" → "Claude Code", "lets us" → "let us"
  7. HOW I BUILT THIS section is missing a closing quote


## Title
Charts Your Broker Doesn't Show You (Using Claude Code)

## Thumbnail Ideas

**Concept 1 — The Chart IS the Thumbnail** *(recommended)*
Background: screenshot of the Midnight-scheme chart (dark navy,
blue/orange lines). Bold white text overlaid:
- Large: Chart YOUR REAL COST BASIS
- Small (bottom): Build it with Claude Code

Give Gemini: the chart screenshot + "make a YouTube thumbnail with
bold white text 'YOUR REAL COST BASIS' in the upper third and small
text 'Built with Claude Code' at the bottom, keep the chart visible"

**Concept 2 — Split / Contrast**
Left half: greyed-out brokerage account view. Right half: colorful
chart. Bold text across the center:
- vs. THIS

Give Gemini: both images side by side + "YouTube thumbnail split
screen, left side desaturated/grey, right side vibrant, bold text
'vs. THIS' across the middle"

**Concept 3 — The Hook**
Dark background, your face (surprised/impressed) on one side, chart
on the other. Text:
- YOUR BROKER HIDES THIS

Give Gemini: your photo + chart screenshot + "YouTube thumbnail, face
on left looking surprised, chart on right, bold red/white text 'YOUR
BROKER HIDES THIS' at the top"

---

## HOOK (0:00–1:30)
*[Animation: chart fly-in — close price line draws left to right,
then adjusted cost basis line draws underneath it, transaction
markers pop in, right-edge labels appear showing P&L]*

This episode is all about charting your positions with Claude Code.
It's related to my last episode about making Google Sheets for your
positions with Claude Code, linked in the description.

We're going to once again use transactions logs from your brokerage,
but this time we're going to visualize your position performance
with charts.

Borrowing the theme from last episode, the charts in this episode
will show you something your brokerage account doesn't — your *real*
performance.

[Switch to a real chart]
These charts include every covered call and put you've ever sold,
every dividend you've collected, and every time you've bought and
sold shares.

I built this entire thing without writing a single line of code
myself, I just described what I wanted, and Claude wrote all the
code to produce these charts, and document them. It even suggested
the free charting tool to use.

[Back to Animation]

Then Claude Design, a new product that comes with your Claude Code
subscription, took one of the charts and made this animation.
That's what you're seeing here and here's all I did to make the
animation: I asked twice, second time was successful but used up my
weekly allowance of Claude Design usage. That was my first
experiment with Design.

---

## SETUP THE PROBLEM (1:30–2:10)

[Show actual chart]

Back to the more detailed Cost Basis Chart

"Most people look at their brokerage account and see a some numbers
or a chart showing a simple average cost per share. We'll do better.
These charts will enhance your typical brokerage view with every
transaction related to each of your positions. The Python script
parses your transaction history, runs First In, First Out accounting
on every trade, and subtracts all the income you've collected. Each
of the lines you see here is a different view of how profitable your
position is.

It also overlays these lines on the real historical price from Yahoo
Finance, so you can see the full picture at a glance, the blue line
here..."

---

## LIVE DEMO — ADDING PNG EXPORT (2:10–4:10)
*[Screen: terminal with Claude Code open, chart HTML visible]*

"Now lets see what it looks like to add a feature with Claude Code.
The charts output as HTML, which is great — but what if I want to
share one as an image in a doc or a Slack message?

I'll just ask."

*[Type into Claude Code: "add a --png flag that saves a static PNG
of the chart alongside the HTML"]*

*[Claude writes the code — briefly show the diff scrolling]*

"Done. Let's run it."

*[Terminal:]*
`uv run python cost-basis-charts/run_charts.py --symbol PFE --png`

*[File explorer: PFE_cost_basis.png appears in the charts/ folder]*
*[Open the PNG]*

"That's the whole workflow. Describe what you want, Claude writes it,
you test it. No docs, no Stack Overflow, no writing code."

---

## THE CHART IN DETAIL (4:10–7:40)
*[Show a chart with open options — dashed live cost line visible]*

"Let's take a closer look at everything on this chart.

The blue line is the closing price from Yahoo Finance — that's what
the stock actually traded at each day.

The purple line is your stock FIFO cost basis. That's the raw
average cost of your shares based on the order you bought them —
first in, first out. Every time you buy shares, it includes them in
the average. Every time you sell, the oldest lots come off first
and it adjusts.

The orange line is your adjusted cost basis. It starts the same as
FIFO, but every time you collect a premium on a covered call or a
put, or receive a dividend, that income gets subtracted from your
cost. Over time, if you're actively selling options, you'll see this
line drift lower and lower — meaning your cost basis is less, and
it's easier for the position to be profitable. The one exception is
if you sell a debit roll, not a credit, then the line will drift
higher.

The dots on the lines mark individual transactions — buys, sells,
options trades, dividends. Hover over any dot, and you'll see
exactly what the transaction was. Hover anywhere on the price line,
and you get the closing price plus your P&L per share against your
adjusted cost at that date.

The labels on the right edge show your current numbers at a glance —
close price, adjusted cost, and FIFO cost, with P&L in green or red.

If you have open covered calls or puts right now, the chart gets
one more line — the dashed one. The script estimates the current
market value of each open option using Black-Scholes (linked in
description) and adds that liability back into your cost basis. So
you can see your *true* break-even today. This accounts for what it
would cost to close your open positions. That line updates every
time you run the script.

The dashed horizontal line shows your strike price over the lifetime
of your open option — from when you opened it to expiration. You
can see at a glance whether the stock is above or below your
strikes.

Below the main lines you'll also see Intrinsic Value and Time Value.
These break down the current worth of your open options. Intrinsic
value is how far in the money the option is — the portion that has
real dollar value right now.

Time value is everything else — the probability premium that decays
to zero as you approach expiration. Depending on circumstances, Time
value can be a great indicator of whether to close your position.
For example, if a covered call is deep ITM and will almost surely
get called away, and its remaining Time Value is very small compared
to the position's close out value, then you may consider taking
action.

You'd probably be better off closing the position and investing in
better yielding cash or find another investment opportunity."

---

## HOW I BUILT THIS WITH CLAUDE CODE (7:40–8:20)

"The entire script for building these cost basis charts for each of
your positions was written by Claude Code. I described what I
wanted — parse broker CSVs, compute FIFO cost basis,
make a line showing this, make another line showing this, etc...
add the historical Yahoo Finance prices, and the current option —
and Claude wrote it. Then I iterated visually: tweaked the chart
layout, added things like the black sholes estimate of the open
option line, added the annotation collision-avoidance so labels
don't overlap.

The whole workflow is: describe the feature, look at the output, say
what's wrong, repeat. So much easier than the olden days when I
actually had to write the code from scratch.

---

## WHAT YOU'LL NEED (8:20–8:45)

If you'd like to do this yourself with your transactions logs,
You'll need to do some setup.  The easy-mode way to do this is to get
a subscription to Claude Code (linked in Readme), and start Claude in the
stockpile/cost-basis-charts directory after cloning or downloading the
repository.  Then ask it to help you get it running with your
transactions file.

You'll need:

1. A transaction history export from your brokerage. My repo
   currently supports Schwab and Robinhood, more brokerages soon.
2. Python installed on your machine, see the README for details.
3. This repo — link in the description, it's free on GitHub.

---

## EXPORTING YOUR TRANSACTIONS (8:45–9:15)
*[Screen recording of Schwab web UI]*

I won't bore you with how to download your brokerage full transaction
history, just put it somewhere — the /input directory in the root of
this repo works. Make sure you go back as far as you can to increase
your chances of getting all your position history. Create a copy of 
config.toml.example and name it config.toml in the cost-basis-charts folder.
Then point the configuration in that file to your downloaded transactions file
from your brokerage.

---

## RUNNING IT (9:15–10:15)
*[Terminal: `uv run python cost-basis-charts/run_charts.py`]*

"One command from the repo root. It'll parse your transactions, pull
historical prices from Yahoo Finance, and write an interactive HTML
file for each ticker into the `charts/` folder."

*[Go to charts folder and open one with Chrome]*

Open one of the charts you just made, and have a look — be sure to
hover the mouse over the lines.

and 4th, if you want to tweak it, improve or add new features, feel
free! Subscribe to claude code, fork my repo, and lets us know what
you did.

---

## OUTRO (10:15–10:35)
Link to the repo is in the description — it's all open source. If
you're running covered calls, wheeling, or just want a cleaner
picture of your actual risk in a position, this could help.
Let me know in the comments what other views or features would
be useful, what other interesting things we could do with our
transaction logs?

Please consider liking and subscribing, and have a look at my last
episode, which was about making Google Sheets from your transaction
logs.

---

## RESOURCES (description links)

- Repo: https://github.com/driekhof/stockpile
- Black-Scholes explained:
  https://www.investopedia.com/terms/b/blackscholes.asp
- Previous episode (Google Sheets positions tracker):
  [PASTE URL HERE]

Support the work:
- GitHub Sponsors: https://github.com/sponsors/medloh
- Patreon: https://www.patreon.com/OptionsforLongTermInvestors

---

## PRODUCTION NOTES

### Before Recording
- Write the description first — YouTube indexes it for search
- Pick a target keyword phrase ("cost basis covered calls", "Claude
  Code python stock charts") and say it naturally in the first 30s
- Record a strong first 30 seconds — audience retention at 30s is a
  key ranking signal

### Before Publishing
- Add chapters (timestamps in description) — viewers scrub instead
  of leaving, which increases watch time
- Add 3–5 tags matching your target keywords
- Write strong first 2 lines of description — that's what shows
  before "show more" in search results
- Set custom thumbnail BEFORE publishing, not after
- Add cards at ~20%, 40%, 60% of runtime pointing to the Google
  Sheets episode

### Immediately After Publishing (first 48 hours matter most)
- Share to relevant communities:
  - r/options, r/thetagang, r/learnprogramming
  - Claude/AI Discord servers
  Early velocity signals quality to the algorithm
- Pin a comment with the repo link and a seed question:
  "What other charts would be useful?"
- Reply to every early comment — engagement in the first 48 hours
  boosts distribution

### Exit Screens
Go back and add this video to the exit screen of:
- The Google Sheets episode [PASTE URL HERE]
- Any other popular episodes on your channel
Viewers already interested in your tools are most likely to watch
both.

### Ongoing (2 weeks after)
- Check YouTube Studio analytics
  - If click-through rate is under ~4%, test a new thumbnail
  - If one chapter gets most views, consider a standalone short on
    just that topic
