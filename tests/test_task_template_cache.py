from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Ensure repository root is on sys.path for module imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import todo
import social_templates


def _doc(data, doc_id="id"):
    d = MagicMock()
    d.to_dict.return_value = data
    d.id = doc_id
    return d


def test_load_tasks_cache_and_clears_on_add():
    todo.load_tasks.clear()
    db = MagicMock()
    coll = db.collection.return_value
    where = coll.where.return_value
    select = where.select.return_value
    select.stream.return_value = [_doc({"description": "t1", "assignee": "a1", "week": "w1", "due": "d1", "completed": False}, "id1")]
    with patch("todo._get_db", return_value=db):
        first = todo.load_tasks("w1")
        second = todo.load_tasks("w1")
        assert first == second
        assert select.stream.call_count == 1
        where.select.assert_called_once_with([
            "description",
            "assignee",
            "week",
            "due",
            "completed",
        ])

        select.stream.return_value = [_doc({"description": "t2", "assignee": "a2", "week": "w1", "due": "d", "completed": False}, "id2")]
        todo.add_task("t2", "a2", "w1", "d")
        refreshed = todo.load_tasks("w1")
    assert refreshed == [
        {
            "description": "t2",
            "assignee": "a2",
            "week": "w1",
            "due": "d",
            "completed": False,
            "id": "id2",
        }
    ]


def test_update_task_clears_cache():
    with patch("todo._get_db") as get_db, patch.object(todo.load_tasks, "clear") as mock_clear:
        doc_ref = MagicMock()
        get_db.return_value.collection.return_value.document.return_value = doc_ref
        todo.update_task("id1", {"completed": True})
        doc_ref.update.assert_called_once_with({"completed": True})
        mock_clear.assert_called_once()


def test_load_templates_cache_and_clears_on_add():
    social_templates.load_templates.clear()
    db = MagicMock()
    coll = db.collection.return_value
    select = coll.select.return_value
    select.stream.return_value = [_doc({"title": "tmp1", "platform": "p1", "content": "c1"}, "id1")]
    with patch("social_templates._get_db", return_value=db):
        first = social_templates.load_templates()
        second = social_templates.load_templates()
        assert first == second
        assert select.stream.call_count == 1
        coll.select.assert_called_once_with(["title", "platform", "content"])

        select.stream.return_value = [_doc({"title": "tmp2", "platform": "p2", "content": "c2"}, "id2")]
        social_templates.add_template("tmp2", "p2", "c2")
        refreshed = social_templates.load_templates()
    assert refreshed == [{"title": "tmp2", "platform": "p2", "content": "c2", "id": "id2"}]


def test_delete_template_clears_cache():
    with patch("social_templates._get_db") as get_db, patch.object(social_templates.load_templates, "clear") as mock_clear:
        doc_ref = MagicMock()
        get_db.return_value.collection.return_value.document.return_value = doc_ref
        social_templates.delete_template("id1")
        doc_ref.delete.assert_called_once()
        mock_clear.assert_called_once()
