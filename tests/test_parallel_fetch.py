import time
from unittest.mock import patch
import pandas as pd
import importlib.util
from pathlib import Path
import sys
import os

# Ensure repository root is on path for module dependencies
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_fetch_assets_parallel():
    module_path = Path(__file__).resolve().parents[1] / "email.py"
    spec = importlib.util.spec_from_file_location("email_module", module_path)
    email_module = importlib.util.module_from_spec(spec)

    dummy_df = pd.DataFrame({
        "studentcode": ["s0"],
        "level": ["A0"],
        "name": ["n0"],
        "phone": ["p0"],
        "paid": ["0"],
        "balance": ["0"],
        "contractstart": ["2020-01-01"],
        "contractend": ["2020-02-01"],
        "assignment": ["a0"],
    })
    def fake_radio(label, options, **kwargs):
        return options[0]

    with patch.dict(os.environ, {"EMAIL_SKIP_PRELOAD": "1"}), \
         patch("streamlit.sidebar.radio", side_effect=fake_radio):
        spec.loader.exec_module(email_module)

    urls = {"logo": "logo_url", "watermark": "watermark_url"}

    def slow_fetch(url, timeout=10):  # match fetch_url signature
        time.sleep(0.2)
        return url.encode()

    def sequential():
        results = {}
        for k, u in urls.items():
            results[k] = slow_fetch(u)
        return results

    start = time.time()
    sequential()
    seq_time = time.time() - start

    with patch.object(email_module, "fetch_url", side_effect=slow_fetch):
        start = time.time()
        results = email_module.fetch_assets(urls)
        par_time = time.time() - start

    assert par_time < seq_time
    assert results["logo"] == b"logo_url"
    assert results["watermark"] == b"watermark_url"

