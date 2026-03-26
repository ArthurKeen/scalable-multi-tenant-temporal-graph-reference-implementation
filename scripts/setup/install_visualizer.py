#!/usr/bin/env python3
"""
Install ArangoDB Graph Visualizer customizations for both graphs:
  - network_assets_smartgraph (theme, canvas actions)
  - taxonomy_satellite_graph  (theme, canvas actions)

All visualizer collections are stored in the target database.
Idempotent -- safe to run repeatedly.

Usage:
    PYTHONPATH=. python3 scripts/setup/install_visualizer.py
"""
from __future__ import annotations

import copy
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from arango import ArangoClient

from src.config.centralized_credentials import CredentialsManager

logger = logging.getLogger(__name__)

ASSET_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "visualizer"

GRAPH_THEMES: Dict[str, Path] = {
    "network_assets_smartgraph": ASSET_DIR / "theme.json",
    "taxonomy_satellite_graph": ASSET_DIR / "taxonomy_theme.json",
}

SAVED_QUERY_FILES: Dict[str, Path] = {
    "network_assets_smartgraph": ASSET_DIR / "saved_queries.json",
    "taxonomy_satellite_graph": ASSET_DIR / "taxonomy_saved_queries.json",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_collection(db, name: str, *, edge: bool = False) -> None:
    if db.has_collection(name):
        return
    db.create_collection(name, edge=edge, system=name.startswith("_"))


def get_graph_schema(db, graph_name: str) -> Tuple[Set[str], Set[str]]:
    if not db.has_graph(graph_name):
        return set(), set()
    g = db.graph(graph_name)
    vertex_colls = set(g.vertex_collections())
    edge_defs = g.edge_definitions()
    edge_colls = set(ed["edge_collection"] for ed in edge_defs)
    return vertex_colls, edge_colls


def prune_theme(theme_raw: Dict, vertex_colls: Set[str], edge_colls: Set[str]) -> Dict:
    theme = copy.deepcopy(theme_raw)
    if "nodeConfigMap" in theme:
        theme["nodeConfigMap"] = {k: v for k, v in theme["nodeConfigMap"].items() if k in vertex_colls}
    if "edgeConfigMap" in theme:
        theme["edgeConfigMap"] = {k: v for k, v in theme["edgeConfigMap"].items() if k in edge_colls}
    return theme


def ensure_visualizer_shape(theme: Dict) -> None:
    for node_cfg in theme.get("nodeConfigMap", {}).values():
        node_cfg.setdefault("rules", [])
        node_cfg.setdefault("hoverInfoAttributes", [])
    for edge_cfg in theme.get("edgeConfigMap", {}).values():
        edge_cfg.setdefault("rules", [])
        edge_cfg.setdefault("hoverInfoAttributes", [])
        edge_cfg.setdefault("arrowStyle", {"sourceArrowShape": "none", "targetArrowShape": "triangle"})
        edge_cfg.setdefault("labelStyle", {"color": "#1d2531"})


def ensure_default_viewpoint(db, graph_name: str) -> str:
    ensure_collection(db, "_viewpoints")
    vp_col = db.collection("_viewpoints")

    existing = list(vp_col.find({"graphId": graph_name, "name": "Default"}))
    if existing:
        return existing[0]["_id"]

    ts = now_iso()
    res = vp_col.insert({
        "graphId": graph_name,
        "name": "Default",
        "description": f"Default viewpoint for {graph_name}",
        "createdAt": ts,
        "updatedAt": ts,
    })
    return res["_id"]


def _upsert_canvas_action(
    canvas_col, vp_act_col, vp_id: str,
    graph_name: str, name: str, description: str,
    query_text: str, bind_vars: Dict, ts: str,
) -> str:
    existing = list(canvas_col.find({"name": name, "graphId": graph_name}))
    if existing:
        existing = sorted(existing, key=lambda d: d.get("_key", ""))
        for extra in existing[1:]:
            try:
                canvas_col.delete(extra["_key"])
            except Exception as e:
                logger.warning(f"Failed to delete duplicate canvas action {extra['_key']}: {e}")
        doc = {
            "graphId": graph_name,
            "name": name,
            "description": description,
            "queryText": query_text,
            "bindVariables": bind_vars,
            "updatedAt": ts,
            "_key": existing[0]["_key"],
            "_id": existing[0]["_id"],
            "createdAt": existing[0].get("createdAt", ts),
        }
        canvas_col.replace(doc, check_rev=False)
        action_id = existing[0]["_id"]
    else:
        doc = {
            "graphId": graph_name,
            "name": name,
            "description": description,
            "queryText": query_text,
            "bindVariables": bind_vars,
            "createdAt": ts,
            "updatedAt": ts,
        }
        res = canvas_col.insert(doc)
        action_id = res["_id"]

    if not list(vp_act_col.find({"_from": vp_id, "_to": action_id})):
        vp_act_col.insert({"_from": vp_id, "_to": action_id, "createdAt": ts, "updatedAt": ts})
    return action_id


def install_canvas_actions(db, graph_name: str, vertex_colls: Set[str], edge_colls: Set[str]) -> int:
    ensure_collection(db, "_canvasActions")
    ensure_collection(db, "_viewpointActions", edge=True)
    canvas_col = db.collection("_canvasActions")
    vp_act_col = db.collection("_viewpointActions")
    vp_id = ensure_default_viewpoint(db, graph_name)

    edge_list_str = ", ".join(sorted(edge_colls))
    with_clause = "WITH " + ", ".join(sorted(vertex_colls | edge_colls))
    ts = now_iso()
    count = 0

    default_query = f"""{with_clause}
FOR node IN @nodes
  FOR v, e IN 1..2 ANY node GRAPH "{graph_name}"
  LIMIT 100
  RETURN e"""
    _upsert_canvas_action(
        canvas_col, vp_act_col, vp_id, graph_name,
        "Find 2-hop neighbors (default)",
        "Find 2-hop neighbors of the selected nodes",
        default_query, {"nodes": []}, ts,
    )
    count += 1

    for v_coll in sorted(vertex_colls):
        query = f"""{with_clause}
FOR node IN @nodes
  FILTER IS_SAME_COLLECTION("{v_coll}", node)
  FOR v, e, p IN 1..1 ANY node {edge_list_str}
  LIMIT 20
  RETURN p"""
        _upsert_canvas_action(
            canvas_col, vp_act_col, vp_id, graph_name,
            f"[{v_coll}] Expand Relationships",
            f"Expand related entities for {v_coll}",
            query, {"nodes": []}, ts,
        )
        count += 1

    return count


def install_saved_queries(
    db, *, queries: List[Dict[str, Any]], database_name: str,
) -> int:
    """Install queries into _editor_saved_queries for the global query editor."""
    ensure_collection(db, "_editor_saved_queries")
    col = db.collection("_editor_saved_queries")
    ts = now_iso()
    processed = 0

    for q in queries:
        if "title" not in q and "name" in q:
            q["title"] = q["name"]
        q.setdefault("name", q.get("title") or "Untitled query")

        aql_text = q.pop("queryText", None) or q.get("content", "")
        q["content"] = aql_text
        q["value"] = aql_text

        q.setdefault("bindVariables", {})
        q["updatedAt"] = ts
        q.setdefault("createdAt", ts)
        q.setdefault("databaseName", database_name)

        key = q.pop("_key", None)
        if key:
            q["_key"] = key
            if col.has(key):
                col.replace(q)
            else:
                col.insert(q)
        else:
            existing = list(col.find({"title": q["title"]}))
            if existing:
                q["_key"] = existing[0]["_key"]
                col.replace(q)
            else:
                col.insert(q)
        processed += 1
    return processed


def _upsert_graph_query(
    queries_col, vp_q_col, vp_id: str,
    graph_name: str, name: str, description: str,
    query_text: str, bind_vars: Dict, ts: str,
) -> str:
    """Upsert a stored query into _queries and link to the viewpoint."""
    existing = list(queries_col.find({"name": name, "graphId": graph_name}))
    if existing:
        existing = sorted(existing, key=lambda d: d.get("_key", ""))
        for extra in existing[1:]:
            try:
                queries_col.delete(extra["_key"])
            except Exception as e:
                logger.warning(f"Failed to delete duplicate graph query {extra['_key']}: {e}")
        doc = {
            "graphId": graph_name,
            "name": name,
            "description": description,
            "queryText": query_text,
            "bindVariables": bind_vars,
            "updatedAt": ts,
            "_key": existing[0]["_key"],
            "_id": existing[0]["_id"],
            "createdAt": existing[0].get("createdAt", ts),
        }
        queries_col.replace(doc, check_rev=False)
        query_id = existing[0]["_id"]
    else:
        doc = {
            "graphId": graph_name,
            "name": name,
            "description": description,
            "queryText": query_text,
            "bindVariables": bind_vars,
            "createdAt": ts,
            "updatedAt": ts,
        }
        res = queries_col.insert(doc)
        query_id = res["_id"]

    if not list(vp_q_col.find({"_from": vp_id, "_to": query_id})):
        vp_q_col.insert({"_from": vp_id, "_to": query_id, "createdAt": ts, "updatedAt": ts})
    return query_id


def install_graph_queries(
    db, graph_name: str, vertex_colls: Set[str], edge_colls: Set[str],
) -> int:
    """Install starter queries into _queries for the Graph Visualizer Queries panel.

    These queries load initial vertices/subgraphs for demo scenarios.
    Linked to viewpoints via _viewpointQueries edges.
    """
    ensure_collection(db, "_queries")
    ensure_collection(db, "_viewpointQueries", edge=True)
    queries_col = db.collection("_queries")
    vp_q_col = db.collection("_viewpointQueries")
    vp_id = ensure_default_viewpoint(db, graph_name)

    with_clause = "WITH " + ", ".join(sorted(vertex_colls | edge_colls))
    ts = now_iso()
    count = 0

    if graph_name == "network_assets_smartgraph":
        _upsert_graph_query(
            queries_col, vp_q_col, vp_id, graph_name,
            "Load Tenant Network",
            "Load device network topology for a tenant (starting nodes for demo)",
            f"""{with_clause}
FOR proxy IN DeviceProxyIn
  FILTER proxy.tenantId == @tenantId
  LIMIT @limit
  FOR v, e, p IN 1..2 OUTBOUND proxy GRAPH "{graph_name}"
    OPTIONS {{order: "bfs", uniqueVertices: "global"}}
    LIMIT 200
    RETURN p""",
            {"tenantId": "1b45406a99d9", "limit": 5}, ts,
        )
        count += 1

        _upsert_graph_query(
            queries_col, vp_q_col, vp_id, graph_name,
            "Device with Full Context",
            "Load a device with its software, location, connections, and classification",
            f"""{with_clause}
FOR proxy IN DeviceProxyIn
  FILTER proxy._key == @deviceProxy
  FOR v, e, p IN 1..3 OUTBOUND proxy GRAPH "{graph_name}"
    OPTIONS {{order: "bfs", uniqueVertices: "global"}}
    LIMIT 100
    RETURN p""",
            {"deviceProxy": "1b45406a99d9:device1"}, ts,
        )
        count += 1

        _upsert_graph_query(
            queries_col, vp_q_col, vp_id, graph_name,
            "Time Travel: Current Device Versions",
            "Show only current (non-expired) device versions for a tenant",
            f"""{with_clause}
FOR proxy IN DeviceProxyIn
  FILTER proxy.tenantId == @tenantId
  FOR device, edge IN 1..1 OUTBOUND proxy hasVersion
    FILTER edge.expired == 9223372036854775807
    RETURN {{proxy: proxy, device: device, edge: edge}}""",
            {"tenantId": "1b45406a99d9"}, ts,
        )
        count += 1

        _upsert_graph_query(
            queries_col, vp_q_col, vp_id, graph_name,
            "Network Connections",
            "Show device-to-device connections for a tenant",
            f"""{with_clause}
FOR conn IN hasConnection
  FILTER conn.tenantId == @tenantId
  LET fromNode = DOCUMENT(conn._from)
  LET toNode = DOCUMENT(conn._to)
  RETURN {{from: fromNode, to: toNode, edge: conn}}""",
            {"tenantId": "1b45406a99d9"}, ts,
        )
        count += 1

    elif graph_name == "taxonomy_satellite_graph":
        _upsert_graph_query(
            queries_col, vp_q_col, vp_id, graph_name,
            "Full Taxonomy Tree",
            "Load the complete class hierarchy",
            f"""{with_clause}
FOR cls IN Class
  FOR v, e, p IN 0..5 OUTBOUND cls subClassOf
    RETURN p""",
            {}, ts,
        )
        count += 1

        _upsert_graph_query(
            queries_col, vp_q_col, vp_id, graph_name,
            "Device Taxonomy Branch",
            "Show the device classification hierarchy",
            f"""{with_clause}
FOR cls IN Class
  FILTER cls.category == "device"
  FOR v, e, p IN 0..3 OUTBOUND cls subClassOf
    RETURN p""",
            {}, ts,
        )
        count += 1

    return count


def _ensure_default_theme(
    theme_col, graph_name: str, vertex_colls: Set[str], edge_colls: Set[str]
) -> None:
    """Ensure a plain 'Default' theme exists so the user can switch back."""
    if list(theme_col.find({"name": "Default", "graphId": graph_name})):
        return
    ts = now_iso()
    node_config = {
        v: {"background": {}, "labelAttribute": "_key", "hoverInfoAttributes": ["_key", "_id"], "rules": []}
        for v in sorted(vertex_colls)
    }
    edge_config = {
        e: {
            "lineStyle": {},
            "arrowStyle": {"sourceArrowShape": "none", "targetArrowShape": "triangle"},
            "hoverInfoAttributes": [], "rules": [], "labelStyle": {"color": "#1d2531"},
        }
        for e in sorted(edge_colls)
    }
    theme_col.insert({
        "name": "Default",
        "description": f"Default theme for {graph_name}",
        "graphId": graph_name,
        "nodeConfigMap": node_config,
        "edgeConfigMap": edge_config,
        "isDefault": False,
        "createdAt": ts,
        "updatedAt": ts,
    })


def install_all(db, *, database_name: str) -> List[Dict[str, Any]]:
    """Install themes, saved queries, and canvas actions for all configured graphs.

    Called by the deployment pipeline and by main() when run standalone.
    """
    ensure_collection(db, "_graphThemeStore")
    theme_col = db.collection("_graphThemeStore")
    results = []

    for graph_name, theme_path in GRAPH_THEMES.items():
        result: Dict[str, Any] = {"graph_id": graph_name}

        if not db.has_graph(graph_name):
            result["skipped"] = True
            results.append(result)
            continue

        vertex_colls, edge_colls = get_graph_schema(db, graph_name)

        # Install theme
        raw = json.loads(theme_path.read_text(encoding="utf-8"))
        theme = prune_theme(raw, vertex_colls, edge_colls)
        theme["graphId"] = graph_name
        ts = now_iso()
        theme["createdAt"] = ts
        theme["updatedAt"] = ts
        theme["isDefault"] = True
        ensure_visualizer_shape(theme)

        existing = list(theme_col.find({"name": theme["name"], "graphId": graph_name}))
        if existing:
            theme["_key"] = existing[0]["_key"]
            theme["_id"] = existing[0]["_id"]
            theme_col.replace(theme, check_rev=False)
        else:
            theme_col.insert(theme)
        result["theme_name"] = theme["name"]

        _ensure_default_theme(theme_col, graph_name, vertex_colls, edge_colls)

        # Install editor saved queries (global query editor)
        queries_path = SAVED_QUERY_FILES.get(graph_name)
        if queries_path and queries_path.exists():
            queries = json.loads(queries_path.read_text(encoding="utf-8"))
            result["editor_query_count"] = install_saved_queries(
                db, queries=queries, database_name=database_name,
            )
        else:
            result["editor_query_count"] = 0

        # Install graph visualizer stored queries (_queries collection)
        result["graph_query_count"] = install_graph_queries(
            db, graph_name, vertex_colls, edge_colls,
        )

        # Install canvas actions
        result["action_count"] = install_canvas_actions(db, graph_name, vertex_colls, edge_colls)

        results.append(result)

    return results


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    creds = CredentialsManager.get_database_credentials()
    client = ArangoClient(hosts=creds.endpoint)
    db = client.db(creds.database_name, username=creds.username, password=creds.password)

    print(f"Installing visualizer assets")
    print(f"  Database: {creds.database_name}")
    print(f"  Endpoint: {creds.endpoint}")
    print()

    results = install_all(db, database_name=creds.database_name)

    for r in results:
        graph_id = r["graph_id"]
        if r.get("skipped"):
            print(f"  [{graph_id}] SKIPPED (graph not found)")
            continue
        print(f"  [{graph_id}]")
        print(f"    Theme:            {r['theme_name']} (isDefault=true)")
        print(f"    Editor queries:   {r.get('editor_query_count', 0)}")
        print(f"    Graph queries:    {r.get('graph_query_count', 0)}")
        print(f"    Canvas actions:   {r['action_count']}")
        print()

    print("Done. Refresh the Visualizer UI:")
    print("  - Theme: auto-applied (isDefault=true), or select from Legend dropdown")
    print("  - Saved queries: Queries panel")
    print("  - Canvas actions: right-click a node in the graph")


if __name__ == "__main__":
    main()
