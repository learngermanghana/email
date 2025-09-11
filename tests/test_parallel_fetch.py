import time
from unittest.mock import patch
import pandas as pd
import importlib.util
from pathlib import Path
import sys

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
    with patch("pandas.read_csv", return_value=dummy_df):
        spec.loader.exec_module(email_module)

    urls = {"logo": "logo_url", "watermark": "watermark_url"}

    class DummyResp:
        def __init__(self, content):
            self.status_code = 200
            self.content = content

    def slow_get(url):
        time.sleep(0.2)
        return DummyResp(url.encode())

    def sequential():
        results = {}
        for k, u in urls.items():
            resp = slow_get(u)
            results[k] = resp.content
        return results

    start = time.time()
    sequential()
    seq_time = time.time() - start

    with patch.object(email_module.requests, "get", side_effect=slow_get):
        start = time.time()
        results = email_module.fetch_assets(urls)
        par_time = time.time() - start

    assert par_time < seq_time
    assert results["logo"] == b"logo_url"
    assert results["watermark"] == b"watermark_url"
