import re
import os
import json
import logging
import requests
from dotenv import load_dotenv

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential, before_sleep_log


load_dotenv()

logger = logging.getLogger(__name__)

# Define retry strategy parameters
RETRY_TIMES = int(os.getenv('RETRY_TIMES'))
WAIT_TIME_LOWER = int(os.getenv('WAIT_TIME_LOWER'))
WAIT_TIME_UPPER = int(os.getenv('WAIT_TIME_UPPER'))

OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
MODEL = os.getenv('OPENAI_MODEL')

# PATCH (rgp2 local-ollama setup): qwen3 models default to an extended
# "thinking" pass before answering -- on CPU-only local inference this adds
# several minutes of reasoning tokens per judge call (observed: single calls
# taking 3-5 min, some exceeding OPENAI_TIMEOUT and erroring outright).
# Ollama's OpenAI-COMPATIBLE endpoint (/v1/chat/completions) does not honor
# either qwen3's own "/no_think" in-text switch or a "think" request field --
# both were tried and verified to still emit full reasoning. Ollama's NATIVE
# endpoint (/api/chat) does honor "think": false (verified: ~4.5s vs ~2min+
# for the same prompt). So when RG_NO_THINK=1 we route through the native
# endpoint instead of the openai client, for every call. Off by default so
# this file still matches upstream when evaluating other frames/models.
_NO_THINK = os.getenv('RG_NO_THINK', '0') == '1'
# RG_PREFIX_NO_THINK: for OpenAI-compatible servers that DO honor qwen3's
# in-text /no_think switch (llama-cpp server on GPU, unlike ollama's /v1):
# just prefix the prompt -- no native-endpoint reroute needed.
_PREFIX_NO_THINK = os.getenv('RG_PREFIX_NO_THINK', '0') == '1'
_THINK_RX = None
_NATIVE_CHAT_URL = None
if _NO_THINK:
    _base = (os.getenv('OPENAI_BASE_URL') or '').rstrip('/')
    _NATIVE_CHAT_URL = (_base[:-3] if _base.endswith('/v1') else _base) + '/api/chat'


# ---------------------------------------------------------------------------
# PATCH (rgp2, 2026-09-09): A JUDGE-VERDICT CACHE.
#
# Every judge stage (integrity, accuracy, update, QA) reaches the model
# through llm_request / llm_request_for_json, so one cache here covers all
# four. Two reasons it exists:
#
#   1. CRASH RESUME. evaluation.py checkpoints only when a whole USER
#      finishes, so a machine reboot at 88% of a 6-hour accuracy pass threw
#      away 6 hours (2026-09-07). With the cache a re-run replays every
#      verdict already earned and only pays for what is new.
#   2. VARIANT ROWS ARE MOSTLY THE SAME RECORDS. An extraction variant that
#      ADDS records leaves the prompts of the unchanged ones byte-identical,
#      so its accuracy pass costs only the delta.
#
# Keyed on (model, call shape, exact prompt) -- a different model or a
# changed prompt can never hit. Verdicts are appended to one JSONL shard per
# PID, so the ProcessPoolExecutor workers never interleave a line; readers
# glob every shard. Set RG_JUDGE_CACHE=0 to disable, RG_JUDGE_CACHE_DIR to
# relocate.
import hashlib
import glob as _glob

_CACHE_ON = os.getenv('RG_JUDGE_CACHE', '1') != '0'
_CACHE_DIR = os.path.expanduser(
    os.getenv('RG_JUDGE_CACHE_DIR',
              '~/rg_private/halumem/judge_cache'))
_CACHE = {}
_CACHE_FH = None
_CACHE_FH_PID = None


def _cache_key(kind, prompt):
    h = hashlib.sha1()
    h.update((MODEL or '').encode())
    h.update(b'\x00' + kind.encode() + b'\x00')
    h.update((prompt or '').encode())
    return h.hexdigest()


def _cache_load():
    if not _CACHE_ON:
        return
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        for f in _glob.glob(os.path.join(_CACHE_DIR, '*.jsonl')):
            with open(f, encoding='utf-8') as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        _CACHE[d['k']] = d['v']
                    except Exception:
                        continue          # a torn line is a miss, never a crash
    except Exception:
        pass


def _cache_get(key):
    return _CACHE.get(key) if _CACHE_ON else None


def _cache_put(key, value):
    global _CACHE_FH, _CACHE_FH_PID
    if not _CACHE_ON:
        return
    _CACHE[key] = value
    try:
        pid = os.getpid()
        if _CACHE_FH is None or _CACHE_FH_PID != pid:
            # reopened after a fork: each worker owns its own shard
            os.makedirs(_CACHE_DIR, exist_ok=True)
            _CACHE_FH = open(os.path.join(_CACHE_DIR, f'{pid}.jsonl'),
                             'a', encoding='utf-8')
            _CACHE_FH_PID = pid
        _CACHE_FH.write(json.dumps({'k': key, 'v': value}) + '\n')
        _CACHE_FH.flush()
    except Exception:
        pass                              # a cache write must never fail a run


_cache_load()


common_params = {}

if os.getenv('OPENAI_MAX_TOKENS'):
    common_params["max_tokens"] = int(os.getenv('OPENAI_MAX_TOKENS'))

if os.getenv('OPENAI_TEMPERATURE'):
    common_params["temperature"] = float(os.getenv('OPENAI_TEMPERATURE'))

if os.getenv('OPENAI_TIMEOUT'):
    common_params["timeout"] = int(os.getenv('OPENAI_TIMEOUT'))


client = OpenAI(
    base_url=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY
)


def _native_ollama_chat(prompt):
    """PATCH (rgp2): think:false via ollama's native /api/chat -- see the
    _NO_THINK comment above. Returns the same str shape as
    response_obj.choices[0].message.content would."""
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {},
    }
    if "temperature" in common_params:
        payload["options"]["temperature"] = common_params["temperature"]
    if "max_tokens" in common_params:
        payload["options"]["num_predict"] = common_params["max_tokens"]
    resp = requests.post(_NATIVE_CHAT_URL, json=payload,
                          timeout=common_params.get("timeout", 300))
    resp.raise_for_status()
    return resp.json()["message"]["content"]


@retry(
    wait=wait_random_exponential(min=WAIT_TIME_LOWER, max=WAIT_TIME_UPPER),
    stop=stop_after_attempt(RETRY_TIMES),
    reraise=True,
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def llm_request(prompt):
    """
    Sends a request to the specified language model with a given prompt.

    Args:
        prompt (str): The input text or message to send to the model.

    Returns:
        str: The response generated by the model.
    """

    _key = _cache_key('str', prompt)
    _hit = _cache_get(_key)
    if _hit is not None:
        return _hit

    if _NO_THINK:
        _out = _native_ollama_chat(prompt)
        _cache_put(_key, _out)
        return _out
    if _PREFIX_NO_THINK:
        prompt = '/no_think ' + prompt

    response_obj = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                'role': 'user',
                'content': prompt
            }
        ],
        **common_params
    )

    content = response_obj.choices[0].message.content or ''
    _out = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    _cache_put(_key, _out)
    return _out

@retry(
    wait=wait_random_exponential(min=WAIT_TIME_LOWER, max=WAIT_TIME_UPPER),
    stop=stop_after_attempt(RETRY_TIMES),
    reraise=True,
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def llm_request_for_json(prompt):

    _key = _cache_key('json', prompt)
    _hit = _cache_get(_key)
    if _hit is not None:
        return _hit

    if _NO_THINK:
        content = _native_ollama_chat(prompt)
    else:
        if _PREFIX_NO_THINK:
            prompt = '/no_think ' + prompt
        response_obj = client.chat.completions.create(
            model=MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            **common_params
        )
        content = response_obj.choices[0].message.content or ""
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

    match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON block found in model output: {content}")

    json_str = match.group(1).strip()

    _out = json.loads(json_str)
    _cache_put(_key, _out)
    return _out


if __name__ == '__main__':
    r = llm_request_for_json('hello')
    print(r)