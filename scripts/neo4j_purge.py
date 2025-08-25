import os
import sys
from neo4j import GraphDatabase

# Ensure project root is on sys.path when running as a script
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.settings import settings  # noqa: E402

# Load from pydantic settings (.env)
uri = settings.neo4j_uri or (
    f"neo4j+s://{settings.aura_instanceid}.databases.neo4j.io" if settings.aura_instanceid else None
)
user = settings.neo4j_username
pwd = settings.neo4j_password
db = settings.neo4j_database or "neo4j"

if not uri or not user or not pwd:
    raise SystemExit("Missing Neo4j connection settings; check .env or env vars")

driver = GraphDatabase.driver(uri, auth=(user, pwd))

with driver.session(database=db) as s:
    s.run("MATCH (n) DETACH DELETE n").consume()
    # Drop vector index if exists (ignore errors)
    try:
        s.run("DROP INDEX infinitepay_chunks IF EXISTS").consume()
    except Exception:
        pass

print("Neo4j database purged.")
