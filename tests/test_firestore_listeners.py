from unittest.mock import MagicMock, patch
import sys
from pathlib import Path
import streamlit as st

# Ensure repository root is on sys.path for module imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import todo
import social_templates


def _doc(data, doc_id="id"):
    d = MagicMock()
    d.to_dict.return_value = data
    d.id = doc_id
    return d


def test_load_tasks_snapshot_updates_state_and_reruns():
    st.session_state.clear()
    db = MagicMock()
    coll = db.collection.return_value
    where = coll.where.return_value
    query = where.select.return_value
    listener = MagicMock()
    callback_holder = {}

    def on_snapshot(cb):
        callback_holder["cb"] = cb
        return listener

    query.on_snapshot.side_effect = on_snapshot
    with patch("todo._get_db", return_value=db), patch(
        "streamlit.experimental_rerun", create=True
    ) as rerun:
        assert todo.load_tasks("w1") == []
        callback_holder["cb"](
            [
                _doc(
                    {
                        "description": "t1",
                        "assignee": "a1",
                        "week": "w1",
                        "due": "d",
                        "completed": False,
                    },
                    "id1",
                )
            ],
            [],
            None,
        )
        assert st.session_state["tasks"] == [
            {
                "description": "t1",
                "assignee": "a1",
                "week": "w1",
                "due": "d",
                "completed": False,
                "id": "id1",
            }
        ]
        rerun.assert_called_once()


def test_load_tasks_replaces_listener_on_week_change():
    st.session_state.clear()
    db = MagicMock()
    coll = db.collection.return_value
    where = coll.where.return_value
    query = where.select.return_value
    listener1 = MagicMock()
    listener2 = MagicMock()
    query.on_snapshot.side_effect = [listener1, listener2]
    with patch("todo._get_db", return_value=db), patch(
        "streamlit.experimental_rerun", create=True
    ):
        todo.load_tasks("w1")
        todo.load_tasks("w2")
    listener1.unsubscribe.assert_called_once()
    assert st.session_state["task_listener"] is listener2
    assert st.session_state["task_listener_week"] == "w2"


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
        "streamlit.experimental_rerun", create=True
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
