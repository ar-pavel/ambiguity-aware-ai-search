# Five runs with a live model reading the requests

Claude Opus 5.5 on Amazon Bedrock as the interpreter, 24 November 2026. Each run is a separate process, because the app keeps a reading while it runs. Run 1 is [`../bedrock.md`](../bedrock.md); runs 2 to 5 are in the folders here. All five are reported. No run fell back to the stand-in, and the frozen files were unchanged since `v1.2-a2` in every run.

Figures are in requests out of 42. "Flagged" counts unclear requests in which the model reported at least one unclear part.

| Run | Always act: wrong | Always show: wrong, all noticed | half noticed | Always ask: questions | wrong, all noticed | half noticed | The rule: questions | wrong, all noticed | half noticed | Flagged, familiar wording (of 19) | Flagged, rewordings (of 11) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 17.25 | 5.5 | 11.5 | 22 | 5.75 | 6.25 | 14 | 5.75 | 8.25 | 15 | 7 |
| 2 | 17.25 | 6 | 11.688 | 22 | 6.25 | 6.5 | 14 | 6.25 | 8.5 | 15 | 7 |
| 3 | 17.25 | 7 | 12.188 | 20 | 7.25 | 7.5 | 12 | 7.25 | 9.5 | 14 | 6 |
| 4 | 16.75 | 5.5 | 11.188 | 23 | 5.75 | 6 | 14 | 5.75 | 8.25 | 15 | 8 |
| 5 | 16.75 | 6 | 11.438 | 22 | 6.25 | 6.5 | 14 | 6.25 | 8.5 | 15 | 7 |
| **range** | 16.75 to 17.25 | 5.5 to 7 | 11.188 to 12.188 | 20 to 23 | 5.75 to 7.25 | 6 to 7.5 | 12 to 14 | 5.75 to 7.25 | 8.25 to 9.5 | 14 to 15 | 6 to 8 |

With the stand-in the same figures are: always act 20.75; always show 9 and 15.06; always ask 22 questions, 9 and 9.75; the rule 16 questions, 9 and 11.25; flagged 18 of 19 and 4 of 11.

**Reading.** The live model's result is stable across runs. It leaves fewer wrong lists than the stand-in (5.5 to 7.25 against 9 when everything shown is noticed), mostly because it knows skills the stand-in does not. It flags about as many unclear requests in total (20 to 23 of 30, against 22), but a different set: fewer in the wording the stand-in's rules were written for, more of the rewordings.
