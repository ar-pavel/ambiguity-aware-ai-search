"""Typed follow-up commands for the write actions (issue #42).

    "add them to the Java shortlist at Bluefin"     -> shortlist, job words ["Java", "Bluefin"]
    "close these"                                   -> close
    "Python developers who closed deals"            -> None (a new search)

parse() only recognises the command; it never writes. The command still goes through the same
plan -> confirm -> apply as the buttons, so a misread command costs one Cancel, not a write.

A non-command must stay a new search, so the verb counts only when it is clearly a verb:
  * it starts the text ("close these", "shortlist for the Senior Backend Engineer role"), or
  * it is applied to the current results ("can you close them", "add those to the shortlist").
"Closed", "shortlisted" and "close to London" never count, and "shortlist" as a noun
("everyone on the Java shortlist") is not a verb.
"""
import re

REFERENT = r"(?:all\s+(?:of\s+)?(?:them|these|those|the\s+results)|them|these|those|all|everyone|everybody|the\s+results)"
_START = r"^\s*(?:(?:please|ok(?:ay)?|now|then|and|so|can\s+you|could\s+you|would\s+you)[\s,]+)*"
# "close to London", "close by Leeds": an adjective about a place, not the verb.
_NOT_CLOSE = r"\s+(?:to|by|near|enough|proximity)\b"

SHORTLIST = [
    re.compile(_START + r"shortlist\b", re.I),                                   # shortlist ... (at the start)
    re.compile(r"\bshortlist\s+" + REFERENT + r"\b", re.I),                      # ... shortlist them ...
    re.compile(_START + r"(?:add|put)\b.*?\b(?:to|on|onto|in)\b.*\bshortlist\b", re.I),
    re.compile(r"\b(?:add|put)\s+" + REFERENT + r"\b.*?\b(?:to|on|onto|in)\b.*\bshortlist\b", re.I),
]
CLOSE_START = re.compile(_START + r"close\b(?!" + _NOT_CLOSE + r")", re.I)
CLOSE_REFERENT = re.compile(r"\bclose\s+" + REFERENT + r"\b", re.I)

# Words that carry no information about which job is meant.
STOP = set("""
a an the to for at in on onto of and or with as by from into please ok okay now then so just also too can
could would you me my our we us i is are this that it its
add put shortlist close them these those all everyone everybody results result lot
candidate candidates people person one ones
job jobs role roles position positions vacancy vacancies opening openings posting postings list
""".split())


def _words(text):
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9.+#-]*[A-Za-z0-9+#]|[A-Za-z0-9]", text)


def _stem(word):
    """Lower-case, and 'developers' -> 'developer', so a plural still matches a title."""
    w = word.lower()
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def parse(text):
    """None if the text is not a write command; otherwise {"action": ..., "job_words": [...]}.
    job_words are the words left once the verb, the referent and stop-words are gone (shortlist only)."""
    text = (text or "").strip()
    if not text:
        return None
    if any(p.search(text) for p in SHORTLIST):
        words = [w for w in _words(text) if w.lower() not in STOP]
        return {"action": "shortlist", "job_words": words}
    if CLOSE_REFERENT.search(text) or CLOSE_START.search(text):
        # Close works on the results on screen, so nothing else may describe which jobs:
        # "close these 3 jobs" is a command, "close all Java jobs in London" is a new search.
        rest = [w for w in _words(text) if w.lower() not in STOP and not w.isdigit()]
        if not rest:
            return {"action": "close", "job_words": []}
    return None


def match_jobs(words, jobs):
    """The jobs the words point to, by whole words of title, company and city, case-insensitive.

    A job must match at least one word there. Jobs matching the most such words win; a tie is
    broken by the job's skills, so "the Java shortlist at Bluefin" finds Bluefin's Java job rather
    than every Bluefin job and every Java job. Skills alone never pick a job.
    Returns (jobs, the words that matched them, in the order typed, and whether every job matched
    every one of those words)."""
    wanted = []
    for w in words:
        if _stem(w) not in [s for _, s in wanted]:
            wanted.append((w, _stem(w)))
    scored = []
    for job in jobs:
        named = {_stem(w) for w in _words(" ".join((job["title"], job["company"], job["city"])))}
        skills = {_stem(w) for w in _words(" ".join(job["skills"]))}
        hit = {s for _, s in wanted if s in named}
        if hit:
            extra = {s for _, s in wanted if s in skills} - hit
            scored.append(((len(hit), len(extra)), job, hit | extra))
    if not scored:
        return [], [], True
    best = max(score for score, _, _ in scored)
    chosen = [(job, hit) for score, job, hit in scored if score == best]
    union = set().union(*(hit for _, hit in chosen))
    matched = [w for w, s in wanted if s in union]
    return [job for job, _ in chosen], matched, all(hit == union for _, hit in chosen)
