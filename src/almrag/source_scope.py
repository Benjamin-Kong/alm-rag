"""Current source selection is authoritative even before the next collection scan."""
import json


def allows_scope(c,project_uid,scope_id):
    selection=c.execute('SELECT selection_mode,scope_ids FROM project_selections WHERE project_uid=?',(project_uid,)).fetchone()
    if selection is None:return False
    return selection['selection_mode']=='ALL' or scope_id in json.loads(selection['scope_ids'])
