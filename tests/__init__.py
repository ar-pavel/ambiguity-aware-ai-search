"""Tests never touch the recruiter's real changes (state/state.json) or log: each run gets its own files."""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="a2-tests-")
os.environ["A2_STATE"] = os.path.join(_TMP, "state.json")
os.environ.setdefault("A2_LOG", "off")
