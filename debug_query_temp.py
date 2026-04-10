import httpx

base = "https://support.wirenboard.com"
headers = {"Api-Key": "5a847cbd1ab985c9a052e1035849798704a7af46a4a6122f3560a9054469aeb8", "Api-Username": "system"}
name = "debug_topic_28686_temp"
sql = """
WITH topic_fields AS (
  SELECT 'topic_custom_fields' AS src, name, value
  FROM topic_custom_fields
  WHERE topic_id = 28686
),
post_fields AS (
  SELECT 'post_custom_fields' AS src, pcf.name, pcf.value
  FROM posts p
  JOIN post_custom_fields pcf ON pcf.post_id = p.id
  WHERE p.topic_id = 28686
)
SELECT * FROM topic_fields
UNION ALL
SELECT * FROM post_fields
ORDER BY src, name;
"""
client = httpx.Client(base_url=base, headers=headers, timeout=30)
queries = client.get('/admin/plugins/explorer/queries.json')
queries.raise_for_status()
qid = None
for q in queries.json().get('queries', []):
    if q.get('name') == name:
        qid = q.get('id')
        break
if qid is None:
    create = client.post('/admin/plugins/explorer/queries', json={'name':name,'description':'temp debug','sql':sql})
    create.raise_for_status()
    # API returns query list-like payload; re-fetch id by name
    queries = client.get('/admin/plugins/explorer/queries.json')
    queries.raise_for_status()
    for q in queries.json().get('queries', []):
        if q.get('name') == name:
            qid = q.get('id')
            break
else:
    upd = client.put(f'/admin/plugins/explorer/queries/{qid}', json={'name':name,'description':'temp debug','sql':sql})
    upd.raise_for_status()
run = client.post(f'/admin/plugins/explorer/queries/{qid}/run', json={'params':{}})
run.raise_for_status()
res = run.json()
cols = res.get('columns', [])
rows = res.get('rows', [])
print('qid', qid, 'rows', len(rows))
print('columns', cols)
for r in rows[:200]:
    print(r)
