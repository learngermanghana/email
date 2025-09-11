from unittest.mock import MagicMock, patch
import sys
from pathlib import Path
import streamlit as st

# Ensure repository root is on sys.path for module imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import social_templates


def _doc(data, doc_id="id"):
    d = MagicMock()
    d.to_dict.return_value = data
    d.id = doc_id
    return d


def test_load_templates_snapshot_updates_state_and_reruns():
    st.session_state.clear()
    db = MagicMock()
    coll = db.collection.return_value
    query = coll.select.return_value
    listener = MagicMock()
    callback_holder = {}

    def on_snapshot(cb):
        callback_holder["cb"] = cb
        return listener

    query.on_snapshot.side_effect = on_snapshot
    with patch("social_templates._get_db", return_value=db), patch(
        "streamlit.rerun", create=True
    ) as rerun:
        assert social_templates.load_templates() == []
        callback_holder["cb"](
            [_doc({"title": "tmp1", "platform": "p", "content": "c"}, "id1")],
            [],
            None,
        )
        assert st.session_state["templates"] == [
            {"title": "tmp1", "platform": "p", "content": "c", "id": "id1"}
        ]
        rerun.assert_called_once()
