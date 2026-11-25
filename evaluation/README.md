# Evaluation

**Question:** what does each strategy cost in questions asked, and how many wrong lists does it leave?

**Method.** The rule, the stand-in, the search and the data were frozen at `v1.2-a2`. I then wrote
[42 new requests](requests.json): 12 clear ones and 30 with one or two unclear parts. Each
plausible meaning is taken as the intended one in turn. Every request runs through the same code as
the page under four strategies, with a scripted recruiter who answers questions as they meant and
notices a wrong reading they are shown with a fixed probability. There were no participants, and the
noticing rate is an assumption, not a measurement. Figures are averages, in requests out of 42.

| Strategy | Questions asked (needless) | Wrong lists if everything shown is noticed | If half is noticed |
|---|---|---|---|
| Always act | 0 | 20.75 | 20.75 |
| Always show | 0 | 9.0 | 15.06 |
| Always ask (whenever something unclear is detected) | 22 (10.25) | 9.0 | 9.75 |
| The rule (θ = 0.5) | 16 (7.25) | 9.0 | 11.25 |

**What it shows** ([full tables](results/rules.md)):

- Acting on the first reading gives a wrong list for about half the requests.
- With a recruiter who notices everything, showing matches asking and the rule with no questions. The
  rule only earns its questions if people overlook what they are shown. At half noticing it sits
  between: 6 fewer questions than always asking, 1.5 more wrong lists.
- 9 wrong lists survive every strategy. Three come from skills the stand-in does not know (Vue,
  Kotlin); six from ambiguity it never flagged. It flagged 18 of 19 requests in the wording its rules
  were written for, and 4 of 11 rewordings. No strategy fixed what was never flagged.
- Five separate runs with Claude Opus 5.5 on Amazon Bedrock reading the requests
  ([all five](results/bedrock_runs/README.md)) cut the 9 to between 5.5 and 7.25, mostly by
  knowing more skills. The model flagged about as many unclear requests as the stand-in (20 to 23 of
  30, against 22) but a different set: it missed other ambiguity instead ("near London", "available
  immediately").

**Limits.** The noticing rate was assumed, the data is synthetic, and I wrote both the stand-in's
rules and the requests, so 18 of 19 flatters it. The planned next step is a small study with recruiters that measures
how often they notice a wrong reading.

Run it again with `python3 tools/evaluate.py` (add `--with bedrock` for a live model). The harness is [`tools/evaluate.py`](../tools/evaluate.py).
