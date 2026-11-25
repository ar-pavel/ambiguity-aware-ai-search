# The Figure 1 request with a live model

Request: *Python and AWS people with Senior in the title* (the request that started the project).
Run on 25 November 2026 with `A2_MODEL=bedrock` (Claude Opus 5.5 on Amazon Bedrock), θ = 0.5, ten times,
each as a separate process because the app keeps a reading while it runs:

    python3 -m assistant.strategy "Python and AWS people with Senior in the title"

| Interpreter | Outcome |
|---|---|
| Rule-based stand-in (simulated) | show, every time: AND kept, 7 candidates; OR would give 22 |
| Claude Opus 5.5 on Amazon Bedrock | show in 6 of 10 runs; act in 4 of 10 (it reported nothing unclear) |
| `qwen3:14b` through Ollama ([table](compare-qwen3-14b.md)) | ask |

In all three cases the search used AND. Code keeps AND whenever the user wrote *and*, *with* or *&*,
even if the model returns OR or flags nothing (`interpret.from_model`), so a missed flag here costs
the recruiter the chip that offers OR, not a silently wider list.

The order of the ten Claude runs was: show, show, act, show, act, show, act, show, show, act.
