import httpx

base = "https://support.wirenboard.com"
headers = {
    "Api-Key": "5a847cbd1ab985c9a052e1035849798704a7af46a4a6122f3560a9054469aeb8",
    "Api-Username": "system",
}
query_id = 41
sql = """
SELECT DISTINCT ON (t.id)
  t.id AS topic_id,
  CONCAT('https://support.wirenboard.com/t/', t.id) AS topic_link,
  t.title AS topic_title,
  u.username AS assigned_user,
  t.updated_at AS last_updated
FROM topics t
JOIN topic_custom_fields tcf ON t.id = tcf.topic_id
JOIN posts p_acc ON p_acc.id = tcf.value::integer AND p_acc.topic_id = t.id
JOIN post_custom_fields pcf ON pcf.post_id = p_acc.id
JOIN assignments a ON t.id = a.topic_id
JOIN users u ON a.assigned_to_id = u.id
WHERE tcf.name = 'accepted_answer_post_id'
  AND tcf.value ~ '^[0-9]+$'
  AND pcf.name = 'is_accepted_answer'
  AND pcf.value = 'true'
  AND p_acc.deleted_at IS NULL
  AND t.archived = false
  AND t.closed = false
  AND t.updated_at >= NOW() - INTERVAL '5 months'
  AND NOT EXISTS (
    SELECT 1
    FROM posts p2
    WHERE p2.topic_id = t.id
      AND p2.raw LIKE '%эта тема была автоматически закрыта%'
  )
ORDER BY t.id, t.updated_at DESC
"""
client = httpx.Client(base_url=base, headers=headers, timeout=30)
q = client.get(f"/admin/plugins/explorer/queries/{query_id}.json")
q.raise_for_status()
existing = q.json().get("query") or q.json()
payload = {
    "name": existing.get("name") or "auto_unassign_solved_topics_v1",
    "description": existing.get("description") or "For discourse-assignee-automation service",
    "sql": sql,
}
r = client.put(f"/admin/plugins/explorer/queries/{query_id}", json=payload)
print("update_status", r.status_code)
r.raise_for_status()
run = client.post(f"/admin/plugins/explorer/queries/{query_id}/run", json={"params": {}})
print("run_status", run.status_code)
run.raise_for_status()
rows = run.json().get("rows", [])
print("rows_count", len(rows))
found = False
for row in rows:
    if isinstance(row, list) and row and int(row[0]) == 28686:
        found = True
    if isinstance(row, dict) and int(row.get("topic_id", -1)) == 28686:
        found = True
print("contains_28686", found)
