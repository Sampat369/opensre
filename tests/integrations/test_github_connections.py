"""Stable public IDs for GitHub connections, including named instances.

Multi-instance IDs follow ``<record-id>::instance:<URL-encoded-name>``;
single-instance records retain their historical record ID.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from integrations.github import connections


def test_named_instances_have_stable_independent_connection_ids(monkeypatch) -> None:
    monkeypatch.setattr(
        connections,
        "classify",
        lambda credentials, record_id: (
            SimpleNamespace(model_dump=lambda: {"auth_token": credentials["auth_token"]}),
            "github",
        ),
    )
    monkeypatch.setattr(connections, "github_mcp_is_usably_configured", lambda config: True)
    records = [
        {
            "id": "github-local",
            "service": "github",
            "status": "active",
            "instances": [
                {"name": "work", "credentials": {"auth_token": "work-token"}},
                {"name": "personal", "credentials": {"auth_token": "personal-token"}},
            ],
        }
    ]

    resolved = {}
    connections.classify_github_connections(records, resolved)
    choices = resolved["_all_github_instances"]
    assert [choice["name"] for choice in choices] == ["work", "personal"]
    assert [choice["connection_id"] for choice in choices] == [
        "github-local::instance:work",
        "github-local::instance:personal",
    ]

    # Reloading serialized records and building a fresh resolver preserves the IDs.
    reloaded = json.loads(json.dumps(records))
    fresh = {}
    connections.classify_github_connections(reloaded, fresh)
    assert [choice["connection_id"] for choice in fresh["_all_github_instances"]] == [
        choice["connection_id"] for choice in choices
    ]

    for choice, token in zip(choices, ("work-token", "personal-token"), strict=True):
        selected = connections.select_github_connection(resolved, choice["connection_id"])
        assert selected["github"]["auth_token"] == token
        assert selected["github"]["connection_id"] == choice["connection_id"]

    ambiguous = connections.select_github_connection(resolved, "github-local")
    assert ambiguous["github"]["connection_verified"] is False


def test_single_instance_and_managed_connection_ids_remain_compatible(monkeypatch) -> None:
    monkeypatch.setattr(
        connections,
        "classify",
        lambda credentials, record_id: (
            SimpleNamespace(model_dump=lambda: {"auth_token": credentials.get("auth_token", "")}),
            "github",
        ),
    )
    monkeypatch.setattr(connections, "github_mcp_is_usably_configured", lambda config: True)
    resolved = {}
    connections.classify_github_connections(
        [
            {
                "id": "github-managed-1",
                "service": "github",
                "status": "active",
                "instances": [
                    {"name": "work", "credentials": {"auth_token": "token", "is_default": "true"}}
                ],
            }
        ],
        resolved,
    )
    assert resolved["_all_github_instances"][0]["connection_id"] == "github-managed-1"
    assert resolved["github"]["connection_id"] == "github-managed-1"
    assert connections.select_github_connection(resolved, "github-managed-1")["github"][
        "auth_token"
    ] == "token"
